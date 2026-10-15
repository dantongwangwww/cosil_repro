#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /home/wdt/miniconda3/etc/profile.d/conda.sh
conda activate cosil
set -u
export PYTHONPATH="$PWD:$PWD/afl/fl:${PYTHONPATH:-}"
export PROJECT_FILE_LOC="$PWD/repo_structures_verified"
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
phase="${1:-prepare}"
shift || true
case "$phase" in
  annotations) exec python -u code_v3b/gen_annotations_300.py "$@" ;;
  prepare) exec python -u code_v3b/run_experiment_300.py --phase prepare "$@" ;;
  canary) exec python -u code_v3b/run_experiment_300.py --phase canary "$@" ;;
  run) exec python -u code_v3b/run_experiment_300.py --phase run "$@" ;;
  pipeline) exec python -u code_v3b/pipeline_300.py "$@" ;;
  *) echo "Unknown phase: $phase" >&2; exit 2 ;;
esac
