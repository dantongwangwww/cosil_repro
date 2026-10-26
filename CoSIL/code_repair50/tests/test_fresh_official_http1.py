"""Pure synthetic fresh-DATA policy and frozen v2 reader tests."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from code_repair50 import image_transport as T
from code_repair50 import fresh_official_http1 as F
from code_repair50.tests import test_image_transport as fixtures


class FreshOfficialTests(fixtures.ImageTransportTests):
    @contextmanager
    def fresh_fixture(self, *, active=True, data_disk=True, absent=False):
        _, _, target = self.initial_cache_fixture()
        with patch.object(T, "TRANSPORT_ROOT", self.root), patch.object(T.shutil, "disk_usage", return_value=Mock(free=2 ** 50)):
            if data_disk:target = self.select_empty_fixture_on_data(target)
            if active:F.activate_run_fresh_official_http1_policy()
            complete = self.archive().read_bytes(); raw = json.dumps(self.manifest, separators=(",", ":")).encode()
            client = Mock(); client.images.get.return_value.attrs = {"Id": self.config_digest,
                "RootFS": {"Type": "layers", "Layers": self.diff_ids}, "Os": "linux", "Architecture": "amd64"}
            local_load = self.fake_local_image_load(client, [False]) if absent else None
            def pull(command, **kwargs):
                if command[0] == "docker":
                    self.assertIsNotNone(local_load); return local_load(command, **kwargs)
                self.assertEqual(command[:4], ["/pinned-crane", "--platform", "linux/amd64", "pull"])
                self.assertEqual(command[4], self.record["image_reference"])
                self.assertEqual(kwargs["env"]["HTTPS_PROXY"], "http://approved.invalid")
                self.assertEqual(kwargs["env"]["SSL_CERT_FILE"], "/synthetic/approved-ca")
                if active and data_disk:self.assertEqual(kwargs["env"]["GODEBUG"], "http2client=0")
                else:self.assertNotIn("GODEBUG", kwargs["env"])
                self.assertNotIn("NO_PROXY", kwargs["env"]); self.assertNotIn("DEEPSEEK_API_KEY", kwargs["env"])
                cache = Path(command[command.index("--cache_path") + 1])
                for layer, body in zip(self.manifest["layers"], self.layers):self.assertEqual((cache / layer["digest"]).read_bytes(), body)
                Path(command[5]).write_bytes(complete)
                return Mock(returncode=0, poll=Mock(return_value=0))
            with patch.dict(os.environ, {"HTTPS_PROXY": "http://approved.invalid", "SSL_CERT_FILE": "/synthetic/approved-ca",
                    "NO_PROXY": "should.not.bypass", "DEEPSEEK_API_KEY": "dummy-key"}, clear=True), \
                    patch.object(T, "verified_binary", return_value=Path("/pinned-crane")), \
                    patch.object(T.subprocess, "run", return_value=Mock(returncode=0, stdout=raw + b"\n", stderr=b"")) as probe, \
                    patch.object(T.subprocess, "Popen", side_effect=pull) as process:
                yield target, client, probe, process

    def test_fresh_default_inactive_keeps_original_official_auto(self):
        with self.fresh_fixture(active=False) as (target, client, probe, pull):
            self.assertIsNone(F.fresh_case(self.record, target))
            T.ensure_verified_image(client, self.record, workdir=target)
            self.assertNotIn("GODEBUG", pull.call_args.kwargs["env"])
            self.assertFalse((target / "initial_cache/transport_request.json").exists())
            self.assertFalse(F.policy_path().exists())

    def test_fresh_activation_is_fixed_private_and_once(self):
        with self.fresh_fixture() as (target, _, _, _):
            p = F.policy_path(); before = p.read_bytes(), p.stat().st_mtime_ns
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(p.read_text())["storage_root"], str(T.DATA_TRANSPORT_ROOT.absolute()))
            self.assertEqual(json.loads(p.read_text())["timeout_seconds"], 1800)
            with self.assertRaises(FileExistsError):F.activate_run_fresh_official_http1_policy()
            self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), before)

    def test_fresh_activation_refuses_competing_active_dom_policy(self):
        with self.fresh_fixture(active=False):
            T.activate_run_fresh_http1_policy()
            with self.assertRaises(T.ImageTransportError):F.activate_run_fresh_official_http1_policy()
            self.assertFalse(F.policy_path().exists())

    def test_fresh_data_only_never_selects_existing_legacy_scope(self):
        with self.fresh_fixture(data_disk=False) as (target, _, _, _):
            before = {str(p):(p.read_bytes(), p.stat().st_mtime_ns) for p in target.rglob('*') if p.is_file()}
            self.assertIsNone(F.fresh_case(self.record, target))
            self.assertEqual(before, {str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in target.rglob('*') if p.is_file()})

    def test_fresh_started_scope_markers_never_acquire_policy(self):
        with self.fresh_fixture() as (target, _, probe, pull):
            T._save(target / "registry_manifest_receipt.json", self.record)
            self.assertIsNotNone(F.fresh_case(self.record, target))
            for name in ("official_image.tar", "initial_cache", "initial_layer_cache", "probe", "download", "transport_retry_1", "unknown_empty"):
                p = target / name; p.touch(); snapshot = p.read_bytes(), p.stat().st_mtime_ns
                with self.subTest(name=name):
                    self.assertIsNone(F.fresh_case(self.record, target)); self.assertEqual((p.read_bytes(),p.stat().st_mtime_ns),snapshot)
                p.unlink()
            probe.assert_not_called(); pull.assert_not_called()

    def test_fresh_policy_unknown_body_or_permissions_rejected(self):
        with self.fresh_fixture() as (target, _, probe, pull):
            p=F.policy_path(); raw=p.read_bytes()
            p.write_bytes(raw+b'\n')
            with self.assertRaises(T.ImageTransportError):F.fresh_case(self.record,target)
            p.write_bytes(raw);p.chmod(0o644)
            with self.assertRaises(T.ImageTransportError):F.fresh_case(self.record,target)
            probe.assert_not_called();pull.assert_not_called()

    def test_fresh_policy_symlink_rejected(self):
        with self.fresh_fixture() as (target, _, _, _):
            p=F.policy_path();other=p.with_name('preserved-policy');p.rename(other);p.symlink_to(other)
            with self.assertRaises(T.ImageTransportError):F.fresh_case(self.record,target)

    def test_fresh_scope_child_symlink_rejected(self):
        with self.fresh_fixture() as (target, _, _, _):
            (target/'registry_manifest_receipt.json').symlink_to(self.root/'image.tar')
            with self.assertRaises(T.ImageTransportError):F.fresh_case(self.record,target)

    def test_fresh_success_freezes_v2_and_uses_canonical_official_h1(self):
        with self.fresh_fixture() as (target, client, probe, pull):
            T._save(target/'registry_manifest_receipt.json',self.record)
            reg_before=(target/'registry_manifest_receipt.json').read_bytes(),(target/'registry_manifest_receipt.json').stat().st_mtime_ns
            with patch.object(T,'seed_verified_partial_cache') as partial:
                result=T.ensure_verified_image(client,self.record,workdir=target)
            partial.assert_not_called();self.assertTrue(result['loaded_image_verified'])
            self.assertEqual((target/'registry_manifest_receipt.json').read_bytes(),reg_before[0]);self.assertEqual((target/'registry_manifest_receipt.json').stat().st_mtime_ns,reg_before[1])
            request=json.loads((target/'initial_cache/transport_request.json').read_text())
            cleanup=json.loads((target/'initial_cache/cleanup_receipt.json').read_text())
            self.assertEqual(request['schema'],F.REQUEST_SCHEMA);self.assertEqual(request['transport_reference'],self.record['image_reference'])
            self.assertEqual(request['placement_snapshot'],F.O._placement(self.record,target))
            self.assertEqual(request['policy']['timeout_seconds'],1800);self.assertEqual(request['policy']['max_transport_attempts'],1)
            self.assertEqual(cleanup['transport_request_sha256'],'sha256:'+hashlib.sha256((target/'initial_cache/transport_request.json').read_bytes()).hexdigest())
            self.assertTrue(cleanup['initial_evidence']);self.assertFalse((target/'initial_layer_cache').exists())
            self.assertEqual(probe.call_count,1);self.assertEqual(pull.call_count,1)
            self.assertEqual(probe.call_args.kwargs['env']['GODEBUG'],'http2client=0')
            self.assertFalse((target/'domestic_mirror_attempt_1').exists());self.assertFalse((target/'official_http1_attempt_1').exists())

    def test_fresh_success_without_shared_donors_still_uses_full_verification(self):
        with self.fresh_fixture() as (target,client,_,pull):
            discovery=T.discover_initial_cache_sources(self.record,target);discovery['selected_receipts']=[]
            complete=self.archive().read_bytes()
            def no_seed(command,**kwargs):
                cache=Path(command[command.index('--cache_path')+1]);self.assertEqual(list(cache.iterdir()),[])
                Path(command[5]).write_bytes(complete);return Mock(returncode=0,poll=Mock(return_value=0))
            pull.side_effect=no_seed
            with patch.object(T,'discover_initial_cache_sources',return_value=discovery):
                result=T.ensure_verified_image(client,self.record,workdir=target)
            self.assertTrue(result['compressed_layers_verified']);self.assertTrue(result['uncompressed_layers_verified'])
            F.validate_initial_transport_state(self.record,target)

    def test_fresh_actual_new_load_has_true_ownership_and_actual_u_capacity(self):
        with self.fresh_fixture(absent=True) as (target,client,_,pull):
            result=T.ensure_verified_image(client,self.record,workdir=target)
            for flag in ('new_to_daemon','loaded_by_this_run','load_performed_in_this_call'):self.assertTrue(result[flag])
            cap=json.loads(Path(result['storage_load_capacity_receipt_path']).read_text())
            self.assertTrue(cap['allowed']);self.assertEqual(cap['actual_verified_uncompressed_bytes'],44)
            self.assertEqual(pull.call_count,2)

    def test_fresh_retired_policy_keeps_cached_reload_cached_offline(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            F.policy_path().rename(F.policy_path().with_suffix('.retired'))
            before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in target.rglob('*') if p.is_file()}
            with patch.object(F,'_read_policy',side_effect=AssertionError('cached must use frozen request')),patch.object(T,'download_archive') as network,patch.object(T.subprocess,'run') as probe,patch.object(T.subprocess,'Popen') as process:
                cached=T.ensure_verified_image(client,self.record,workdir=target)
            network.assert_not_called();probe.assert_not_called();process.assert_not_called()
            for flag in ('new_to_daemon','loaded_by_this_run','load_performed_in_this_call'):self.assertFalse(cached[flag])
            with patch.object(F,'_read_policy',side_effect=AssertionError('reload must use frozen request')),patch.object(T.subprocess,'Popen',side_effect=self.fake_local_image_load(client,[False])) as process,patch.object(T,'download_archive') as network,patch.object(T.subprocess,'run') as probe:
                reloaded=T.ensure_verified_image(client,self.record,workdir=target)
                cached=T.ensure_verified_image(client,self.record,workdir=target)
            process.assert_called_once();network.assert_not_called();probe.assert_not_called()
            for flag in ('new_to_daemon','loaded_by_this_run','load_performed_in_this_call'):
                self.assertTrue(reloaded[flag]);self.assertFalse(cached[flag])
            for path,snapshot in before.items():self.assertEqual((Path(path).read_bytes(),Path(path).stat().st_mtime_ns),snapshot)

    def test_fresh_failed_initial_is_once_without_any_automatic_fallback(self):
        with self.fresh_fixture() as (target,client,probe,pull):
            def failed(command,**kwargs):
                Path(command[5]).write_bytes(b'new initial HTTP1 prefix')
                kwargs['stdout'].write(self.native_unexpected_eof_line(Path(command[5])))
                return Mock(returncode=1,poll=Mock(return_value=1))
            pull.side_effect=failed
            with patch.object(T,'recover_verified_partial_image') as recover,patch.object(T,'automatic_eof_recovery_eligibility') as automatic:
                with self.assertRaises(T.CraneDownloadError):T.ensure_verified_image(client,self.record,workdir=target)
                with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)
            recover.assert_not_called();automatic.assert_not_called();self.assertEqual(pull.call_count,1)
            self.assertTrue((target/'initial_cache/failure_receipt.json').exists());self.assertFalse((target/'automatic_eof_recovery_eligibility.json').exists())
            self.assertTrue((target/'initial_layer_cache').exists())

    def test_fresh_disk_gate_precedes_seed_probe_and_pull(self):
        with self.fresh_fixture() as (target,client,probe,pull):
            with patch.object(T.shutil,'disk_usage',return_value=Mock(free=0)),patch.object(T,'seed_full_verified_archive_cache') as seed:
                with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)
            seed.assert_not_called();probe.assert_not_called();pull.assert_not_called()

    def test_fresh_original_1800_gate_stops_only_own_download(self):
        with self.fresh_fixture() as (target,client,_,_):
            child=Mock(returncode=None,poll=Mock(return_value=None));ticks=iter(range(0,100000,1801))
            with patch.object(T.subprocess,'Popen',return_value=child),patch.object(T.time,'monotonic',side_effect=lambda:next(ticks)):
                with self.assertRaisesRegex(T.ImageTransportError,'timeout or disk-reserve'):
                    T.ensure_verified_image(client,self.record,workdir=target)
            child.terminate.assert_called_once();child.wait.assert_called_once_with(timeout=15)

    def test_fresh_request_tampering_or_unknown_schema_stops_without_network(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            p=target/'initial_cache/transport_request.json';raw=p.read_bytes();mtime=p.stat().st_mtime_ns
            for key,value in (('schema','UNKNOWN'),('source_reference','swerebench/other@'+self.record['digest']),('transport_reference','other.invalid/source'),('policy',{})):
                changed=json.loads(raw);changed[key]=value;p.write_text(json.dumps(changed))
                with self.subTest(key=key),patch.object(T,'download_archive') as network,self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)
                network.assert_not_called();p.write_bytes(raw);os.utime(p,ns=(p.stat().st_atime_ns,mtime))

    def test_fresh_external_placement_tampering_stops_without_network(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            p=T._placement_path(target.name);p.write_bytes(p.read_bytes()+b'\n')
            with patch.object(T,'download_archive') as network,self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)
            network.assert_not_called()

    def test_fresh_cleanup_request_sha_tampering_stops_without_network(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            p=target/'initial_cache/cleanup_receipt.json';data=json.loads(p.read_text());data['transport_request_sha256']='sha256:'+'0'*64;p.write_text(json.dumps(data))
            with patch.object(T,'download_archive') as network,self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)
            network.assert_not_called()

    def test_fresh_probe_or_completion_metadata_tampering_stops(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            p=target/'probe/manifest.raw';p.write_bytes(p.read_bytes()+b'changed')
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)

    def test_fresh_donor_archive_tampering_stops_cached_reader(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            de=json.loads((target/'initial_cache/donor_evidence.json').read_text());source=Path(de['evidence'][-1]['path']);source.write_bytes(source.read_bytes()+b'changed')
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)

    def test_fresh_corrupt_tar_and_wrong_actual_diffids_stop(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            p=target/'official_image.tar';p.write_bytes(p.read_bytes()+b'changed')
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)

    def test_fresh_actual_wrong_daemon_diffids_stop(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            client.images.get.return_value.attrs['RootFS']['Layers']=['sha256:'+'f'*64]
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)

    def test_fresh_unknown_daemon_error_is_not_treated_as_missing_image(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            error=RuntimeError('daemon unavailable');client.images.get.side_effect=error
            with patch.object(T.subprocess,'Popen') as process,self.assertRaises(RuntimeError) as caught:T.ensure_verified_image(client,self.record,workdir=target)
            self.assertIs(caught.exception,error);process.assert_not_called()

    def test_fresh_unknown_completed_state_artifact_is_rejected(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            (target/'initial_cache/unknown_extra.json').write_text('{}')
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client,self.record,workdir=target)

    def test_fresh_unknown_active_policy_is_not_consulted_for_started_scope(self):
        with self.fresh_fixture() as (target,client,_,_):
            T.ensure_verified_image(client,self.record,workdir=target)
            F.policy_path().write_text('{"unknown":"future policy"}')
            with patch.object(T.subprocess,'Popen',side_effect=self.fake_local_image_load(client,[False])) as process,patch.object(T,'download_archive') as network:
                result=T.ensure_verified_image(client,self.record,workdir=target)
            process.assert_called_once();network.assert_not_called();self.assertTrue(result['load_performed_in_this_call'])

    def test_fresh_selector_is_strict_and_mutually_exclusive(self):
        for args in ({'_fresh_official_http1':1},{'_fresh_official_http1':True,'_fresh_domestic_http1':True}):
            with self.subTest(args=args),self.assertRaises(T.ImageTransportError):
                T.first_download_with_private_cache(self.record,self.root/'none.tar',self.root/'none',workdir=self.root,**args)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(FreshOfficialTests(name) for name in
        loader.getTestCaseNames(FreshOfficialTests) if name in FreshOfficialTests.__dict__ and name.startswith('test_fresh_'))
