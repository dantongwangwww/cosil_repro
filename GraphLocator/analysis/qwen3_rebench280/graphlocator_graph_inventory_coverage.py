"""Post-terminal graph/AST coverage diagnostic. Never runs repository/model/tool code.

A target is present only if a function-family graph node maps by exact public
base AST file, original leaf name and definition start to its complete QName.
No class/file expansion, fuzzy names, containment or Gold-assisted mapping.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import shutil
import time
import unittest

FUNCTION_TYPES = frozenset(('FUNCTION', 'METHOD', 'CONSTRUCTOR'))

def source_relative(raw):
    if not isinstance(raw, str) or not raw.startswith('/source/'):
        return None
    path = raw[len('/source/'):]
    parts = PurePosixPath(path).parts
    if not path or '..' in parts or '.' in parts or path.startswith('/'):
        return None
    return path


def function_index(graph, definitions):
    anchors = defaultdict(list)
    for path, rows in definitions.items():
        for row in rows:
            if row.get('kind') == 'function':
                qname = row.get('qualified_name', '')
                anchors[(path, row.get('start_line'), qname.rsplit('.', 1)[-1])].append(row)
    canonical = defaultdict(list)
    unverified = Counter()
    exact_other_kinds = defaultdict(list)
    for index, node in enumerate(graph.get('nodes', [])):
        loc = node.get('location') or {}
        path = source_relative(loc.get('file_path'))
        key = (path, loc.get('start_line'), node.get('name'))
        matching = anchors.get(key, [])
        evidence = {'graph_node_index': index, 'graph_type': node.get('type'),
                    'graph_name': node.get('name'), 'path': path,
                    'start_line': loc.get('start_line'), 'end_line': loc.get('end_line')}
        if node.get('type') not in FUNCTION_TYPES:
            for row in matching:
                exact_other_kinds[path + '::' + row['qualified_name']].append(evidence)
            continue
        if path is None:
            unverified['outside_source_or_invalid_path'] += 1
        elif len(matching) != 1:
            unverified['no_unique_exact_public_ast_anchor'] += 1
        else:
            qname = path + '::' + matching[0]['qualified_name']
            canonical[qname].append(evidence)
    return canonical, exact_other_kinds, dict(unverified)



def graph_binding(result, record, expected, run_start):
    """Use the worker result normally; controller timeout keeps original ledger proof."""
    value=result.get('graph_sha256')
    if value is not None:
        if value != expected: raise ValueError('Result graph SHA differs')
        return 'worker_result_graph_sha256'
    if not (result.get('controller_created_terminal') is True and result.get('status') == 'failed'):
        raise ValueError('Missing result graph binding outside explicit controller terminal')
    if not isinstance(run_start,dict) or run_start.get('event') != 'run_start':
        raise ValueError('Controller terminal lacks original worker run_start')
    if any(run_start.get(key)!=record.get(key) for key in ('instance_id','repo','base_commit')):
        raise ValueError('Original worker run_start identity differs')
    if run_start.get('graph_sha256')!=expected:
        raise ValueError('Original worker run_start graph SHA differs')
    return 'original_worker_run_start_for_controller_created_terminal'


def target_coverage(targets, definitions, index, other):
    rows = []
    for target in targets:
        if not isinstance(target, str) or target.count('::') != 1:
            raise ValueError('Final evaluation Gold must contain canonical path::QName strings')
        path, qname = target.split('::', 1)
        matches = [r for r in definitions.get(path, [])
                   if r.get('kind') == 'function' and r.get('qualified_name') == qname]
        if index.get(target):
            status = 'PRESENT_EXACT_GRAPH_AST_ANCHOR'
        elif len(matches) == 0:
            status = 'UNVERIFIED_TARGET_ABSENT_FROM_PUBLIC_AST'
        elif len(matches) > 1:
            status = 'UNVERIFIED_MULTIPLE_PUBLIC_AST_DEFINITIONS'
        elif other.get(target):
            status = 'NO_FUNCTION_NODE_EXACT_ANCHOR_HAS_NONFUNCTION_KIND'
        else:
            status = 'NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET'
        rows.append({'target': target, 'status': status,
                     'public_ast_definition_matches': matches,
                     'exact_function_graph_nodes': index.get(target, []),
                     'same_exact_anchor_other_kind_nodes': other.get(target, [])})
    return rows


class Tests(unittest.TestCase):
    def fixture(self):
        definitions = {'p.py': [
            {'kind': 'function', 'qualified_name': 'C.fn', 'start_line': 3, 'end_line': 8},
            {'kind': 'function', 'qualified_name': 'outer.fn', 'start_line': 12, 'end_line': 15},
        ]}
        def node(kind, name, line, path='/source/p.py'):
            return {'type': kind, 'name': name, 'location': {'file_path': path, 'start_line': line, 'end_line': line + 2}}
        return definitions, node
    def test_controller_terminal_requires_original_run_start(self):
        record={'instance_id':'i','repo':'r','base_commit':'b'}
        result={'status':'failed','controller_created_terminal':True}
        event=dict(record,event='run_start',graph_sha256='expected')
        self.assertEqual(graph_binding(result,record,'expected',event),'original_worker_run_start_for_controller_created_terminal')
        with self.assertRaises(ValueError):graph_binding(result,record,'expected',dict(event,base_commit='other'))
        with self.assertRaises(ValueError):graph_binding(result,record,'expected',None)
    def test_result_sha_never_overridden_by_event(self):
        record={'instance_id':'i','repo':'r','base_commit':'b'}
        event=dict(record,event='run_start',graph_sha256='expected')
        with self.assertRaises(ValueError):graph_binding({'graph_sha256':'wrong'},record,'expected',event)
        with self.assertRaises(ValueError):graph_binding({'status':'failed'},record,'expected',event)
    def test_function_family_exact_and_nested(self):
        defs, n = self.fixture(); graph = {'nodes': [n('METHOD','fn',3), n('CONSTRUCTOR','fn',12)]}
        idx, other, bad = function_index(graph, defs)
        self.assertEqual(set(idx), {'p.py::C.fn', 'p.py::outer.fn'})
        self.assertEqual(bad, {})
    def test_class_not_expanded(self):
        defs, n = self.fixture(); idx, other, bad = function_index({'nodes':[n('CLASS','fn',3)]}, defs)
        self.assertEqual(dict(idx), {})
        r = target_coverage(['p.py::C.fn'], defs, idx, other)[0]
        self.assertEqual(r['status'],'NO_FUNCTION_NODE_EXACT_ANCHOR_HAS_NONFUNCTION_KIND')
    def test_wrong_coordinate_no_name_fallback(self):
        defs, n = self.fixture(); idx, other, _ = function_index({'nodes':[n('FUNCTION','fn',4)]},defs)
        self.assertEqual(dict(idx),{})
        self.assertEqual(target_coverage(['p.py::C.fn'],defs,idx,other)[0]['status'], 'NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET')
    def test_no_ast_unverified_not_absent(self):
        defs,n=self.fixture();idx,other,_=function_index({'nodes':[]},defs)
        self.assertEqual(target_coverage(['missing.py::fn'],defs,idx,other)[0]['status'],'UNVERIFIED_TARGET_ABSENT_FROM_PUBLIC_AST')
    def test_bad_path_not_canonicalized(self):
        defs,n=self.fixture();idx,other,bad=function_index({'nodes':[n('FUNCTION','fn',3,'/source/../p.py')]},defs)
        self.assertEqual(dict(idx),{});self.assertEqual(bad['outside_source_or_invalid_path'],1)
    def test_ambiguous_anchor_not_resolved_by_gold(self):
        defs,n=self.fixture();defs['p.py'].append(dict(defs['p.py'][0],qualified_name='D.fn'))
        idx,other,bad=function_index({'nodes':[n('FUNCTION','fn',3)]},defs)
        self.assertEqual(dict(idx),{});self.assertEqual(bad['no_unique_exact_public_ast_anchor'],1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--run-dir',type=Path);parser.add_argument('--scope',choices=['pilot20','full280'])
    parser.add_argument('--evaluation-json',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--audit-script',type=Path,default=Path('/tmp/graphlocator_v3_final_tool_failure_audit.py'))
    args=parser.parse_args()
    if args.self_test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if not all((args.run_dir,args.scope,args.evaluation_json,args.output)):
        parser.error('run/scope/evaluation/output required')
    spec=importlib.util.spec_from_file_location('audit',args.audit_script)
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    reader=audit.Reader();run=args.run_dir.resolve();started=time.time()
    records,outputs,status=audit.status_scope(run,args.scope,reader)
    if status['status']!='FINAL_SCOPE_READY':
        print(json.dumps({'status':'STATUS_ONLY_WAIT_FOR_ALL_TERMINAL','scope':args.scope,
                          'evaluation_opened':False,'scope_state':status},ensure_ascii=False))
        return
    # Gold appears only in final scoring joined after the complete scope barrier.
    protocol=reader.data(run/'protocol.json');evaluation=reader.data(args.evaluation_json)
    if evaluation['summary'].get('status')!='FINAL' or evaluation['summary'].get('scope')!=args.scope or evaluation['summary'].get('protocol_sha256')!=reader.hashes[str(run/'protocol.json')]:
        raise ValueError('Different/nonfinal scoring protocol')
    scored={r['instance_id']:r for r in evaluation['records']}
    if set(scored)!={r['instance_id'] for r in records}:
        raise ValueError('Final evaluation task IDs differ from fixed scope')
    if args.output.exists():raise FileExistsError('Preserve earlier diagnostic outputs; use a new output directory')
    rows=[];target_counts=Counter();issue_counts=Counter();node_counts=Counter()
    for record in records:
        iid=record['instance_id'];work=run/'outputs'/iid;result=outputs[iid];score=scored[iid]
        resultpath=str(work/'result.json')
        if evaluation['summary']['worker_result_sha256'].get(resultpath)!=reader.hashes[resultpath]:
            raise ValueError('Final evaluation uses different raw result bytes')
        graphpath=run/record['graph'];receiptpath=run/record['graph_receipt']
        graph=reader.data(graphpath);receipt=reader.data(receiptpath)
        if not graph or not receipt or receipt.get('status')!='success' or receipt.get('graph_sha256')!=reader.hashes[str(graphpath)]:
            raise ValueError('Graph receipt hash mismatch: '+iid)
        for key in ('instance_id','repo','base_commit'):
            if receipt.get(key)!=record.get(key):raise ValueError('Graph identity mismatch: '+iid)
        run_start=None
        if result.get('graph_sha256') is None:
            logpath=work/'http/events.jsonl'
            # Original worker emits run_start before search; only that first proof is used.
            events=reader.data(logpath,jsonl=True)
            starts=[e for e in events if e.get('event')=='run_start']
            if len(starts)==1:run_start=starts[0]
        binding_source=graph_binding(result,record,reader.hashes[str(graphpath)],run_start)
        public=reader.data(work/'public_inventory.json') or {};definitions=public.get('definitions',{})
        idx,other,unverified=function_index(graph,definitions)
        targets=score['gold_functions'];coverage=target_coverage(targets,definitions,idx,other)
        statuses=Counter(r['status'] for r in coverage);target_counts.update(statuses);node_counts.update(unverified)
        present=sum(x['status']=='PRESENT_EXACT_GRAPH_AST_ANCHOR' for x in coverage)
        unknown=sum(x['status'].startswith('UNVERIFIED_') for x in coverage)
        taskstatus='ALL_TARGETS_PRESENT' if coverage and present==len(coverage) else 'PARTLY_PRESENT' if present else 'NO_TARGET_EXACTLY_VERIFIED'
        if unknown:taskstatus+='_WITH_UNVERIFIED_PUBLIC_AST_TARGETS'
        issue_counts[taskstatus]+=1
        rows.append({'instance_id':iid,'status':result['status'],'function_hit5':score['graphlocator_function']['hit5'],
                     'coverage_status':taskstatus,'target_count':len(coverage),'present_exact_count':present,
                     'unverified_ast_target_count':unknown,'target_details':coverage,
                     'public_ast_parse_errors':public.get('parse_errors',[]),
                     'graph_node_total':len(graph.get('nodes',[])),
                     'canonical_function_identity_count':len(idx),'unverified_graph_function_node_counts':unverified,
                     'graph_sha256':reader.hashes[str(graphpath)],'worker_graph_binding_source':binding_source,'graph_receipt_sha256':reader.hashes[str(receiptpath)],
                     'public_inventory_sha256':reader.hashes[str(work/'public_inventory.json')],
                     'source_result_sha256':reader.hashes[resultpath]})
    args.output.mkdir(parents=True)
    summary={'status':'FINAL','scope':args.scope,'rule':'Exact public AST path/kind/definition-start/original-leaf identity, no fuzzy name or class expansion',
             'target_status_counts':dict(target_counts),'issue_status_counts':dict(issue_counts),
             'unverified_graph_function_node_counts':dict(node_counts),'records':rows,
             'elapsed_seconds':time.time()-started,'new_model_calls':0,'tool_replays':0,
             'private_gold_opened':False,'final_scoring_joined':True,'read_errors':reader.errors,
             'source_files_sha256':reader.hashes,
             'limitations':['No exact function node is a graph-inventory constraint, not proof target source is absent from all class/file content.',
                            'A graph node present does not certify search recall, source use or repair reasoning.',
                            'Missing/ambiguous public AST target remains UNVERIFIED, never asserted graph absent.',
                            'Definition coordinates identify functions; graph end ranges/content completeness are not revalidated.']}
    audit.dump(args.output/'图库存目标覆盖核验.json',summary);audit.csv_write(args.output/'逐题图库存目标覆盖.csv',rows)
    lines=['# 静态图库存的既有目标函数覆盖核验','',f"{args.scope}全终态后连接同协议最终评价，纯CPU读取既有静态图与worker公开AST库存。零新增模型调用、零工具重放，不改预测。",'',
           '仅FUNCTION/METHOD/CONSTRUCTOR节点按文件路径、函数定义起点和原叶名唯一对齐公开AST限定名。类、文件与近似拼写不扩成目标函数。','',
           '## 目标级精确核验','', '| 状态 | 目标数 |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in target_counts.items()]
    lines += ['', '## 逐题覆盖','', '| 状态 | 题数 |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in issue_counts.items()]
    lines += ['', '## 未能全部精确验证的题目','']
    for row in rows:
        if row['coverage_status']=='ALL_TARGETS_PRESENT':continue
        lines += [f"### {row['instance_id']}",'',f"- 最终函数Hit@5：{row['function_hit5']}；图库存状态：{row['coverage_status']}。"]
        lines += [f"- {r['target']}：{r['status']}。" for r in row['target_details']]
        lines += ['']
    lines += ['## 解释边界','', *['- '+s for s in summary['limitations']], '']
    (args.output/'图库存目标覆盖核验.md').write_text('\n'.join(lines),encoding='utf-8')
    shutil.copyfile(__file__,args.output/'analysis_graph_inventory_coverage.py')
    print(json.dumps({k:summary[k] for k in ('status','scope','target_status_counts','issue_status_counts','elapsed_seconds','read_errors')},ensure_ascii=False))

if __name__=='__main__':main()
