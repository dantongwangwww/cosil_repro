"""Synthetic CPU tests: membership, private projection and original runtime adapter."""
import copy
from contextlib import ExitStack, contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import prepare as p


@contextmanager
def fixture():
    import pyarrow as pa
    import pyarrow.parquet as pq
    with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
        parent = Path(folder)/'official'; prior = parent/'pilot100'
        parent.mkdir(); prior.mkdir()
        rows = [{'instance_id': f'owner__repo-{i}', 'repo': 'owner/repo',
                 'base_commit': f'{i+1:040x}'} for i in range(560)]
        parquet = parent/'dataset_download/data/test-00000-of-00001.parquet'
        parquet.parent.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist(rows), parquet)
        data_sha = p.b.sha(parquet)
        scorer=parent/p.SCORER_RELATIVE
        scorer.parent.mkdir(parents=True)
        scorer.write_text('# synthetic frozen official evaluator asset\n')
        protocol = {'name': 'synthetic_official', 'allocated': 560,
            'source_failures': 'keep all560 without replacement', 'thinking': False,
            'context_limit': 65536, 'training_repo_overlap_repos': []}
        p.b.write(parent/'protocol.json', protocol)
        source_rows = [dict(r, source=p.original.DATASET, source_id=p.original.SOURCE_ID,
            source_revision=p.original.REVISION, source_sha256=data_sha, train_repo_seen=False)
            for r in rows]
        alloc = {'n':560, 'allocated':560, 'records':source_rows}
        p.b.write(parent/'allocation.json', alloc)
        selected = [{k:v for k,v in r.items() if k!='train_repo_seen'} for r in source_rows]
        p.b.write(parent/'selection/selection.json', {'n':560,'allocated':560,
            'records':selected,'selection_frozen':True,'status':'READY'})
        prep = [{k:r[k] for k in (*p.IDENTITY,'source_id','source_revision','source_sha256')} |
                {'problem_statement':'Synthetic public issue.', 'base_files_sha256':{'m.py':'a'*64}}
                for r in source_rows]
        ledger = [{'instance_id':r['instance_id'],'status':'SOURCE_PROOF_READY',
            'runtime_preparation_blocked':False,'runtime_preparation_errors':{},
            'case_receipt':'immutable-parent-evidence','train_repo_seen':False}
            for r in source_rows]
        p.b.write(parent/'evaluator_private/preparation_records.private.json', {'records':prep})
        p.b.write(parent/'evaluator_private/preparation_ledger.private.json', {'allocated':560,'records':ledger})
        for name in ['official_gold.private.json','base_inventory.private.json']:
            p.b.write(parent/'evaluator_private'/name,
                {r['instance_id']:{'private_target_marker':'NEVER_MODEL_INPUT'} for r in source_rows})
        p.b.write(parent/'evaluator_private/isolation_audit.private.json',
                  {'sealed_test_contents_read_or_hashed':False})
        chosen = sorted(source_rows,key=p.pilot.key)[:100]
        p.b.write(prior/'allocation.json', dict(alloc,n=100,allocated=100,records=chosen))
        p.b.write(prior/'protocol.json', dict(protocol,allocated=100))
        p.b.write(prior/'selection/sampling_freeze.json', {'seed':p.SEED})
        p.b.write(prior/'audits/pilot_projection_gate.json', {'parent_files_sha256':{
            str(parent/'protocol.json'):p.b.sha(parent/'protocol.json'),
            str(parent/'allocation.json'):p.b.sha(parent/'allocation.json')}})
        for obj, name, value in [(p.original,'PROTOCOL_SHA',p.b.sha(parent/'protocol.json')),
                (p.pilot,'PARENT_ALLOCATION_SHA',p.b.sha(parent/'allocation.json')),
                (p,'PILOT_PROTOCOL_SHA',p.b.sha(prior/'protocol.json')),
                (p,'PILOT_ALLOCATION_SHA',p.b.sha(prior/'allocation.json')),
                (p.original,'PARQUET_SHA',data_sha),
                (p,'SCORER_SHA',p.b.sha(scorer))]:
            stack.enter_context(patch.object(obj,name,value))
        yield parent, prior, source_rows


