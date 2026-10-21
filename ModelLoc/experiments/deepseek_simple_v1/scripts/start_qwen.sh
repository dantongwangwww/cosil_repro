#!/usr/bin/env bash
set -eo pipefail
source /home/wdt/miniconda3/etc/profile.d/conda.sh
conda activate cosil
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CONDA_PREFIX/bin:$PATH"
export CUDA_VISIBLE_DEVICES=0
export VLLM_BATCH_INVARIANT=1
export VLLM_USE_FLASHINFER_SAMPLER=0
exec vllm serve /home/wdt/models/qwen25coder7b \
 --served-model-name llama3 --port 7333 --seed 0 \
 --max-model-len 65536 --max-num-seqs 4 \
 --attention-backend TRITON_ATTN --enforce-eager \
 --hf-overrides '{"max_position_embeddings":131072,"rope_scaling":{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":32768}}' \
 --gpu-memory-utilization 0.92
