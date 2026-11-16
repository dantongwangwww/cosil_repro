"""Synthetic CPU tests for whole-roster preservation and archive-key concurrency."""
import json
import hashlib
import io
import multiprocessing
from pathlib import Path
import tempfile
import tarfile
import unittest
from concurrent.futures import ProcessPoolExecutor

from . import runtime as r


class ArchiveTests(unittest.TestCase):
    def test_four_distinct_issues_same_base_are_downloaded_once(self):
        rows = [{'instance_id': 'x__y-' + str(i), 'repo': 'x/y', 'base_commit': 'a'*40} for i in range(4)]
        unique = r.unique_archives(rows)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(unique), 1)
        self.assertEqual(next(iter(unique.values()))['instance_id'], rows[0]['instance_id'])

    def test_historical_cache_copy_is_verified_and_not_hardlinked(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder)/'old', Path(folder)/'new'; old.mkdir(); new.mkdir()
            row = {'repo': 'x/y', 'base_commit': 'a'*40}; key = r.b.archive_key(**{'repo':row['repo'], 'base':row['base_commit']})
            body = old/(key+'.tar.gz'); body.write_bytes(b'complete synthetic archive')
            receipt = dict(row, archive_sha256=r.b.sha(body), bytes=body.stat().st_size)
            (old/(key+'.receipt.json')).write_text(json.dumps(receipt))
            old_bytes = body.read_bytes()
            copied = r.copy_verified_archive(row, old, new)
            self.assertEqual(copied['archive_sha256'], r.b.sha(body))
            self.assertNotEqual(body.stat().st_ino, (new/body.name).stat().st_ino)
            (new/body.name).write_bytes(b'changed new cache')
            self.assertEqual(body.read_bytes(), old_bytes)

    def test_bad_historical_hash_is_not_imported(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder)/'old', Path(folder)/'new'; old.mkdir(); new.mkdir()
            row = {'repo': 'x/y', 'base_commit': 'a'*40}; key = r.b.archive_key(row['repo'],row['base_commit'])
            (old/(key+'.tar.gz')).write_bytes(b'wrong')
            (old/(key+'.receipt.json')).write_text(json.dumps(dict(row,archive_sha256='0'*64,bytes=5)))
            with self.assertRaisesRegex(ValueError, 'identity/hash'):
                r.copy_verified_archive(row, old, new)
            self.assertFalse(list(new.iterdir()))


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'instance_id': 'r__repo-'+str(i), 'repo': 'r/repo', 'base_commit': 'a'*40} for i in range(560)]
        self.alloc = {'records': self.rows}
        self.source = {'records': [{'instance_id': x['instance_id'], 'status': 'RUNTIME_PREPARATION_BLOCKED',
                     'runtime_preparation_blocked': True, 'runtime_preparation_errors': {'x.py': 'HTTP404'}} for x in self.rows]}

    def test_repeated_repos_and_preparation_failures_preserve560(self):
        selected = {'records': self.rows[:1]}
        rows = r.allocation_ledger(self.alloc, selected, self.source, self.rows[:1], {})
        self.assertEqual(len(rows),560)
        self.assertEqual(sum(x['runnable'] for x in rows),1)
        self.assertTrue(all(x['status']=='PREPARATION_BLOCKED' for x in rows[1:]))

    def test_missing_build_result_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError, 'explicit builder failure'):
            r.allocation_ledger(self.alloc, {'records': self.rows[:1]}, self.source, [], {})

    def test_missing_selection_without_failure_evidence_is_not_blocked(self):
        self.source['records'][0]['status']='SOURCE_PROOF_READY'
        self.source['records'][0]['runtime_preparation_blocked']=False
        with self.assertRaisesRegex(ValueError, 'explicit preparation-blocked'):
            r.allocation_ledger(self.alloc, {'records': []}, self.source, [], {})

    def test_explicit_builder_failure_retains_its_issue(self):
        iid=self.rows[0]['instance_id']
        rows=r.allocation_ledger(self.alloc, {'records': self.rows[:1]},self.source,[],{iid:{'type':'SourceError'}})
        self.assertEqual(len(rows),560)
        self.assertEqual(rows[0]['errors']['type'],'SourceError')
        self.assertEqual(rows[0]['stage'],'runtime_builder')