class MembershipTests(unittest.TestCase):
    def test_exact_suffix_disjoint_and60_tail_without_repo_cap(self):
        rows = [{'instance_id': f'x__y-{i}','repo':'same/repo'} for i in range(560)]
        ordered = sorted(rows,key=p.pilot.key)
        result = p.ordered_remaining(list(reversed(rows)), ordered[:100])
        self.assertEqual(result,ordered[100:])
        self.assertEqual([len(result[i:i+100]) for i in range(0,460,100)], [100,100,100,100,60])
        self.assertFalse({r['instance_id'] for r in ordered[:100]} &
                         {r['instance_id'] for r in result})
        self.assertEqual(len({r['repo'] for r in result}),1)

    def test_outcomes_never_enter_hash_key_and_wrong_pilot_refused(self):
        rows = [{'instance_id':f'x__y-{i}','score':i%2} for i in range(560)]
        old = sorted(rows,key=p.pilot.key)[:100]
        expected = [r['instance_id'] for r in p.ordered_remaining(rows,old)]
        changed = [dict(r,score=99) for r in rows]
        self.assertEqual(expected,[r['instance_id'] for r in
            p.ordered_remaining(changed,sorted(changed,key=p.pilot.key)[:100])])
        with self.assertRaisesRegex(ValueError,'Pilot'):
            p.ordered_remaining(rows,sorted(rows,key=p.pilot.key)[1:101])
        with self.assertRaisesRegex(ValueError,'560'):
            p.ordered_remaining(rows+[rows[0]],old)

    def test_full_freeze_projection_and_strict_batch_interface(self):
        with fixture() as (parent,prior,rows):
            before={str(x):p.b.sha(x) for x in [parent/'protocol.json',prior/'allocation.json']}
            plan=p.freeze_plan(parent,prior,parent/'continuation460')
            self.assertEqual(plan['status'],'FROZEN')
            self.assertEqual([x['n'] for x in plan['batches']],[100,100,100,100,60])
            self.assertEqual(len(set(i for x in plan['batches'] for i in x['instance_ids'])),460)
            for x in plan['batches']:
                root,verified,batch=p.check_batch(x['work'])
                self.assertEqual(root,parent/'continuation460');self.assertEqual(verified,plan)
                self.assertEqual(batch,x)
                selected=p.b.read(Path(x['work'])/'selection/selection.json')
                self.assertFalse(any('private_target_marker' in str(r) for r in selected['records']))
                self.assertEqual(len(p.b.read(Path(x['work'])/'evaluator_private/official_gold.private.json')),x['n'])
                self.assertEqual(p.b.sha(Path(x['work'])/'dataset_download/data/test-00000-of-00001.parquet'),p.original.PARQUET_SHA)
                self.assertEqual(p.b.sha(Path(x['work'])/p.SCORER_RELATIVE),p.SCORER_SHA)
            self.assertTrue(all(p.b.sha(path)==h for path,h in before.items()))

    def test_projected_scorer_satisfies_original_report_freeze_asset_contract(self):
        from code_locbench_sfpruner_20261116 import report
        with fixture() as (parent,prior,_):
            plan=p.freeze_plan(parent,prior,parent/'continuation460')
            work=Path(plan['batches'][0]['work'])
            for name in ['runnable_manifest.json','allocation_status.json']:
                p.b.write(work/'runtime'/name,{})
            records=p.b.read(work/'allocation.json')['records']
            out=work/'controller/report_freeze.json'
            with patch.object(report,'PARQUET_SHA',p.original.PARQUET_SHA),\
                 patch.object(report,'OFFICIAL_SCORER_SHA',p.SCORER_SHA),\
                 patch.object(report,'source_files',return_value=[Path(p.__file__)]),\
                 patch.object(report,'check_public_inputs',return_value=(records,[],{})):
                frozen=report.freeze_inputs(work,out,draws=40)
            self.assertEqual(frozen['official_scorer_sha256'],p.SCORER_SHA)
            self.assertIn(str((work/p.SCORER_RELATIVE).resolve()),frozen['source_sha256'])
            self.assertFalse(frozen['models_called'])

    def test_membership_is_written_before_private_gold_projection(self):
        with fixture() as (parent,prior,_):
            original_read=p.b.read
            def checked(path):
                if Path(path).name in ('official_gold.private.json','base_inventory.private.json'):
                    self.assertTrue((parent/'continuation460/selection/membership_freeze.json').exists())
                return original_read(path)
            with patch.object(p.b,'read',side_effect=checked):
                p.freeze_plan(parent,prior,parent/'continuation460')

    def test_parent_and_pilot_changes_are_rejected(self):
        for which in ['parent','pilot']:
            with fixture() as (parent,prior,_):
                plan=p.freeze_plan(parent,prior,parent/'continuation460')
                target=(parent if which=='parent' else prior)/'allocation.json'
                target.write_text('{}')
                with self.assertRaisesRegex(ValueError,'allocation changed'):
                    p.check_batch(plan['batches'][0]['work'])

    def test_batch_source_or_plan_order_tampering_is_rejected(self):
        for which in ['source','order']:
            with fixture() as (parent,prior,_):
                plan=p.freeze_plan(parent,prior,parent/'continuation460')
                work=Path(plan['batches'][0]['work'])
                if which=='source':
                    (work/'selection/selection.json').write_text('{}')
                else:
                    plan['batches'][0]['instance_ids'].reverse()
                    p.b.write(parent/'continuation460/plan.json',plan,immutable=False)
                with self.assertRaises(ValueError):p.check_batch(work)

    def test_rehashing_a_changed_method_cannot_authorize_it(self):
        with fixture() as (parent,prior,_):
            plan=p.freeze_plan(parent,prior,parent/'continuation460')
            spec=plan['batches'][0];work=Path(spec['work']);target=work/'protocol.json'
            changed=p.b.read(target);changed['thinking']=True
            p.b.write(target,changed,immutable=False)
            spec['protocol_sha256']=p.b.sha(target)
            spec['files_sha256'][str(target)]=p.b.sha(target)
            p.b.write(parent/'continuation460/plan.json',plan,immutable=False)
            with self.assertRaisesRegex(ValueError,'method/filter'):
                p.validate_plan(parent/'continuation460')


