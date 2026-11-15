"""Read-only admission gate for a separate judge using spare GPU memory.

This is explicitly NOT an exclusive-idle-card claim or an ownership proof. The
NVML entries allowed here are unresolved records absent from the supplied host
/proc view. They are never reset, signalled, or silently called our processes.

Only the already audited residual PID1632241 is allowed by default. Expanding
that allowlist requires a new explicit caller-side audit. This gate is for
PRE-LAUNCH use: after a judge starts, its visible compute PID correctly makes
this admission test fail. Runtime supervision must separately verify its own
process receipts and continue recording residual observations.
"""
from __future__ import annotations

import csv
import io
import math
import os
from pathlib import Path
import stat
import subprocess
import time

DEFAULT_ORPHAN_PIDS = frozenset({1632241})
MIN_FREE_MIB = 16384
STABLE_SECONDS = 90.0
GPU_QUERY = ['nvidia-smi',
    '--query-gpu=index,uuid,memory.total,memory.used,memory.free,utilization.gpu',
    '--format=csv,noheader,nounits']
APP_QUERY = ['nvidia-smi',
    '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory',
    '--format=csv,noheader,nounits']


def _query(command):
    return subprocess.check_output(command, text=True, stderr=subprocess.PIPE, timeout=10)


def _integer(value, name):
    if isinstance(value, bool):
        raise ValueError(name + ' must not be bool')
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip())
    else:
        raise ValueError('Unmeasurable ' + name)
    if result < 0:
        raise ValueError(name + ' must be nonnegative')
    return result


def _probe_pid(pid, proc_root):
    """Only explicit ENOENT is absence; permission/other errors are not absence."""
    try:
        root_info = Path(proc_root).stat()
        if not stat.S_ISDIR(root_info.st_mode):
            raise ValueError('The supplied host proc root is not a directory')
        info = (Path(proc_root) / str(pid)).stat()
        return {'visible': True, 'uid': info.st_uid, 'error': None}
    except FileNotFoundError as error:
        # A missing /proc mount must never classify every process as an orphan.
        try:
            root_info = Path(proc_root).stat()
            if not stat.S_ISDIR(root_info.st_mode):
                raise ValueError('Invalid proc root')
        except Exception as root_error:
            return {'visible': None, 'uid': None,
                    'error': type(root_error).__name__ + ': ' + str(root_error)}
        return {'visible': False, 'uid': None, 'error': None}
    except Exception as error:
        return {'visible': None, 'uid': None,
                'error': type(error).__name__ + ': ' + str(error)}


def _rows(text, expected_fields, label):
    result = []
    for row in csv.reader(io.StringIO(text)):
        if not row or all(not field.strip() for field in row):
            continue
        if len(row) != expected_fields:
            raise ValueError('Unexpected ' + label + ' CSV fields')
        result.append([field.strip() for field in row])
    return result