class ProcessGenerationTests(unittest.TestCase):
    def test_old_success_receipt_is_byte_preserved_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);runtime=base/'runtime';source_file=runtime/'tasks/x/m.py'
            source_file.parent.mkdir(parents=True);source_file.write_text('def f():\n    return 1\n')
            record={'instance_id':'fixture__repo-1','repo':'fixture/repo','base_commit':'a'*40};row={'instance_id':record['instance_id']}
            receipt={'binding':r.case_binding(record,row),'runtime_files_sha256':{'tasks/x/m.py':r.b.sha(source_file)},'record':record}
            old=base/'old.json';old.write_text(json.dumps(receipt));original=old.read_bytes()
            new=base/'new/case.json';proof=r.import_completed_case(old,new,runtime,record,row)
            self.assertEqual(old.read_bytes(),original);self.assertEqual(new.read_bytes(),original)
            self.assertFalse(proof['original_receipt_modified'])
            source_file.write_text('modified')
            with self.assertRaisesRegex(ValueError,'runtime bytes changed'):
                r.import_completed_case(old,base/'changed.json',runtime,record,row)

    def test_interrupted_stable_task_is_preserved_without_fake_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);task=root/'runtime/tasks/fixture__repo-1';task.mkdir(parents=True)
            (task/'job.json').write_text('{"unfinished":true}')
            proof=r.preserve_orphan_task(task,root/'generation')
            self.assertFalse(task.exists())
            self.assertEqual((Path(proof['preserved_path'])/'job.json').read_text(),'{"unfinished":true}')
            self.assertFalse(proof['deleted']);self.assertFalse(proof['synthetic_completion_receipt_created'])
            self.assertFalse((root/'generation/cases').exists())

    def test_process_builder_cannot_start_cold_network(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'cold network'):
                r.cached_archive_only({'repo':'fixture/repo','base_commit':'a'*40},folder)

    def test_real_spawn_runs_original_builder_for_two_distinct_same_base_issues(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cache=root/'cache';cache.mkdir();raw=b'def f():\n    return 1\n'
            key=r.b.archive_key('fixture/repo','a'*40);archive=cache/(key+'.tar.gz')
            with tarfile.open(archive,'w:gz') as tf:
                member=tarfile.TarInfo('fixture-root/m.py');member.size=len(raw);tf.addfile(member,io.BytesIO(raw))
            r.b.write(cache/(key+'.receipt.json'),{'repo':'fixture/repo','base_commit':'a'*40,
                      'archive_sha256':r.b.sha(archive),'bytes':archive.stat().st_size})
            payloads=[]
            for i in range(2):
                iid='fixture__repo-'+str(i)
                record={'instance_id':iid,'repo':'fixture/repo','base_commit':'a'*40,
                        'source_id':'locbench_v1_c44cf3b7','source':'czlll/Loc-Bench_V1',
                        'source_revision':'c44cf3b74e07ca642cec841b471a9939907c12a7','source_sha256':r.DATA_SHA}
                row={k:record[k] for k in ('instance_id','repo','base_commit','source_id','source_revision','source_sha256')}
                row.update(problem_statement='Synthetic CPU index fixture only.',base_files_sha256={'m.py':hashlib.sha256(raw).hexdigest()})
                payloads.append((record,row,str(root/'runtime'),str(root/'generation/cases'),str(cache)))
            with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
                records=list(pool.map(r.build_one_spawn,payloads))
            self.assertEqual(len(records),2)
            self.assertEqual({x['instance_id'] for x in records},{'fixture__repo-0','fixture__repo-1'})
            for record in records:
                self.assertEqual((root/'runtime/tasks'/record['instance_id']/'snapshot/m.py').read_bytes(),raw)
                self.assertTrue((root/'generation/cases'/(record['instance_id']+'.json')).is_file())


if __name__ == '__main__':
    unittest.main()
