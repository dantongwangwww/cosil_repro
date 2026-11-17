#!/usr/bin/env bash
set -euo pipefail
graphlocator_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
graphlocator_gpu="$1"
graphlocator_port="$2"
export CUDA_VISIBLE_DEVICES="$graphlocator_gpu"
export VLLM_BATCH_INVARIANT=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export DO_NOT_TRACK=1
export HF_HUB_OFFLINE=1
exec /mnt/skygruop0/home/wdt/miniconda3/envs/cosil/bin/vllm serve /home/wdt/models/qwen25coder7b \
  --served-model-name llama3 --port "$graphlocator_port" --seed 0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --max-model-len 65536 --max-num-seqs 4 \
  --attention-backend TRITON_ATTN --enforce-eager \
  --hf-overrides '{"max_position_embeddings":131072,"rope_scaling":{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":32768}}' \
  --gpu-memory-utilization 0.92 > "$graphlocator_root/results/qwen_adapt_v2/service_logs/qwen_gpu${graphlocator_gpu}.log" 2>&1