def observe_spare(index, *, query=_query, proc_root=Path('/proc'),
                  pid_probe=None, allowed_orphan_pids=DEFAULT_ORPHAN_PIDS):
    """Return auditable read-only evidence; all observation errors deny admission.

    `query` and `pid_probe` are dependency-injection points for CPU fixtures.
    The default implementation reads nvidia-smi and process directory metadata
    only. It does not inspect command lines, environments or sealed data.
    """
    observation = {'eligible': False, 'reason': 'observation_not_completed',
        'index': index, 'uuid': None, 'free_mib': None, 'used_mib': None,
        'total_mib': None, 'utilization': None, 'orphan_pids': [],
        'orphan_records': [], 'visible_compute_pids': [], 'compute_records': [],
        'errors': [], 'observed_utc': time.time(), 'whole_card_exclusive': False,
        'ownership_established': False, 'admission_only': True,
        'minimum_free_mib': MIN_FREE_MIB,
        'interpretation': 'Unresolved NVML records, not visible in this host proc view; no reset or signalling'}
    try:
        index = _integer(index, 'GPU index')
        allowed = {_integer(pid, 'allowed orphan PID') for pid in allowed_orphan_pids}
        if 0 in allowed:
            raise ValueError('PID0 cannot be an allowed orphan')
        observation.update(index=index, allowed_orphan_pids=sorted(allowed))
        rows = _rows(query(list(GPU_QUERY)), 6, 'GPU')
        matching = [row for row in rows if _integer(row[0], 'GPU index') == index]
        if len(matching) != 1:
            raise ValueError('Requested GPU must have exactly one measurable row')
        _, uuid, total, used, free, util = matching[0]
        if not uuid.startswith('GPU-'):
            raise ValueError('Missing physical GPU UUID')
        observation.update(uuid=uuid, total_mib=_integer(total, 'total memory'),
            used_mib=_integer(used, 'used memory'), free_mib=_integer(free, 'free memory'),
            utilization=_integer(util, 'GPU utilization'))
        if (observation['total_mib'] <= 0 or observation['free_mib'] > observation['total_mib']
                or observation['used_mib'] > observation['total_mib'] or observation['utilization'] > 100):
            raise ValueError('Inconsistent GPU measurements')
        applications = _rows(query(list(APP_QUERY)), 4, 'compute application')
        chosen = [row for row in applications if row[0] == uuid]
        seen = set(); unknown_markers = []; unapproved = []
        for _, pid_text, name, used_text in chosen:
            pid = _integer(pid_text, 'compute PID')
            if not pid or pid in seen:
                raise ValueError('Invalid or duplicate compute PID')
            seen.add(pid)
            used_mib = _integer(used_text, 'per-process used memory')
            state = pid_probe(pid) if pid_probe is not None else _probe_pid(pid, proc_root)
            if not isinstance(state, dict) or state.get('visible') not in (True, False, None):
                raise ValueError('Invalid host PID observation')
            record = {'pid': pid, 'process_name': name, 'used_mib': used_mib,
                      'host_visible': state.get('visible'), 'uid': state.get('uid'),
                      'host_probe_error': state.get('error')}
            observation['compute_records'].append(record)
            if state.get('visible') is True:
                # No UID exception: any visible compute process blocks admission.
                observation['visible_compute_pids'].append(pid)
            elif state.get('error') or state.get('visible') is not False:
                observation['errors'].append('PID' + str(pid) + ': ' + str(state.get('error', 'unknown visibility')))
            else:
                if name.casefold() != '[not found]':
                    unknown_markers.append(pid)
                if pid not in allowed:
                    unapproved.append(pid)
                if name.casefold() == '[not found]' and pid in allowed:
                    observation['orphan_pids'].append(pid)
                    observation['orphan_records'].append(record)
        observation['orphan_pids'].sort()
        observation['orphan_records'].sort(key=lambda row: row['pid'])
        observation['visible_compute_pids'].sort()
        if observation['errors']:
            observation['reason'] = 'host_observation_error'
        elif observation['visible_compute_pids']:
            observation['reason'] = 'visible_compute_process'
        elif unknown_markers:
            observation['reason'] = 'absent_process_without_not_found_marker'
        elif unapproved:
            observation['reason'] = 'unapproved_unresolved_pid'
        elif observation['utilization'] != 0:
            observation['reason'] = 'gpu_utilization_nonzero'
        elif observation['free_mib'] < MIN_FREE_MIB:
            observation['reason'] = 'insufficient_spare_memory'
        else:
            observation.update(eligible=True, reason='admission_candidate_with_unresolved_residual'
                               if observation['orphan_pids'] else 'admission_candidate_no_compute_records')
        observation['unapproved_pids'] = sorted(unapproved)
        observation['absent_without_marker_pids'] = sorted(unknown_markers)
    except Exception as error:
        observation.update(eligible=False, reason='observation_error')
        observation['errors'].append(type(error).__name__ + ': ' + str(error))
    return observation


class SpareGate:
    """Require 90 continuous seconds of the same admitted residual signature."""
    def __init__(self):
        self.signature = None
        self.since = None
        self.last_now = None

    def observe(self, observation, now):
        try:
            if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
                raise ValueError('Invalid monotonic time')
            valid = (observation.get('eligible') is True and not observation.get('errors')
                     and observation.get('utilization') == 0
                     and _integer(observation.get('free_mib'), 'free memory') >= MIN_FREE_MIB
                     and not observation.get('visible_compute_pids'))
            pids = tuple(sorted(_integer(pid, 'orphan PID') for pid in observation.get('orphan_pids', [])))
            if len(set(pids)) != len(pids):
                raise ValueError('Repeated residual PID')
            signature = (observation['index'], observation['uuid'], pids,
                         tuple((row['pid'], row['used_mib']) for row in observation.get('orphan_records', [])))
            if not isinstance(observation['uuid'], str) or not observation['uuid'].startswith('GPU-'):
                raise ValueError('Missing GPU identity')
        except Exception as error:
            self.signature = self.since = self.last_now = None
            return {'ready': False, 'eligible': False, 'idle_seconds': 0.,
                    'reason': 'invalid_gate_observation: ' + str(error), 'whole_card_exclusive': False}
        if self.last_now is not None and now < self.last_now:
            self.signature, self.since, self.last_now = signature if valid else None, now if valid else None, now
            return {'ready': False, 'eligible': valid, 'idle_seconds': 0.,
                    'reason': 'clock_moved_backwards_reset', 'whole_card_exclusive': False}
        self.last_now = now
        if not valid:
            self.signature = self.since = None
            return {'ready': False, 'eligible': False, 'idle_seconds': 0.,
                    'reason': observation.get('reason', 'not_admitted'), 'whole_card_exclusive': False}
        changed = signature != self.signature
        if changed or self.since is None:
            self.signature, self.since = signature, now
        elapsed = now - self.since
        return {'ready': elapsed >= STABLE_SECONDS, 'eligible': True,
                'idle_seconds': elapsed, 'required_stable_seconds': STABLE_SECONDS,
                'signature_changed': changed, 'index': observation['index'], 'uuid': observation['uuid'],
                'orphan_pids': list(pids), 'reason': observation['reason'],
                'whole_card_exclusive': False, 'ownership_established': False}
