#!/usr/bin/env python3
"""Read existing audit raw logs; verify error counts without replaying tools."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--audit-dir', type=Path, default=Path(__file__).resolve().parent)
a = p.parse_args()
manifest = json.loads((a.audit_dir/'source_projection_manifest.json').read_text())
expected = json.loads((a.audit_dir/'工具错误类型补充.json').read_text())
counts, affected = Counter(), defaultdict(set)
for binding in manifest['records']:
    raw = Path(binding['raw_result_path'])
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == binding['raw_result_sha256']
    for log in raw.parent.glob('samples/sample_*/tools.jsonl'):
        for line in log.read_text().splitlines():
            event = json.loads(line)
            if event.get('status') == 'success':
                continue
            message = str(event.get('error', event.get('output', '')))
            if message.startswith('ToolError: AssertionError:'):
                kind = '运行时边类型枚举不合法'
            elif message.startswith('ToolError: ValueError:') and 'kth(' in message and 'out of bounds' in message:
                kind = '检索工具top-k边界越界'
            else:
                kind = '检索内部IndexError，触发点不确定'
            counts[kind] += 1
            affected[kind].add(binding['instance_id'])
actual_affected = {k: len(v) for k, v in affected.items()}
assert dict(counts) == expected['event_counts']
assert actual_affected == expected['affected_tasks']
print(json.dumps({'status':'PASS', 'events':sum(counts.values()), 'counts':dict(counts),
                  'affected_tasks':actual_affected, 'model_calls':0, 'tool_replays':0}, ensure_ascii=False))
