#!/usr/bin/env bash
COSIL_NEW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /home/wdt/miniconda3/etc/profile.d/conda.sh
conda activate cosil
export PYTHONPATH="$COSIL_NEW_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PROJECT_FILE_LOC=/home/wdt/cosil_repro/CoSIL/repo_structures_verified
export COSIL_DATASET=/home/wdt/cosil_repro/CoSIL/swebench_local/SWE-bench_Lite_test
export COSIL_MAX_CONTEXT_TOKENS=65536
export COSIL_RETRY_TEXT_TOOL_CALLS=1
export OPENAI_API_BASE=http://127.0.0.1:7333/v1
export OPENAI_API_KEY=empty
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export LITELLM_LOCAL_MODEL_COST_MAP=True
export LITELLM_TELEMETRY=False
export DO_NOT_TRACK=1
cd "$COSIL_NEW_ROOT"
