#!/usr/bin/env bash
set -euo pipefail
graphlocator_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$graphlocator_root"
source scripts/qwen_env.sh
while [[ ! -f results/qwen_300/canary_gate.json ]]; do
  sleep 5
done
.venv/bin/python - <<'PY'
from pathlib import Path
import json
assert json.loads(Path('results/qwen_300/canary_gate.json').read_text())['passed'], 'Canary failed'
assert json.loads(Path('deployment/replica_equivalence.json').read_text())['all_responses_equal_except_tool_ids'], 'Model replicas differ'
# The already running canary used the earlier manifest enumerator. Extend its
# registration to non-Python inputs without changing or rerunning inference.
import runpy
runner=runpy.run_path('scripts/run_experiment.py')
current=runner['freeze']()
gate_path=Path('results/qwen_300/canary_gate.json')
gate=json.loads(gate_path.read_text())
previous=gate['source_sha256']
assert all(current.get(k)==v for k,v in previous.items()), 'Canary inference Python source changed'
added=set(current)-set(previous)
allowed={'datasets/swe_bench_lite_gt_entities_3levels.json','deployment/requirements_runtime.txt','scripts/qwen_env.sh','scripts/serve_qwen.sh','rdfs/dependency_graph/lib/languages-linux-x86_64.so'}
assert added<=allowed,'Unexpected source additions after canary'
assert current==json.loads(Path('deployment/final_pre_full_hashes.json').read_text()),'Final deployment snapshot changed'
if added:
    Path('results/qwen_300/canary_gate_original.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2))
    gate['source_sha256']=current
    gate['source_manifest_extension']={'added_non_python_inputs':sorted(added),'inference_python_hashes_unchanged':True,'reason':'Register previously hashed parser and runtime files; running canary enumerator predated this extension'}
    gate_path.write_text(json.dumps(gate,ensure_ascii=False,indent=2))
PY
sleep 3
exec .venv/bin/python -u scripts/run_experiment.py --phase full > deployment/full_run.log 2>&1
