"""Transactional incremental USD ledger; unknown charges retain their reserve."""
from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import uuid

NANO = 10**9
PEAK_RATES = {"input_miss": 300, "input_hit": 6, "output": 1200}  # nanoUSD/token
PRICE_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"


class BudgetExceeded(RuntimeError):
    pass


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def dollars(value):
    return value / NANO


def worst_charge(prompt_upper: int, max_tokens: int):
    if type(prompt_upper) is not int or type(max_tokens) is not int or prompt_upper < 0 or max_tokens < 1:
        raise ValueError("Nonnegative prompt bound and positive output cap required")
    return prompt_upper * PEAK_RATES["input_miss"] + max_tokens * PEAK_RATES["output"]


def usage_charge(usage, created):
    """Returned usage plus published tariff. Missing cache usage is unknown."""
    if not isinstance(usage, dict) or type(created) is not int:
        return None
    prompt, output = usage.get("prompt_tokens"), usage.get("completion_tokens")
    hit = usage.get("prompt_cache_hit_tokens")
    if hit is None:
        hit = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    if any(type(v) is not int or v < 0 for v in (prompt, output, hit)) or hit > prompt:
        return None
    miss = prompt - hit
    if usage.get("prompt_cache_miss_tokens") not in (None, miss):
        return None
    when = dt.datetime.fromtimestamp(created, dt.timezone.utc)
    peak = when.weekday() < 5 and (1 <= when.hour < 4 or 6 <= when.hour < 10)
    # Current run is a weekend. No guessed holiday discount on weekday peaks.
    divisor = 1 if peak else 2
    amount = (miss * 300 + hit * 6 + output * 1200) // divisor
    return {"nano_usd": amount, "cost_usd": dollars(amount), "prompt_tokens": prompt,
            "completion_tokens": output, "cache_hit_tokens": hit, "cache_miss_tokens": miss,
            "tariff": "peak_no_holiday_assumption" if peak else "off_peak",
            "price_source": PRICE_SOURCE, "response_created_utc": when.isoformat()}


class BudgetLedger:
    def __init__(self, path, cap_usd=5):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("Ledger symlinks forbidden")
        self.lock = self.path.with_suffix(self.path.suffix + ".lock")
        self.cap = int(Decimal(str(cap_usd)) * NANO)
        if self.cap != 5 * NANO:
            raise ValueError("This authorization has an immutable5USD cap")
        with self._transaction() as state:
            if state["cap_nano_usd"] != self.cap:
                raise ValueError("Cannot change existing authorization")

    @contextmanager
    def _transaction(self):
        with self.lock.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.exists():
                state = json.loads(self.path.read_text())
            else:
                state = {"schema": "repair50_incremental_transaction_ledger_v1",
                         "authorization": "repair50_20261024_5USD", "cap_nano_usd": self.cap,
                         "created_at": timestamp(), "reservations": {}, "events": []}
            yield state
            temp = self.path.with_name(self.path.name + "." + uuid.uuid4().hex + ".tmp")
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, self.path)

    @staticmethod
    def _committed(state):
        return sum(row["charge_nano_usd"] if row["status"] == "SETTLED" else row["upper_nano_usd"]
                   for row in state["reservations"].values() if row["status"] != "RELEASED")

    def _add(self, state, key, upper, metadata):
        if key in state["reservations"]:
            raise ValueError("Duplicate reservation identity; never silently resample")
        state["reservations"][key] = {"status": "RESERVED", "upper_nano_usd": upper,
            "charge_nano_usd": None, "metadata": metadata, "created_at": timestamp()}
        state["events"].append({"time": timestamp(), "event": "RESERVE", "id": key, "upper_nano_usd": upper})

    def reserve(self, identity, prompt_upper, max_tokens):
        upper = worst_charge(prompt_upper, max_tokens)
        with self._transaction() as state:
            if self._committed(state) + upper > self.cap:
                raise BudgetExceeded("Incremental5USD cap cannot accommodate the next attempt")
            self._add(state, identity, upper, {"prompt_upper": prompt_upper, "max_tokens": max_tokens})
        return identity

    def reserve_pair(self, pair_id, upper_A_tokens, upper_B_tokens, max_tokens):
        slots = {"A": str(pair_id) + ":A", "B": str(pair_id) + ":B"}
        amounts = {"A": worst_charge(upper_A_tokens, max_tokens), "B": worst_charge(upper_B_tokens, max_tokens)}
        with self._transaction() as state:
            if self._committed(state) + sum(amounts.values()) > self.cap:
                raise BudgetExceeded("Stop before a new pair; preserve context quality and the pending arm")
            if any(key in state["reservations"] for key in slots.values()):
                raise ValueError("Duplicate pair allocation")
            for arm, key in slots.items():
                self._add(state, key, amounts[arm], {"pair": str(pair_id), "arm": arm, "max_tokens": max_tokens,
                                                   "prompt_upper": upper_A_tokens if arm == "A" else upper_B_tokens})
        return slots

    def reservation(self, identity):
        with self._transaction() as state:
            return dict(state["reservations"][identity])

    def settle(self, identity, charge_nano_usd, evidence):
        if type(charge_nano_usd) is not int or charge_nano_usd < 0:
            raise ValueError("Known nonnegative integer cost required")
        with self._transaction() as state:
            row = state["reservations"][identity]
            if row["status"] != "RESERVED":
                raise ValueError("Only a fresh reserved attempt can settle")
            row.update(status="SETTLED", charge_nano_usd=charge_nano_usd, evidence=evidence)
            state["events"].append({"time": timestamp(), "event": "SETTLE", "id": identity,
                                    "charge_nano_usd": charge_nano_usd, "evidence": evidence})
            if charge_nano_usd > row["upper_nano_usd"]:
                state["bound_violation"] = True  # Persist fact and make every next request fail closed.

    def unknown(self, identity, reason):
        with self._transaction() as state:
            row = state["reservations"][identity]
            if row["status"] != "RESERVED":
                raise ValueError("Only a reserved attempt can become unknown")
            row.update(status="UNKNOWN_COST", reason=reason)
            state["events"].append({"time": timestamp(), "event": "UNKNOWN_COST", "id": identity, "reason": reason})

    def release(self, identity, reason="Request not sent"):
        with self._transaction() as state:
            row = state["reservations"][identity]
            if row["status"] != "RESERVED":
                raise ValueError("Sent or unknown requests cannot be released")
            row.update(status="RELEASED", reason=reason)
            state["events"].append({"time": timestamp(), "event": "RELEASE_UNUSED", "id": identity})

    def assert_sendable(self, identity, prompt_upper, max_tokens):
        with self._transaction() as state:
            row = state["reservations"][identity]
            if (state.get("bound_violation") or self._committed(state) > self.cap or row["status"] != "RESERVED"
                    or row["upper_nano_usd"] < worst_charge(prompt_upper, max_tokens)):
                raise BudgetExceeded("Budget or reservation is not safe to send")

    def summary(self):
        with self._transaction() as state:
            rows = list(state["reservations"].values())
            return {"cap_usd": 5, "known_cost_usd": dollars(sum(r["charge_nano_usd"] for r in rows if r["status"] == "SETTLED")),
                    "committed_upper_usd": dollars(self._committed(state)),
                    "unknown_cost_attempts": sum(r["status"] == "UNKNOWN_COST" for r in rows),
                    "settled_attempts": sum(r["status"] == "SETTLED" for r in rows),
                    "active_reservations": sum(r["status"] == "RESERVED" for r in rows),
                    "bound_violation": state.get("bound_violation", False)}