class CacheTests(unittest.TestCase):
    def context(self,folder):
        root=Path(folder);parent=root/'parent';prior=parent/'pilot100';out=parent/'continuation460'
        work=out/'batch01';work.mkdir(parents=True)
        plan={'parent':str(parent),'pilot':str(prior),'batches':[{'index':1,'work':str(work)}]}
        row={'instance_id':'x__y-1','repo':'x/y','base_commit':'a'*40}
        return parent,work,plan,row,p.b.archive_key(row['repo'],row['base_commit'])

    def archive(self,directory,row,key,**changes):
        directory.mkdir(parents=True,exist_ok=True);body=directory/(key+'.tar.gz');body.write_bytes(b'synthetic archive bytes')
        receipt=dict(repo=row['repo'],base_commit=row['base_commit'],bytes=body.stat().st_size,
                     archive_sha256=p.b.sha(body));receipt.update(changes)
        p.b.write(directory/(key+'.receipt.json'),receipt)
        return body

    def test_verified_cache_copy_preserves_old_bytes_and_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,work,plan,row,key=self.context(folder);old=parent/'archive_cache'
            body=self.archive(old,row,key);original=body.read_bytes()
            events=[{'attempt':1,'status':'started','utc':1}, {'attempt':1,'status':'complete','utc':2}]
            (old/(key+'.attempts.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in events))
            proof=p.import_caches(work,plan,plan['batches'][0],[row])
            self.assertTrue(proof[0]['complete_cache_found'])
            self.assertEqual((work/'archive_cache'/body.name).read_bytes(),original)
            self.assertEqual(body.read_bytes(),original)
            self.assertNotEqual(body.stat().st_ino,(work/'archive_cache'/body.name).stat().st_ino)
            self.assertEqual(proof[0]['historical_lifetime_attempts_used'],1)

    def test_foreign_receipt_hash_or_URL_refused_before_network(self):
        for changes in [{'repo':'evil/repo'},{'archive_sha256':'0'*64},{'url':'https://evil.invalid/bytes'}]:
            with tempfile.TemporaryDirectory() as folder:
                parent,work,plan,row,key=self.context(folder)
                self.archive(parent/'archive_cache',row,key,**changes)
                with self.assertRaisesRegex(ValueError,'Foreign or corrupt'):
                    p.import_caches(work,plan,plan['batches'][0],[row])
                self.assertFalse((work/'archive_cache'/(key+'.receipt.json')).exists())

    def test_three_spent_attempts_not_reset_and_no_network_can_start(self):
        with tempfile.TemporaryDirectory() as folder:
            parent,work,plan,row,key=self.context(folder);old=parent/'archive_cache';old.mkdir(parents=True)
            events=[{'attempt':i,'status':'started','utc':i} for i in range(1,4)]
            (old/(key+'.attempts.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in events))
            partial=old/(key+'.part');partial.write_bytes(b'keep original interrupted bytes')
            proof=p.import_caches(work,plan,plan['batches'][0],[row])
            self.assertEqual(proof[0]['historical_lifetime_attempts_used'],3)
            self.assertEqual(partial.read_bytes(),b'keep original interrupted bytes')
            class NoRequests:
                def get(self,*a,**k):raise AssertionError('Exhausted budget must not request')
            with self.assertRaisesRegex(RuntimeError,'attempt limit exhausted'):
                p.b.download_archive(row,work/'archive_cache',session=NoRequests())

    def test_duplicate_ledgers_not_double_counted_distinct_starts_are_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a=root/'a';other=root/'b'
            event={'attempt':1,'status':'started','utc':1}
            a.write_text(json.dumps(event)+'\n');other.write_text(json.dumps(event)+'\n')
            events,used=p.merge_attempt_ledgers([a,other]);self.assertEqual(used,1);self.assertEqual(len(events),1)
            other.write_text(json.dumps(dict(event,utc=2))+'\n')
            events,used=p.merge_attempt_ledgers([a,other]);self.assertEqual(used,2)
            self.assertEqual(events[-1]['status'],'historical_lifetime_budget_floor')

    def test_malformed_or_symlink_ledger_is_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a=root/'a';a.write_text('{"attempt":1}')
            with self.assertRaisesRegex(ValueError,'malformed'):p.merge_attempt_ledgers([a])
            link=root/'link';link.symlink_to(a)
            with self.assertRaisesRegex(ValueError,'Symlink'):p.merge_attempt_ledgers([link])


class AdapterTests(unittest.TestCase):
    def test_original_algorithms_used_and_global_patches_restored(self):
        with fixture() as (parent,prior,_):
            plan=p.freeze_plan(parent,prior,parent/'continuation460');work=Path(plan['batches'][4]['work'])
            original_check,original_roster=p.runtime.check_work,p.runtime.roster
            events=[]
            def prewarm(candidate,**kwargs):
                self.assertEqual(p.runtime.check_work(candidate),work)
                self.assertEqual(len(p.runtime.roster(candidate)),60)
                self.assertEqual(kwargs,{'workers':4,'legacy':None});events.append('prewarm')
            def build(candidate,**kwargs):events.append('build');self.assertEqual(kwargs['workers'],4)
            def gate(candidate):events.append('gate');return {'status':'PASS','allocated':60}
            with patch.object(p,'import_caches'),patch.object(p.runtime,'prewarm',side_effect=prewarm),\
                 patch.object(p.runtime,'build',side_effect=build),patch.object(p.runtime,'gate',side_effect=gate):
                result=p.prepare_batch(work)
            self.assertEqual(events,['prewarm','build','gate']);self.assertEqual(result['allocated'],60)
            self.assertIs(p.runtime.check_work,original_check);self.assertIs(p.runtime.roster,original_roster)
            with p.original_runtime_for_batch(work):
                with self.assertRaisesRegex(ValueError,'Cross-batch'):
                    p.runtime.check_work(plan['batches'][0]['work'])

    def test_adapters_restore_on_failure_and_started_batch_cannot_prepare(self):
        with fixture() as (parent,prior,_):
            plan=p.freeze_plan(parent,prior,parent/'continuation460');work=Path(plan['batches'][0]['work'])
            before=p.runtime.check_work
            with self.assertRaises(RuntimeError):
                with p.original_runtime_for_batch(work):raise RuntimeError('synthetic')
            self.assertIs(p.runtime.check_work,before)
            marker=work/'paired_run/pairs/fixture/baseline/started.json';marker.parent.mkdir(parents=True);marker.write_text('{}')
            with self.assertRaisesRegex(ValueError,'started'):
                p.prepare_batch(work)
            with self.assertRaisesRegex(ValueError,'between1 and4'):
                p.prepare_batch(work,workers=5)


if __name__ == '__main__':
    unittest.main()
