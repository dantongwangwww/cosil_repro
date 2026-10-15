"""Run the unchanged final v3 risk rules with verified AST line caching only."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

from code_v5.ast_source_cache import cached_ast_source_lines
from code_v5 import build_pruner_data as miner
from code_v5 import refine_pruner_data_v3 as rules

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"refine_pruner_data_v3.py": "18075ca5a26c85bf2a692d74907460176061e00d8ca24bfad8038739d8a9b3e5",
            "refine_pruner_data.py": "7decc711b94dda810de8780f924ef315b8c6d7fcb0b1be560d883990a8783d33",
            "build_pruner_data.py": "95d56df3bf8d3cbbf41d310c41ab71d2693275c6b57b8721fec43ceda3284372"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output", type=Path, default=ROOT / "results/v5_pruner/data_v3")
    args, _ = parser.parse_known_args()
    output_stats = args.output.resolve() / "statistics.json"
    hashes = {name: sha(ROOT / "code_v5" / name) for name in EXPECTED}
    if hashes != EXPECTED:
        raise RuntimeError("Frozen v3 rules, v2 helper or original miner changed")
    entry_sha = sha(Path(__file__))
    cache_path = ROOT / "code_v5/ast_source_cache.py"
    cache_sha = sha(cache_path)
    original_atomic = miner.atomic_json
    with cached_ast_source_lines(maxsize=128) as cache:
        def annotate_statistics(path, value):
            if Path(path).resolve() == output_stats:
                if value["refiner_sha256"] != EXPECTED["refine_pruner_data_v3.py"]:
                    raise RuntimeError("Statistics do not identify the frozen v3 rule source")
                value = {**value, "refiner_rule_sha256": EXPECTED["refine_pruner_data_v3.py"],
                         "fast_implementation": {"entry_path": str(Path(__file__).resolve()), "entry_sha256": entry_sha,
                            "source_cache_path": str(cache_path), "source_cache_sha256": cache_sha,
                            "original_v3_rule_sha256": EXPECTED["refine_pruner_data_v3.py"],
                            "original_v2_helper_sha256": EXPECTED["refine_pruner_data.py"],
                            "optimization": "unchanged stdlib AST line splitter cached per complete source; fresh list returned",
                            "risk_rules_seed_split_sampling_unchanged": True, "workers": 1,
                            "source_cache": cache["cache_info"]()}}
            return original_atomic(path, value)
        miner.atomic_json = annotate_statistics
        try:
            result = rules.main()
            if hashes != {name: sha(ROOT / "code_v5" / name) for name in EXPECTED}:
                raise RuntimeError("Frozen rule/helper source changed during final data refinement")
            if entry_sha != sha(Path(__file__)) or cache_sha != sha(cache_path):
                raise RuntimeError("Fast implementation source changed during execution")
            return result
        finally:
            miner.atomic_json = original_atomic


if __name__ == "__main__":
    raise SystemExit(main())
