#!/usr/bin/env bash
set -eo pipefail
source "$(dirname "$0")/qwen_env.sh"
set -u
phase="${1:-canary}"
threads="${COSIL_THREADS:-2}"
common=(--dataset "$COSIL_DATASET" --model openai/llama3 --skip_existing --temperature 0.0)
file_run() {
  python -m CoSIL.fl.CoSIL_localize_file --file_level --output_folder "$1" --output_file "$2" --num_threads "$3" "${common[@]}" "${@:4}"
}
func_run() {
  python -m CoSIL.fl.CoSIL_localize_func --output_folder "$1" --output_file "$2" --loc_file "$3" --num_threads "$4" "${common[@]}" "${@:5}"
}
case "$phase" in
  canary)
    file_run results/canary/file loc_f.jsonl 1 --target_id astropy__astropy-12907
    func_run results/canary/func loc_func.jsonl results/canary/file/loc_f.jsonl 1 --target_id astropy__astropy-12907
    ;;
  file) file_run results/full/file loc_out_full.jsonl "$threads" ;;
  func)
    python scripts/validate_file_inputs.py results/full/file/loc_out_full.jsonl
    func_run results/full/func loc_func_full.jsonl results/full/file/loc_out_full.jsonl "$threads"
    ;;
  full)
    file_run results/full/file loc_out_full.jsonl "$threads"
    python scripts/validate_file_inputs.py results/full/file/loc_out_full.jsonl
    func_run results/full/func loc_func_full.jsonl results/full/file/loc_out_full.jsonl "$threads"
    ;;
  *) echo 'Usage: bash scripts/run_qwen.sh {canary|file|func|full}' >&2; exit 2 ;;
esac
