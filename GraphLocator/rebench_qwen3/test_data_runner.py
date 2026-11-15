"""CPU-only isolation, fixed-cohort, namespace and restart-boundary checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from rebench_qwen3 import prepare,runner,worker


def public():
    return {'instance_id':'owner__repo-1','repo':'owner/repo','base_commit':'a'*40,
            'problem_statement':'Source source.py retains its normal repository name.'}


class DataRunnerTests(unittest.TestCase):
    def test_public_schema_rejects_hidden_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'input.json';p.write_text(json.dumps(public()))
            self.assertEqual(worker.instance(p),public())
            for hidden in ['patch','gold','test_patch','FAIL_TO_PASS']:
                p.write_text(json.dumps(public()|{hidden:'forbidden'}))
                with self.assertRaises(ValueError):worker.instance(p)

    def test_prefix_is_parent_order_and_never_outcome_sorting(self):
        rows=[{'instance_id':str(i),'repo':str(i),'observed_hit':int(i%2)} for i in [3,1,4,2]]
        self.assertEqual(prepare.selected(rows,2),rows[:2])
        with self.assertRaises(ValueError):prepare.selected(rows,5)
        with self.assertRaises(ValueError):prepare.selected([rows[0],rows[0]],1)

    def test_base_ast_inventory_keeps_nested_async_and_bom_without_exec(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'source.py').write_text('\ufeffclass Outer:\n    class Inner:\n        async def run(self):\n            def local():\n                return 1\n            return local()\n',encoding='utf-8')
            (root/'broken.py').write_text('def missing(\n')
            result,errors=worker.inventory(root)
            self.assertEqual([x['qualified_name'] for x in result['source.py']],
                             ['Outer','Outer.Inner','Outer.Inner.run','Outer.Inner.run.local'])
            self.assertEqual(result['source.py'][2]['start_line'],3)
            self.assertEqual(errors[0]['path'],'broken.py')

    def test_source_materialization_preserves_bytes_and_refuses_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();(source/'repo.py').write_bytes(b'def f():\n    return 1\n')
            original=root/'original.json';original.write_text(json.dumps(public()))
            run=root/'run';(run/'public/snapshots').mkdir(parents=True)
            row={'instance_id':public()['instance_id'],'source_snapshot':str(source),'source_instance':str(original),
                 'instance':'public/tasks/case/instance.json','snapshot':'public/snapshots/case','instance_sha256':worker.sha(original)}
            sources={row['instance_id']:{'files':[{'path':'repo.py','sha256':worker.sha(source/'repo.py')}]}}
            prepare.materialize(run,row,sources);prepare.materialize(run,row,sources)
            self.assertEqual((run/row['snapshot']).resolve(),source)
            self.assertEqual((run/row['instance']).read_bytes(),original.read_bytes())
            (source/'repo.py').write_text('changed')
            with self.assertRaises(ValueError):prepare.materialize(run,row,sources)

    def test_bwrap_only_mounts_one_source_and_software_no_home_or_gold(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'repo';source.mkdir();work=root/'work';work.mkdir()
            venv=root/'venv';venv.mkdir();(venv/'pyvenv.cfg').write_text('home = /usr/bin\n')
            p=root/'instance.json';p.write_text(json.dumps(public()));g=root/'graph.json';g.write_text('{}')
            g.with_suffix('.receipt.json').write_text('{}')
            with patch.object(runner.shutil,'which',return_value='/usr/bin/bwrap'):
                command=runner.build_command(source_root=Path('/trusted/GraphLocator'),venv=venv,
                    public=p,snapshot=source,work=work,phase='inference',graph=g)
            ro=[(command[i+1],command[i+2]) for i,x in enumerate(command) if x=='--ro-bind']
            self.assertIn((str(source),'/source'),ro);self.assertIn((str(g),'/graph/graph.json'),ro)
            self.assertFalse(any(t in ['/home','/home/wdt','/mnt/skygruop0/home/wdt','/private'] for _,t in ro))
            self.assertIn('--clearenv',command);self.assertIn('--unshare-pid',command)
            self.assertNotIn('OPENAI_API_KEY',command);self.assertNotIn('DEEPSEEK_API_KEY',command)
            self.assertEqual(command[command.index('CUDA_VISIBLE_DEVICES')+1],'')
            self.assertEqual(command[command.index('GRAPHLOCATOR_GRAPH_WORKERS')+1],'2')
            self.assertEqual(command[command.index('PYTHONHASHSEED')+1],'0')

    def test_preflight_rejects_wrong_graph_and_source_before_any_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'selection').mkdir();(run/'public/tasks').mkdir(parents=True)
            source=run/'public/source';source.mkdir();(source/'repo.py').write_text('def f():\n    return 1\n')
            p=run/'public/tasks/instance.json';p.write_text(json.dumps(public()));graph=run/'graph.json';graph.write_text('{}')
            files=[{'path':'repo.py','sha256':worker.sha(source/'repo.py')}]
            row=public()|{'instance':'public/tasks/instance.json','instance_sha256':worker.sha(p),
                'snapshot':'public/source','snapshot_tree_sha256':prepare.digest(files),
                'graph':'graph.json','graph_receipt':'graph.receipt.json'}
            (run/'selection/snapshot_sources.json').write_text(json.dumps({row['instance_id']:{'files':files}}))
            receipt={k:row[k] for k in ['instance_id','repo','base_commit','snapshot_tree_sha256']}|{
                'status':'success','graph_sha256':worker.sha(graph),'source_namespace':'/source','repo_path':'/source',
                'dependency_prewarming':False,'builder_sha256':worker.sha(prepare.ROOT/'rdfs/dependency_graph/graph_generator/tree_sitter_generator/__init__.py')}
            (run/'graph.receipt.json').write_text(json.dumps(receipt))
            self.assertEqual(runner.validate_inputs(run,row,'inference'),public())
            for changed in [{'instance_id':'other'},{'source_namespace':'/wrong'},{'graph_sha256':'wrong'},{'dependency_prewarming':True}]:
                (run/'graph.receipt.json').write_text(json.dumps(receipt|changed))
                with self.assertRaises(ValueError):runner.validate_inputs(run,row,'inference')
            (run/'graph.receipt.json').write_text(json.dumps(receipt));(source/'secret.json').write_text('{}')
            with self.assertRaises(ValueError):runner.validate_inputs(run,row,'inference')

    def test_started_inference_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'selection').mkdir();row=public()
            (run/'selection/manifest.json').write_text(json.dumps({'records':[row]}))
            work=run/'outputs'/row['instance_id'];work.mkdir(parents=True);(work/'runner_started.json').write_text('{}')
            with patch.object(runner.subprocess,'Popen') as start:
                with self.assertRaises(FileExistsError):runner.run_case(run,row['instance_id'])
                start.assert_not_called()

    def test_atomic_artifacts_never_replace_a_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'result.json';worker.write(p,{'terminal':True})
            original=p.read_bytes()
            with self.assertRaises(FileExistsError):worker.write(p,{'terminal':False})
            self.assertEqual(p.read_bytes(),original)

    def test_tool_audit_preserves_exact_return_exception_and_single_call(self):
        events=[];record=lambda event,**fields:events.append({'event':event,**fields})
        original='source/source.py::run\n原始源码';calls=[]
        def search(code,graph,k):calls.append((code,graph,k));return original
        graph=object();wrapped=worker.audit_search(search,record)
        self.assertIs(wrapped('search_node(...)',graph,5),original)
        self.assertEqual(calls,[('search_node(...)',graph,5)])
        self.assertEqual(events[-1]['return_text'],original)
        self.assertEqual(events[-1]['output_sha256'],hashlib.sha256(original.encode()).hexdigest())
        error=ValueError('original error')
        def broken(*args):raise error
        with self.assertRaises(ValueError) as caught:worker.audit_search(broken,record)('bad',graph)
        self.assertIs(caught.exception,error);self.assertEqual(events[-2]['event'],'tool_error')

    def test_causal_parse_audit_preserves_nodes_graph_and_result_identity(self):
        import networkx as nx
        class Node:
            def to_json(self):return json.dumps({'name':'run','location':{'start_line':1,'end_line':2}})
        node=Node();graph=nx.DiGraph();graph.add_node('F1',name='factor',code_element=[node])
        result=(graph,['F1'],[node]);events=[];calls=[]
        def parse(raw,nodes):calls.append((raw,nodes));return result
        before=list(graph.nodes(data=True));wrapped=worker.audit_parse(parse,lambda event,**fields:events.append((event,fields)))
        self.assertIs(wrapped('graph TD',[node]),result)
        self.assertIs(calls[0][1][0],node);self.assertEqual(list(graph.nodes(data=True)),before)
        self.assertEqual(events[-1][1]['graph_nodes'],1)

    def test_graph_cache_drift_is_not_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'public/graphs').mkdir(parents=True)
            row={'instance_id':'case','graph':'public/graphs/case.json','graph_receipt':'public/graphs/case.receipt.json',
                 'snapshot_tree_sha256':'tree'}
            builder=worker.sha(prepare.ROOT/'rdfs/dependency_graph/graph_generator/tree_sitter_generator/__init__.py')
            (run/row['graph']).write_text('changed')
            (run/row['graph_receipt']).write_text(json.dumps({'status':'success','snapshot_tree_sha256':'tree',
                                                           'builder_sha256':builder,'graph_sha256':'different'}))
            with patch.object(prepare,'materialize'),patch.object(runner,'run_case') as start:
                with self.assertRaises(ValueError):prepare.graph_case(run,row,{})
                start.assert_not_called()


if __name__=='__main__':unittest.main()
