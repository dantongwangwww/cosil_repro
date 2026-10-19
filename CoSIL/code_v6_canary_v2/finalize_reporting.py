"""Verify an explicit post-execution report-only revision without editing its freeze."""
from pathlib import Path
from .common import *


def verify_report_revision():
    state=read(OUT/'status.json')
    if state['stage'] not in {'complete','stop_loss','failed'} or not state.get('ended_at'):
        raise RuntimeError('Reporting repair must wait for inference to end')
    if not read(OUT/'service_shutdown.json')['closed']:
        raise RuntimeError('Owned Qwen service must be closed before reporting revision')
    if not (OUT/'process_exit.json').exists():raise RuntimeError('Original controller is still running')
    revision=read(OUT/'report_only_revision.json');f=read(OUT/'freeze.json')
    assert revision['original_freeze_sha256']==sha(OUT/'freeze.json')
    expected_path=str(ROOT/'code_v6_canary_v2/report.py')
    assert set(revision['changed_preexisting_code'])=={expected_path}
    overrides={}
    for path,evidence in revision['changed_preexisting_code'].items():
        assert evidence['as_run_sha256']==f['source_sha256'][path]
        assert sha(evidence['as_run_archive'])==evidence['as_run_sha256']
        assert sha(path)==evidence['reporting_only_sha256']
        overrides[path]=evidence['reporting_only_sha256']
    for path,expected in revision['new_reporting_code_sha256'].items():
        assert Path(path).parent==ROOT/'code_v6_canary_v2'
        assert sha(path)==expected
    verify_files({**f['source_sha256'],**overrides});verify_files(f['protected_sha256'])
    assert test_stats()==f['test_stat_only']
    status(OUT/'reporting_revision_verification.json',{
        'time':now(),'as_run_freeze_preserved':True,'original_freeze_sha256':sha(OUT/'freeze.json'),
        'changed_preexisting_code':[expected_path],'inference_and_stop_loss_code_unchanged':True,
        'model_data_thresholds_predictions_and_history_verified':True,'test_stat_only':test_stats(),
        'report_repair_pre_change_commit':revision['pre_change_github_commit'],
        'new_reporting_code_sha256':revision['new_reporting_code_sha256']})
    return f


def run():
    verify_report_revision()
    from .report import run as report
    return report(verification=verify_report_revision)


if __name__=='__main__':run()
