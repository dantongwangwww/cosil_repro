#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /home/wdt/miniconda3/etc/profile.d/conda.sh
conda activate cosil
set -u
export PROJECT_FILE_LOC="$PWD/repo_structures_verified"
export PYTHONPATH="$PWD:$PWD/afl/fl:${PYTHONPATH:-}"
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
exec python -u code_v3b/run_experiment.py "$@"
