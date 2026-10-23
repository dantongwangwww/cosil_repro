import copy
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from code_rebench_qwen import common as C
from code_rebench_qwen import runner
from code_rebench_qwen_repair import bootstrap as B
from code_rebench_qwen_repair import compat
from code_rebench_qwen_repair import controller as R


def leaf():
    return dict(classes=[dict(name='C',start_line=1,end_line=3,text=['class C:'],
        methods=[dict(name='m',start_line=2,end_line=3,text=[' def m(self): pass'])])],
        functions=[dict(name='f',start_line=5,end_line=5,text=['def f(): pass'])],
        text=['class C:', ' def m(self): pass', '', '', 'def f(): pass'])


class Extraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Imports the existing implementation only; never constructs a provider.
        runner._load_cosil()
        from afl.util import preprocess_data
        cls.module = preprocess_data
        cls.original = staticmethod(preprocess_data.extract_structure)

    def test_real_leaf_delegates_with_exact_original_values_and_order(self):
        tree = {'package': {'one.py': leaf(), 'two.py': leaf()}}
        expected = self.original(copy.deepcopy(tree), 'prefix')
        actual = compat.corrected(self.original)(copy.deepcopy(tree), 'prefix')
        self.assertEqual(actual, expected)
        self.assertEqual([x[0] for x in actual[0]],['prefix/package/one.py','prefix/package/two.py'])

    def test_directory_with_reserved_name_and_three_keys_is_not_a_leaf(self):
        tree = {'Nowcasting':{'__init__.py':leaf(),'data':{'m.py':leaf()},'functions':{'f.py':leaf()}}}
        with self.assertRaises(KeyError):
            self.original(copy.deepcopy(tree))
        actual = compat.corrected(self.original)(copy.deepcopy(tree))
        self.assertEqual([r[0] for r in actual[0]],[
            'Nowcasting/__init__.py','Nowcasting/data/m.py','Nowcasting/functions/f.py'])

    def test_all_three_reserved_directory_names_still_require_list_leaf_values(self):
        tree = {'x':{'classes':{'a.py':leaf()},'functions':{'b.py':leaf()},'text':{'c.py':leaf()}}}
        result = compat.corrected(self.original)(tree)
        self.assertEqual([x[0] for x in result[0]],['x/classes/a.py','x/functions/b.py','x/text/c.py'])

    def test_non_dictionary_entries_preserve_legacy_return_shape(self):
        tree = {'a':'sentinel','d':{'b':'sentinel'}}
        self.assertEqual(compat.corrected(self.original)(tree),self.original(copy.deepcopy(tree)))

    def test_actual_affected_base_structure_enumerates_every_indexed_file_without_model(self):
        job = C.read(C.INPUTS/compat.TARGET/'job.json')
        self.assertIsNotNone(job, 'Actual prepared base-only fixture must exist')
        structure = C.read(job['structure'])['structure']
        index = C.read(job['code_index'])
        with patch('code_rebench_qwen.local_provider.LocalProvider.ask',
                   side_effect=AssertionError('No model call is allowed')) as request:
            files,_,_ = compat.corrected(self.original)(structure)
        request.assert_not_called()
        self.assertEqual({p for p,_ in files},set(index))
        self.assertIn(compat.COLLISION+'/functions/__init__.py',{p for p,_ in files})

    def test_loaded_aliases_and_new_import_alias_restore_on_exception(self):
        fixture = ModuleType('code_v3b.__repair_fixture')
        fixture.__file__ = str(C.ROOT/'code_v3b/__repair_fixture.py')
        fixture.first = self.original
        fixture.second = self.original
        imported = ModuleType('afl.__repair_late_fixture')
        imported.__file__ = str(C.ROOT/'afl/__repair_late_fixture.py')
        fake_runner = SimpleNamespace(_load_cosil=lambda:('unchanged','loader'))
        old_loader, run_id = fake_runner._load_cosil,C.RUN_ID
        with patch.dict(sys.modules,{fixture.__name__:fixture,imported.__name__:imported}):
            with self.assertRaisesRegex(RuntimeError,'controlled failure'):
                with compat.loader_compatibility(fake_runner):
                    self.assertEqual(fake_runner._load_cosil(),('unchanged','loader'))
                    self.assertIsNot(fixture.first,self.original)
                    self.assertIs(fixture.first,fixture.second)
                    self.assertIs(self.module.extract_structure,fixture.first)
                    imported.reference = self.module.extract_structure
                    self.assertEqual(C.RUN_ID,compat.RUN_ID)
                    raise RuntimeError('controlled failure')
            self.assertIs(fixture.first,self.original)
            self.assertIs(fixture.second,self.original)
            self.assertIs(imported.reference,self.original)
        self.assertIs(self.module.extract_structure,self.original)
        self.assertIs(fake_runner._load_cosil,old_loader)
        self.assertEqual(C.RUN_ID,run_id)


class EligibilityAndIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cosil-repair-test-')
        self.root = Path(self.temp.name)
        self.patches = [patch.object(C,'WORK',self.root),patch.object(C,'RUN',self.root/'run'),
                        patch.object(C,'INPUTS',self.root/'inputs'),patch.object(C,'MODEL_DIR',self.root/'model')]
        for p in self.patches:p.start()
        self.job_path = C.INPUTS/compat.TARGET/'job.json'
        self.job = dict(instance_id=compat.TARGET,repo='statsmodels/statsmodels',base_commit='a'*40,
            problem_statement='synthetic isolation fixture',cohort=C.COHORT,
            snapshot=str(self.root/'snapshot'),paths=['m.py'],
            code_index=str(self.job_path.parent/'code_index.json'),
            structure=str(self.job_path.parent/'repo_structures'/f'{compat.TARGET}.json'))
        C.write(self.job_path,self.job)
        C.write(self.job['code_index'],{})
        C.write(self.job['structure'],{'structure':{}})
        Path(self.job['snapshot']).mkdir()
        C.MODEL_DIR.mkdir()
        (C.WORK/'token_cache').mkdir()
        self.scan = dict(collision_nodes=[dict(instance_id=compat.TARGET,path=compat.COLLISION)],
                         affected_issues=[compat.TARGET])
        self.old = dict(instance_id=compat.TARGET,status='failed',semantic_calls=0,http_attempts=0,
            error_type='KeyError',error="'text'",traceback='afl/util/preprocess_data.py extract_structure')
        self.old_case = C.RUN/'cases'/compat.TARGET

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_only_zero_call_exact_engineering_failure_is_eligible(self):
        R.qualify(self.scan,self.old,self.old_case)
        for changes in (dict(status='complete'),dict(semantic_calls=1),dict(http_attempts=1),
                        dict(error_type='ValueError'),dict(error='wrong'),dict(traceback='model error'),
                        dict(instance_id='other-1')):
            with self.subTest(changes=changes):
                with self.assertRaises(RuntimeError):R.qualify(self.scan,dict(self.old,**changes),self.old_case)

    def test_request_artifact_overrides_claimed_zero_usage(self):
        C.write(self.old_case/'calls/0001/request.json',{'model':'sentinel'})
        with self.assertRaisesRegex(RuntimeError,'contains model requests'):
            R.qualify(self.scan,self.old,self.old_case)

    def test_second_collision_or_no_collision_refuses_repair(self):
        for nodes in ([],self.scan['collision_nodes']*2):
            with self.assertRaises(RuntimeError):R.qualify(dict(self.scan,collision_nodes=nodes),self.old,self.old_case)

    def test_bwrap_reuses_original_isolation_plus_one_readonly_package(self):
        command = B.argv(self.job_path,B.case_output())
        mounts = [(command[i],command[i+1],command[i+2]) for i in range(len(command)-2)
                  if command[i] in ('--ro-bind','--bind')]
        package = str(C.ROOT/'code_rebench_qwen_repair')
        self.assertIn(('--ro-bind',package,package),mounts)
        self.assertEqual([(s,d) for kind,s,d in mounts if kind=='--bind'],[(str(B.case_output()),str(B.case_output()))])
        self.assertIn('code_rebench_qwen_repair.bootstrap',command)
        self.assertNotIn(str(C.RUN/'cases'),[s for _,s,_ in mounts])
        self.assertNotIn(str(C.FROZEN),[s for _,s,_ in mounts])
        self.assertNotIn(str(self.job_path.parent/'preparation_receipt.json'),[s for _,s,_ in mounts])

    def test_old_or_arbitrary_output_paths_are_refused(self):
        for out in (self.old_case,B.root(),B.root()/'cases/other',C.RUN/'isolation_probe'):
            with self.assertRaises(PermissionError):B.argv(self.job_path,out)

    def test_job_identity_and_canonical_path_are_enforced(self):
        other = C.INPUTS/'other.json'
        C.write(other,self.job)
        with self.assertRaises(PermissionError):B.argv(other,B.case_output())
        C.write(self.job_path,dict(self.job,instance_id='other-1'))
        with self.assertRaises(ValueError):B.argv(self.job_path,B.case_output())

    def test_symlink_cannot_redirect_repair_output_into_old_cases(self):
        self.old_case.mkdir(parents=True)
        B.root().mkdir(parents=True)
        (B.root()/'cases').symlink_to(C.RUN/'cases',target_is_directory=True)
        with self.assertRaises(PermissionError):B.argv(self.job_path,B.case_output())

    def test_probe_keeps_original_probe_flag_and_uses_separate_output(self):
        out = B.root()/'isolation_probe'
        command = B.argv(self.job_path,out,probe=True)
        self.assertEqual(command[-1],'--probe')
        self.assertEqual(command[command.index('--out')+1],str(out))

    def test_completed_repair_never_restarts_process_even_if_failed(self):
        C.write(B.case_output()/'result.json',dict(instance_id=compat.TARGET,status='failed'))
        C.write(B.root()/'plan.json',{'synthetic':'plan'})
        C.write(B.root()/'isolation_probe/repair_gate.json',dict(passed=True,plan_sha256=C.sha(B.root()/'plan.json')))
        with patch.object(R,'verify',return_value={'original_job':str(self.job_path)}),patch.object(R.subprocess,'run') as run:
            result = R.execute()
        self.assertEqual(result['status'],'failed');run.assert_not_called()

    def test_interrupted_repair_is_not_silently_replayed(self):
        C.write(B.case_output()/'repair_provenance.json',{'synthetic':'started'})
        C.write(B.root()/'plan.json',{'synthetic':'plan'})
        C.write(B.root()/'isolation_probe/repair_gate.json',dict(passed=True,plan_sha256=C.sha(B.root()/'plan.json')))
        with patch.object(R,'verify',return_value={'original_job':str(self.job_path)}),patch.object(R.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'Interrupted repair'):R.execute()
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
