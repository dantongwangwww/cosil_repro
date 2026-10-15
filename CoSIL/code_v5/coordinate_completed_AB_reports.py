"""Persistent CPU-only coordinator for real completed A/B reporting.

Never trains, loads a model, decodes learned-judge test, changes frozen training
code, or overwrites historical reports. Verified expansion remains unexecuted.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import traceback

from code_v5.metrics import evaluate_predictions

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'
A_DATA = BASE / 'data_v3_noise_disclosed'
B_DATA = BASE / 'data_v3_runtime_filtered_reviewed'
A_TRAIN = BASE / 'A_v3_noise_disclosed_training_exploratory'
A_R8 = BASE / 'A_rank8_dropout01_exploratory'
B_RUN = BASE / 'B_runtime_reviewed_regularized_exploratory'
COMPARISON = BASE / 'A_post_vs_B_runtime_comparison_exploratory'
COMPARISON_DOC = ROOT / 'docs/v5-pruner/实验报告_v5_A-B_噪声披露与覆盖过滤对照.md'
DECISIONS = {
    'A_original': BASE / 'A_v3_noise_disclosed_authorization_v2_exploratory/root_exploratory_decision.json',
    'A_r8': BASE / 'A_regularized_authorization_exploratory/root_exploratory_decision.json',
    'B': BASE / 'B_runtime_filtered_regularized_authorization_exploratory/root_exploratory_decision.json'}
REPORT_TOOLS = ('code_v5/compare_noise_runtime.py', 'code_v5/report_gold_routes.py',
                'code_v5/build_v5_ab_overview.py', 'code_v5/plot_validation_curves.py',
                'code_v5/metrics.py', 'code_v5/race_and_calibrate.py', 'code_v5/run_pipeline.py')


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def guard(path):
    path = Path(path)
    if path.name.startswith('pruner_test') and path.suffix == '.jsonl':
        raise PermissionError('Coordinator refuses the sealed test JSON decoder')
    return path


def read(path):
    return json.loads(guard(path).read_text())


def rows(path):
    path = guard(path)
    if re.search(r'(?:^|[/_.-])test(?:$|[/_.-])', str(path.resolve()).lower()):
        raise PermissionError('Coordinator prediction/data row reader refuses test paths')
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def new_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')


def state(work, stage, **fields):
    value = {'at': now(), 'stage': stage, 'model_loaded': False, 'new_model_calls': 0,
             'GPU_claimed': False, 'pruner_test_decoded': False, **fields}
    tmp = work / 'status.tmp'
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(work / 'status.json')
    with (work / 'journal.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n'); stream.flush(); os.fsync(stream.fileno())


def assert_adapter(adapter, manifest):
    for a, b in (('r', 'rank'), ('lora_alpha', 'alpha'), ('lora_dropout', 'dropout')):
        if adapter.get(a) != manifest[b]: raise ValueError('Actual adapter differs from saved training manifest: ' + a)
    if set(adapter.get('target_modules', [])) != {'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'}:
        raise ValueError('Unexpected saved linear LoRA target modules')


def validate_run(run, data, *, kind, rank, dropout):
    mp = run / 'training_manifest.json'; sp = run / 'training_summary.json'
    manifest, summary = read(mp), read(sp)
    expected = {'kind': kind, 'rank': rank, 'alpha': 32, 'dropout': dropout, 'learning_rate': 5e-5,
                'epochs': 3, 'effective_batch': 8, 'micro_batch': 2, 'cutoff': 4096,
                'gradient_checkpointing': True, 'only_lora_trainable': True, 'physical_gpu': 2}
    if any(manifest.get(k) != v for k, v in expected.items()): raise ValueError('Real run configuration differs: ' + str(run))
    if summary.get('test_opened') is not False or summary.get('track') != 'exploratory': raise ValueError('Completed exploratory summary required')
    if manifest['data']['test_labels_read'] is not False: raise ValueError('Training manifest reports test access')
    for field, name in (('statistics_sha256', 'statistics.json'), ('seal_sha256', 'test_file_seal.json'), ('split_manifest_sha256', 'split_manifest.json')):
        if manifest['data'][field] != sha(data / name): raise ValueError('Training data provenance differs from frozen version')
    for path, digest in manifest['code_sha256'].items():
        source = ROOT / (path if path.startswith('code_v5') else 'code_v5/' + path)
        if sha(source) != digest: raise ValueError('Trainer code changed')
    curves_path = run / 'training_curves.json'; curves = read(curves_path)
    if [c['epoch'] for c in curves] != list(range(1, summary['epochs_completed'] + 1)):
        raise ValueError('Missing real completed epochs')
    files = {str(p): sha(p) for p in (mp, sp, curves_path)}
    best = summary['checkpoint_assessments']['best']
    if Path(best['checkpoint']).resolve() != Path(summary['best']).resolve(): raise ValueError('Actual best checkpoint differs from assessment')
    if rank == 8:
        peak = max(curves, key=lambda c: (c['val']['overall']['accuracy'], c['val']['overall']['auc'], c['val']['E_correct_rejection_rate'], -c['epoch']))
        if best['epoch'] != peak['epoch']: raise ValueError('Reranker prescribed completed-epoch val peak not selected')
    measured = {}
    for role in ('best', 'last'):
        assessment = summary['checkpoint_assessments'][role]
        cp = Path(assessment['checkpoint']).resolve()
        if cp.parent != run.resolve() or cp.name != f"epoch_{assessment['epoch']}": raise ValueError('Checkpoint identity/path drift')
        complete_path = cp / 'checkpoint_complete.json'; complete = read(complete_path)
        if complete['epoch'] != assessment['epoch'] or complete['manifest_sha256'] != sha(mp): raise ValueError('Unfinished/unbound checkpoint')
        for field, name in (('adapter_sha256', 'adapter_model.safetensors'), ('training_state_sha256', 'training_state.pt'), ('judge_metadata_sha256', 'judge_metadata.json')):
            if sha(cp / name) != complete[field]: raise ValueError('Checkpoint binary artifact changed')
            files[str(cp / name)] = complete[field]
        adapter_path = cp / 'adapter_config.json'; adapter = read(adapter_path); assert_adapter(adapter, manifest)
        metadata = read(cp / 'judge_metadata.json')
        if metadata['training_manifest_sha256'] != sha(mp) or metadata['kind'] != kind: raise ValueError('Judge metadata drift')
        files[str(adapter_path)] = sha(adapter_path); files[str(complete_path)] = sha(complete_path)
        trainp = Path(assessment['train_prediction_path'])
        if trainp.resolve() != (run / f"train_epoch_{assessment['epoch']}.jsonl").resolve(): raise ValueError('Unexpected train assessment path')
        if sha(trainp) != assessment['train_prediction_sha256']: raise ValueError('Actual train assessment SHA differs')
        train_rows = rows(trainp); train_truth = rows(data / 'pruner_train.jsonl')
        tp = {(r['instance_id'], r['function_id']): r for r in train_rows}
        truth = {(r['instance_id'], r['function_id']): r for r in train_truth}
        if len(tp) != len(train_rows) or tp.keys() != truth.keys() or any(tp[k]['label'] != truth[k]['label'] for k in truth):
            raise ValueError('Actual train assessment differs from frozen train pairs/labels')
        train_metrics = evaluate_predictions(train_rows)
        if train_metrics != assessment['train']: raise ValueError('Stored train metrics do not reproduce actual probabilities')
        valp = run / f"val_epoch_{assessment['epoch']}.jsonl"; val = rows(valp); vt = rows(data / 'pruner_val.jsonl')
        vp = {(r['instance_id'], r['function_id']): r for r in val}; vi = {(r['instance_id'], r['function_id']): r for r in vt}
        if len(vp) != len(val) or vp.keys() != vi.keys() or any(vp[k]['label'] != vi[k]['label'] for k in vi):
            raise ValueError('Actual val assessment differs from frozen val pairs/labels')
        val_metrics = evaluate_predictions(val)
        if val_metrics != assessment['val'] or val_metrics != next(c['val'] for c in curves if c['epoch'] == assessment['epoch']):
            raise ValueError('Stored val metrics do not reproduce actual probabilities')
        files[str(trainp)] = sha(trainp); files[str(valp)] = sha(valp)
        measured[role] = {'epoch': assessment['epoch'], 'train_accuracy': train_metrics['overall']['accuracy'],
                          'val_accuracy': val_metrics['overall']['accuracy'], 'actual_rank': adapter['r'],
                          'actual_alpha': adapter['lora_alpha'], 'actual_dropout': adapter['lora_dropout']}
    return {'run': str(run), 'expected_configuration': expected, 'roles': measured, 'files_sha256': files,
            'best_val_prediction_path': str(run / f"val_epoch_{best['epoch']}.jsonl"), 'test_rows_decoded': False}


def snapshot_bindings():
    result = {}
    for name, path in DECISIONS.items():
        decision = read(path); result[str(path)] = sha(path)
        for rel, digest in decision['policy_code_sha256'].items():
            cp = ROOT / (rel if rel.startswith('code_v5') else 'code_v5/' + rel)
            if sha(cp) != digest: raise ValueError('Frozen core code drift')
            result[str(cp)] = digest
        for rel, digest in decision.get('regularized_code_sha256', {}).items():
            cp = ROOT / 'code_v5_regularized' / rel
            if sha(cp) != digest: raise ValueError('Frozen r8 code drift')
            result[str(cp)] = digest
        for field in ('execution_contract_path',): result[decision[field]] = sha(decision[field])
    for relative in REPORT_TOOLS: result[str(ROOT / relative)] = sha(ROOT / relative)
    result[str(Path(__file__).resolve())] = sha(Path(__file__))
    for data in (A_DATA, B_DATA):
        for name in ('pruner_train.jsonl', 'pruner_val.jsonl', 'pruner_test.jsonl', 'statistics.json', 'split_manifest.json', 'test_file_seal.json'):
            result[str(data / name)] = sha(data / name)  # test is binary hash only
    return result


def check_bindings(plan):
    for path, expected in plan['source_bindings_sha256'].items():
        if sha(path) != expected: raise RuntimeError('Bound source/data/decision changed; do not silently refreeze: ' + path)
    for data in (A_DATA, B_DATA):
        if (data / 'pruner_test.jsonl.v5_opened_once.json').exists(): raise PermissionError('Test opened; report coordinator stops')


def readiness():
    for label, p in [('A_r8', A_R8), ('B', B_RUN)]:
        status = read(p / 'sequence_status.json')
        if status['stage'] in ('failed', 'blocked_by_A_failure') or status.get('test_opened') is not False:
            raise RuntimeError(label + ' execution failed or test opened')
        if status['stage'] != 'complete': return False, label + ':' + status['stage']
        outcome = read(p / 'outcome/assessment_report.json')
        if outcome['test_opened'] is not False: raise PermissionError(label + ' outcome test opened')
        for model in outcome['models'].values():
            if sha(model['training_summary_path']) != model['summary_sha256']: raise RuntimeError('Outcome summary binding drift')
    if read(B_RUN / 'training/pair_status.json')['stage'] != 'complete': raise RuntimeError('B pair not complete despite completed sequence')
    return True, 'real_A_B_complete'


def relocate_links(text, original_dir, new_figures):
    hrefs = []
    def replace(match):
        original = match.group(2).strip('<>')
        if original.startswith(('http://', 'https://', '#', 'mailto:')): return match.group(0)
        filename, _, anchor = original.partition('#')
        path = (new_figures / filename.split('/', 1)[1]) if filename.startswith('figures/') else (original_dir / filename).resolve()
        if not path.exists(): raise FileNotFoundError('Snapshot local href would break: ' + str(path))
        hrefs.append(str(path))
        target = str(path) + ('#' + anchor if anchor else '')
        return match.group(1) + ('<' + target + '>' if ' ' in target else target) + ')'
    converted = re.sub(r'(!?\[[^\]\n]*\]\()([^\)\n]+)\)', replace, text)
    return converted, hrefs


def check_interfaces():
    for module in ('code_v5.compare_noise_runtime', 'code_v5.report_gold_routes', 'code_v5.build_v5_ab_overview', 'code_v5.plot_validation_curves'):
        if not callable(importlib.import_module(module).main): raise ValueError('Missing reporting interface')
    if any(name in sys.modules for name in ('torch', 'transformers', 'peft')): raise RuntimeError('CPU report interface unexpectedly imported model libraries')
    assert_adapter({'r': 8, 'lora_alpha': 32, 'lora_dropout': .1, 'target_modules': ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']}, {'rank': 8,'alpha':32,'dropout':.1})
    try: assert_adapter({'r':16}, {'rank':8,'alpha':32,'dropout':.1})
    except ValueError: pass
    else: raise AssertionError('Wrong adapter rank accepted')
    try: rows(BASE / 'data_v3/pruner_test.jsonl')
    except PermissionError: pass
    else: raise AssertionError('Sealed test not refused before open')
    with tempfile.TemporaryDirectory(prefix='v5-coordinator-linkcheck-') as td:
        p = Path(td); (p/'f.md').write_text('fixture'); figs = p/'figures'; figs.mkdir(); (figs/'x.png').write_bytes(b'fixture')
        converted, links = relocate_links('[file](f.md) ![plot](figures/x.png)', p, figs)
        assert len(links) == 2 and all(Path(x).exists() for x in links)
        try: relocate_links('[missing](nonexistent)', p, figs)
        except FileNotFoundError: pass
        else: raise AssertionError('Broken local href accepted')
    return ['CPU_report_imports_no_model_libraries', 'actual_adapter_rank_guard', 'test_path_refused_before_open', 'snapshot_local_link_relocation', 'missing_local_link_rejected']


def initialize(work):
    if work.exists(): raise FileExistsError('Coordinator plan is immutable; choose a new work directory')
    checks = check_interfaces()
    from code_v5.noise_disclosed_policy import validate_decision as original_gate
    from code_v5_regularized.policy import validate_decision as regularized_gate
    from code_v5.runtime_filtered_policy import validate_decision as B_gate
    original_gate(A_DATA, DECISIONS['A_original']); regularized_gate(A_DATA, DECISIONS['A_r8']); B_gate(B_DATA, DECISIONS['B'])
    a = {'original_reranker': validate_run(A_TRAIN/'reranker', A_DATA, kind='reranker', rank=16, dropout=0.),
         'original_instruct': validate_run(A_TRAIN/'instruct', A_DATA, kind='instruct', rank=16, dropout=0.),
         'prescribed_reranker': validate_run(A_R8/'reranker', A_DATA, kind='reranker', rank=8, dropout=.1)}
    if COMPARISON.exists() or COMPARISON_DOC.exists(): raise FileExistsError('Comparison target exists; no overwrite permitted')
    work.mkdir(parents=True)
    bindings = snapshot_bindings()
    for audit in a.values(): bindings.update(audit['files_sha256'])
    plan = {'at': now(), 'scope': 'CPU-only completed-A/B report coordinator; not training or experiment completion',
            'source_bindings_sha256': bindings, 'initial_actual_A_model_audits': a,
            'CPU_interface_and_guard_checks': checks, 'B_parent': str(B_RUN), 'comparison_output': str(COMPARISON),
            'comparison_doc': str(COMPARISON_DOC), 'snapshot_output': str(work/'final_snapshot'),
            'existing_rolling_report_figure_preserved': True, 'test_rows_decoded': False, 'model_calls': 0,
            'GPU_claimed': False, 'Verified_expansion_executed': False, 'Verified_missing_dependency': 'authentic historical231 reserved OOD IDs/manifest'}
    new_json(work/'plan.json', plan)
    state(work, 'prepared_waiting_for_real_B_complete', plan_sha256=sha(work/'plan.json'))
    print(json.dumps({'initialized': str(work), 'plan_sha256':sha(work/'plan.json'), 'actual_A_audit_passed':True}))


def command(work, args):
    with (work/'commands.jsonl').open('a') as stream: stream.write(json.dumps({'at':now(),'argv':args})+'\n')
    result = subprocess.run([sys.executable, '-B', *args], cwd=ROOT,
        env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1'),
        capture_output=True, text=True)
    with (work/'child_output.log').open('a') as stream: stream.write(result.stdout + result.stderr)
    if result.returncode: raise RuntimeError('CPU reporting subprocess failed; preserved logs: ' + ' '.join(args[:3]))


def final_reports(work, plan):
    check_bindings(plan)
    audits = dict(plan['initial_actual_A_model_audits'])
    audits['B_reranker'] = validate_run(B_RUN/'training/reranker', B_DATA, kind='reranker', rank=8, dropout=.1)
    audits['B_instruct'] = validate_run(B_RUN/'training/instruct', B_DATA, kind='instruct', rank=16, dropout=0.)
    if COMPARISON.exists() or COMPARISON_DOC.exists(): raise FileExistsError('Comparison target appeared; preserve it and stop')
    snapshot = work/'final_snapshot'
    if snapshot.exists(): raise FileExistsError('Final snapshot target exists; never overwrite partially produced evidence')
    snapshot.mkdir()
    state(work, 'verified_completed_summaries_and_actual_adapters_reporting')
    command(work, ['-m','code_v5.compare_noise_runtime','--a-training-dir',str(A_TRAIN), '--a-reranker-dir',str(A_R8/'reranker'),
          '--b-training-dir',str(B_RUN/'training'), '--a-data-dir',str(A_DATA),'--b-data-dir',str(B_DATA),'--output-dir',str(COMPARISON)])
    for kind in ('reranker','instruct'):
        command(work, ['-m','code_v5.report_gold_routes','--predictions',audits['B_'+kind]['best_val_prediction_path'],
             '--validation',str(B_DATA/'pruner_val.jsonl'),'--output-dir',str(snapshot/('B_'+kind+'_GoldRoutes'))])
    # Run root's plotting/report interface in this CPU process and redirect all
    # newly rendered presentation artifacts into a separate final snapshot.
    os.environ['MPLCONFIGDIR'] = str(work/'plot_cache')
    plot = importlib.import_module('code_v5.plot_validation_curves'); plot.OUTPUT = snapshot/'figures'; plot.main()
    overview = importlib.import_module('code_v5.build_v5_ab_overview'); overview.OUT = snapshot/'overview_original_context.txt'; overview.main()
    rewritten, links = relocate_links(overview.OUT.read_text(), ROOT/'docs/v5-pruner', snapshot/'figures')
    final_overview = snapshot/'实验报告_v5_总览.md'
    with final_overview.open('x', encoding='utf-8') as stream: stream.write(rewritten)
    check_bindings(plan)
    if any(name in sys.modules for name in ('torch','transformers','peft')): raise RuntimeError('Model libraries unexpectedly loaded')
    new_json(snapshot/'actual_model_audits.json', {'at':now(),'models':audits,'test_rows_decoded':False,'model_loaded':False})
    comparison = read(COMPARISON/'comparison.json')
    if comparison['test_opened_by_this_tool'] is not False or comparison['model_calls'] != 0: raise RuntimeError('Unexpected test/model action')
    files = {str(p):sha(p) for p in snapshot.rglob('*') if p.is_file()}
    files[str(COMPARISON/'comparison.json')] = sha(COMPARISON/'comparison.json'); files[str(COMPARISON_DOC)] = sha(COMPARISON_DOC)
    receipt = {'at':now(),'status':'completed_CPU_reports_for_actual_A_B_only','coordinator_plan_sha256':sha(work/'plan.json'),
        'snapshot_files_sha256':files, 'snapshot_overview_path':str(final_overview), 'overview_original_context_path':str(ROOT/'docs/v5-pruner/实验报告_v5_总览.md'),
        'snapshot_all_local_hrefs_resolved_existing':True,'snapshot_local_href_targets':links,
        'matched_A_r8_and_B_r8_reranker':True,'matched_original_A_and_B_instruct':True,
        'val_common_pair_count':comparison['validation_pair_counts']['common'],
        'B_GoldRoutes_use_each_actual_best_completed_epoch':True,'root_rolling_overview_and_figures_overwritten':False,
        'model_loaded':False,'new_model_calls':0,'GPU_claimed':False,'test_rows_decoded':False,'new_localization_predictions':False,
        'cross_experiment_matrix_modified':False,'Verified_expansion_executed':False,
        'Verified_unresolved_dependency':'Missing authentic historical231 OOD issue IDs/source manifest; official500 input available, no exact expansion performed',
        'complete_v5_or_end_to_end_success_claimed':False,'root_independent_final_review_required':True}
    new_json(work/'final_report_receipt.json',receipt)
    state(work,'complete_report_snapshot_pending_root_independent_review',receipt_sha256=sha(work/'final_report_receipt.json'))


def run(work):
    plan = read(work/'plan.json')
    try:
        while True:
            check_bindings(plan)
            ready, why = readiness()
            if ready: break
            if (B_RUN/'training/pair_status.json').exists() and read(B_RUN/'training/pair_status.json')['stage'] == 'failed':
                raise RuntimeError('B training pair failed')
            state(work,'waiting_for_real_B_complete',reason=why)
            time.sleep(30)
        final_reports(work,plan)
    except BaseException as exc:
        failure={'at':now(),'status':'stopped_without_fabricating_metrics','type':type(exc).__name__,'error':str(exc),
                 'traceback':traceback.format_exc(),'test_rows_decoded':False,'model_loaded':False,'Verified_executed':False}
        if not (work/'failure_receipt.json').exists(): new_json(work/'failure_receipt.json',failure)
        state(work,'failed_preserving_existing_outputs',error=str(exc))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--initialize',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();work=args.work_dir.resolve()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    if args.initialize: initialize(work)
    elif args.check:
        check_bindings(read(work/'plan.json'));print(json.dumps({'readiness':readiness(),'model_loaded':False,'test_rows_decoded':False}))
    else: run(work)
