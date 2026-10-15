"""Compare completed B/C classifiers without models, test labels, or writers.

First freeze an input binding after both real sequences complete. A separate
execute command verifies the binding and writes a new report directory only.
Saved prediction rows omit input_sha256; it is joined from their hash-bound
source train/val rows after exact identity, label and source validation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from code_v5.metrics import _sources, evaluate_predictions
from code_v5.compare_noise_runtime import CONFIG_FIELDS, paired_accuracy_interval
from code_v5.report_gold_routes import describe

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'results/v5_pruner'
B_RUN = BASE/'B_runtime_reviewed_regularized_exploratory'
B_DATA = BASE/'data_v3_runtime_filtered_reviewed'
OOD = BASE/'verified_regenerated_ood/verified231_manifest.json'
PURE_TOOLS = ('code_v5/metrics.py', 'code_v5/compare_noise_runtime.py',
              'code_v5/report_gold_routes.py', 'code_v5/race_and_calibrate.py',
              'code_v5/coordinate_completed_AB_reports_v3.py',
              'code_v5_c_reports/__init__.py', 'code_v5_c_reports/compare_completed_b_c.py')


class IncompleteInputs(RuntimeError):
    pass


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def read_json(path):
    path = Path(path).resolve()
    if path.suffix != '.json':
        raise PermissionError('JSON metadata reader refuses JSONL/other data formats before open')
    if not path.exists():
        raise IncompleteInputs('Real completed metadata is missing: ' + str(path))
    return json.loads(path.read_text())


def rows(path, split):
    path = Path(path).resolve()
    if split not in {'train','val'} or not re.fullmatch(
            r'(?:pruner_'+split+r'|'+split+r'_epoch_[1-9][0-9]*)\.jsonl', path.name):
        raise PermissionError('Rows reader accepts explicit source/assessment train or val paths only')
    if re.search(r'(?:^|[/_.-])test(?:$|[/_.-])', str(path).lower()):
        raise PermissionError('Sealed test path refused before open')
    if not path.exists():
        raise IncompleteInputs('Saved real assessment/source missing: ' + str(path))
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if any(row.get('split') != split for row in result):
        raise ValueError('Assessment/source rows have a different split')
    return result


def index(supplied):
    found = {}
    for row in supplied:
        key = row['instance_id'], row['function_id']
        if key in found:
            raise ValueError('Repeated pair observations must not be favorably selected or averaged')
        if type(row['label']) is not bool:
            raise ValueError('Relevant label must be an actual bool')
        found[key] = row
    return found


def align_predictions(predicted, truth):
    found, data = index(predicted), index(truth)
    if found.keys() != data.keys():
        raise ValueError('Saved predictions do not cover exact frozen source pairs')
    enriched = {}
    for identity, prediction in found.items():
        source = data[identity]
        fingerprint = source['input_sha256']
        if not re.fullmatch('[0-9a-f]{64}', fingerprint):
            raise ValueError('Frozen source input fingerprint has invalid syntax')
        if (prediction['label'] != source['label'] or _sources(prediction) != _sources(source)
                or prediction.get('input_sha256', fingerprint) != fingerprint):
            raise ValueError('Saved pair label/source/input fingerprint differs from frozen source')
        enriched[identity] = {**prediction, 'input_sha256':fingerprint,
                              'input_sha256_origin':'frozen_source_row_join; original assessment may omit it'}
    evaluate_predictions(list(enriched.values()))  # finite probability and provenance guards
    return enriched


def complete_state(run, condition, files):
    run = Path(run).resolve()
    for relative in ('sequence_status.json','training/pair_status.json','outcome/assessment_report.json'):
        path = run/relative
        state = read_json(path)
        if relative.endswith('status.json') and state.get('stage') != 'complete':
            raise IncompleteInputs(condition+' real sequence/pair is not complete')
        if relative != 'training/pair_status.json' and state.get('test_opened') is not False:
            raise PermissionError('Completed condition opened test or lacks explicit test sealing')
        files[str(path)] = sha(path)
    outcome = read_json(run/'outcome/assessment_report.json')
    expected_policy = 'runtime-covered-v3' if condition == 'B' else 'verified-plus-B-runtime-v1'
    if (outcome.get('track') != 'exploratory' or outcome.get('data_policy') != expected_policy
            or set(outcome['models']) != {'reranker','instruct'}):
        raise ValueError('Unknown completed B/C outcome schema or policy')
    return outcome


def bind_data(data, manifest, files):
    data = Path(data).resolve()
    if (data/'pruner_test.jsonl.v5_opened_once.json').exists():
        raise PermissionError('Pruner test has already been opened')
    metadata = manifest['data']
    if metadata.get('test_labels_read') is not False:
        raise PermissionError('Training data provenance reports test access')
    for field, name in (('statistics_sha256','statistics.json'),('seal_sha256','test_file_seal.json'),
                        ('split_manifest_sha256','split_manifest.json')):
        path = data/name
        if sha(path) != metadata[field]:
            raise ValueError('Actual training provenance differs from its frozen input')
        files[str(path)] = sha(path)
    seal = read_json(data/'test_file_seal.json')
    if seal.get('test_performance_opened') is not False:
        raise PermissionError('Data seal reports opened test performance')
    for split in ('train','val','test'):
        path = data/f'pruner_{split}.jsonl'
        if Path(seal['frozen_files'][split]['path']).resolve() != path or sha(path) != seal['frozen_files'][split]['sha256']:
            raise ValueError('Frozen source bytes differ from seal')
        files[str(path)] = sha(path)  # test bytes only; rows() never called for test
    decision = metadata['root_decision']
    decision_path = Path(decision['path']).resolve()
    if sha(decision_path) != decision['sha256']:
        raise ValueError('Completed run root authorization changed')
    declaration = read_json(decision_path)
    if (declaration.get('test_open_allowed') is not False or declaration.get('track') != 'exploratory'
            or Path(declaration['data_dir']).resolve() != data):
        raise PermissionError('Root data/track/test authorization differs')
    files[str(decision_path)] = sha(decision_path)
    contract = Path(declaration['execution_contract_path']).resolve()
    if sha(contract) != declaration['execution_contract_sha256']:
        raise ValueError('Root execution contract changed')
    files[str(contract)] = sha(contract)
    for split in ('train','val','test'):
        if declaration[split+'_sha256'] != files[str(data/f'pruner_{split}.jsonl')]:
            raise ValueError('Root authorization does not bind this source data version')
    for relative, digest in declaration['policy_code_sha256'].items():
        source = ROOT/(relative if relative.startswith('code_v5') else 'code_v5/'+relative)
        if sha(source) != digest:
            raise ValueError('Frozen policy/training namespace changed')
        files[str(source)] = digest


def audit_run(run, data, outcome_model, kind, files):
    # Reuse the frozen, CPU-only actual checkpoint audit; never import trainers.
    from code_v5.coordinate_completed_AB_reports_v3 import validate_run
    run, data = Path(run).resolve(), Path(data).resolve()
    manifest_path, summary_path = run/'training_manifest.json', run/'training_summary.json'
    manifest, summary = read_json(manifest_path), read_json(summary_path)
    if ('training_summary_path' in outcome_model or Path(outcome_model['summary_path']).resolve() != summary_path
            or outcome_model['summary_sha256'] != sha(summary_path)):
        raise ValueError('Actual B/C summary_path schema/path/hash differs')
    bind_data(data, manifest, files)
    audited = validate_run(run, data, kind=kind, rank=8 if kind=='reranker' else 16,
                           dropout=.1 if kind=='reranker' else 0.)
    files.update(audited['files_sha256'])
    if kind == 'instruct':
        def original_score(curve):
            metric=curve['val'];o=metric['overall']
            acc,auc,e=(-1 if value is None else value for value in
                       (o['accuracy'],o['auc'],metric['E_correct_rejection_rate']))
            return acc>=.8 and auc>=.85,e,acc,auc,-curve['epoch']
        if max(read_json(run/'training_curves.json'),key=original_score)['epoch'] != summary['checkpoint_assessments']['best']['epoch']:
            raise ValueError('Actual instruct best differs from the fixed original qualification/E-best selection')
    datasets = {split:rows(data/f'pruner_{split}.jsonl',split) for split in ('train','val')}
    measured, predictions = {}, {}
    for role in ('best','last'):
        assessment = summary['checkpoint_assessments'][role]
        if outcome_model[role] != assessment:
            raise ValueError('Real outcome best/last differs from saved model summary')
        measured[role] = {'epoch':assessment['epoch'], 'train':assessment['train'], 'val':assessment['val'],
                          'adapter_rank':audited['roles'][role]['actual_rank'],
                          'adapter_alpha':audited['roles'][role]['actual_alpha'],
                          'adapter_dropout':audited['roles'][role]['actual_dropout']}
        for split in ('train','val'):
            path = run/f"{split}_epoch_{assessment['epoch']}.jsonl"
            found = align_predictions(rows(path,split), datasets[split])
            if evaluate_predictions(list(found.values())) != assessment[split]:
                raise ValueError('Saved assessment metrics do not reproduce exact source-bound probabilities')
            if role=='best': predictions[split] = found
    profile = {**{field:manifest[field] for field in CONFIG_FIELDS},'base_model_sha256':manifest['model']['sha256']}
    return {'run':str(run),'profile':profile,'libraries':manifest['libraries'],'assessments':measured,
            'epochs_completed':summary['epochs_completed'],'early_stopped':summary['early_stopped'],
            'prediction_input_sha256_source':'joined from hash-bound original data rows, not fabricated into historical predictions'}, predictions, datasets


def partition_val(bval, cval, manifest):
    bindex, cindex = index(bval), index(cval)
    if len(bindex) != 363 or not bindex.keys() <= cindex.keys():
        raise ValueError('All 363 old Lite validation pairs must survive unchanged')
    for identity, old in bindex.items():
        new = cindex[identity]
        if any(new.get(field) != value for field,value in old.items()):
            raise ValueError('An old Lite validation source/input/label/provenance field changed')
    new_keys = cindex.keys()-bindex.keys(); eligible = set(manifest['mining_eligible_instance_ids'])
    reserved = set(manifest['instance_ids']); lite = set(manifest['Lite_excluded_ids'])
    if eligible & (reserved|lite) or len(eligible)!=186 or len(reserved)!=221:
        raise ValueError('Authoritative Verified cohort identities differ')
    if not new_keys or any(identity[0] not in eligible for identity in new_keys):
        raise ValueError('New validation rows must be genuine eligible Verified issues only')
    if any(row['instance_id'] in reserved for row in cval):
        raise PermissionError('Reserved OOD appeared in training validation')
    return sorted(bindex), sorted(new_keys)


def build(settings):
    files = {str((ROOT/path).resolve()):sha(ROOT/path) for path in PURE_TOOLS}
    runs = {tag:Path(settings[tag+'_run_dir']).resolve() for tag in ('B','C')}
    data = {tag:Path(settings[tag+'_data_dir']).resolve() for tag in runs}
    outcomes = {tag:complete_state(run,tag,files) for tag,run in runs.items()}
    verified_path = Path(settings['verified_manifest']).resolve(); manifest = read_json(verified_path)
    if manifest.get('complete_source_derived') is not True:
        raise IncompleteInputs('Authoritative Verified/OOD source derivation is not complete')
    files[str(verified_path)] = sha(verified_path)
    output = {'schema_version':1,'created_at':now(),'track':'exploratory','condition':'B_to_C_expanded_classifier_val_comparison',
              'model_loaded':False,'new_model_calls':0,'GPU_used':False,'test_labels_decoded':False,
              'new_localization_predictions':False,'new_matrix_columns':0,'classifier_metrics_are_Top5':False,
              'prediction_input_sha256_is_joined_from_frozen_source':True,'models':{},'alignment':{},'source_files_sha256':files}
    for kind in ('reranker','instruct'):
        audits, scores, datasets = {}, {}, {}
        for tag in ('B','C'):
            if Path(outcomes[tag]['data_dir']).resolve() != data[tag]:
                raise ValueError('Completed outcome data identity differs from report request')
            audits[tag], scores[tag], datasets[tag] = audit_run(runs[tag]/'training'/kind,data[tag],outcomes[tag]['models'][kind],kind,files)
        if audits['B']['profile'] != audits['C']['profile'] or audits['B']['libraries'] != audits['C']['libraries']:
            raise ValueError('Actual B/C base weights/configuration/training library versions differ')
        old, new = partition_val(datasets['B']['val'],datasets['C']['val'],manifest)
        bindex,cindex=index(datasets['B']['val']),index(datasets['C']['val'])
        groups = {'B_old_Lite_363':list(scores['B']['val'].values()),'C_all_val':list(scores['C']['val'].values()),
                  'C_old_Lite_363':[scores['C']['val'][identity] for identity in old],
                  'C_new_Verified_val':[scores['C']['val'][identity] for identity in new]}
        paired = {tag:{identity:scores[tag]['val'][identity] for identity in old} for tag in ('B','C')}
        interval = paired_accuracy_interval(paired['B'],paired['C'])
        interval['difference_C_minus_B'] = interval.pop('difference_B_minus_A')
        record = {'matched_actual_configuration':audits['B']['profile'],'actual_runs':audits,
                  'binary_threshold_0_5':{name:evaluate_predictions(members) for name,members in groups.items()},
                  'gold_three_routes_raw_nominal':{name:describe(members,.6,.9) for name,members in groups.items()},
                  'old_Lite_issue_cluster_paired_accuracy':interval,
                  'Qwen_gray_inference_run':False,'routing_thresholds_deployed':False}
        output['models'][kind] = record
        output['alignment'] = {'old_Lite_pair_count':len(old),'new_Verified_val_pair_count':len(new),'C_all_val_count':len(old)+len(new),
                               'old_Lite_identity_input_label_quads':[
                                   [i,f,bindex[i,f]['input_sha256'],bindex[i,f]['label']] for i,f in old],
                               'new_Verified_val_identity_input_label_quads':[
                                   [i,f,cindex[i,f]['input_sha256'],cindex[i,f]['label']] for i,f in new]}
    output['limitations'] = [
        'Train is fitting-sample performance; all reported validation labels are mechanical proxies, not model test or function Top5 localization.',
        'Old/new validation composition and training composition differ; matched profiles and common pairs do not alone establish causal benefit from additional data or noise filtering.',
        'Historical Qwen filtering affects some label provenance; these are not independent Qwen examinations.',
        'Gold means positive A/B source pairs, deduplicated; C-neighbor positives are separate. Gray Qwen has not run and must remain unmeasured.',
        'Raw nominal low=.6/high=.9 is a val diagnostic, not a safety guarantee or deployed threshold. No formal winner is selected by this report.',
        'Verified coverage filtering still has static-only fallback and incomplete path coverage; absence is not proof of causal irrelevance.']
    if any(module in sys.modules for module in ('torch','transformers','peft')):
        raise RuntimeError('CPU report unexpectedly imported model libraries')
    return output


def render(result):
    def pct(value): return 'NA' if value is None else f'{100*value:.2f}%'
    lines = ['# v5 B→C 同底座验证对照（exploratory）','',
             '本报告仅用真实完成checkpoint的保存train/val概率；test继续封存。这里的accuracy是函数相关性分类准确率，不是Top5定位准确率，不新增结果矩阵列。','',
             '预测文件没有inputSHA时，从manifest与封存收据绑定的源train/val行按iid/function/label/sources一一核证并取inputSHA；原预测不改写。旧Lite363逐项保留，新增val仅来自权威Verified186。','',
             '| 底座/条件 | checkpoint | train acc | val acc | val AUC | val E正确剔除 | val gold召回 | val混合集剔除precision |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for kind,record in result['models'].items():
        for tag in ('B','C'):
            best=record['actual_runs'][tag]['assessments']['best'];v=best['val'];m=v['overall']
            lines.append(f"| {kind}/{tag} | {best['epoch']} | {pct(best['train']['overall']['accuracy'])} | {pct(m['accuracy'])} | {m['auc']} | {pct(v['E_correct_rejection_rate'])} | {pct(m['gold_retention_recall'])} | {pct(m['reject_precision'])} |")
    lines += ['', '| 底座/val组成 | pair | accuracy | AUC | E正确剔除 | gold召回 | 混合集剔除precision |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for kind,record in result['models'].items():
        for name,v in record['binary_threshold_0_5'].items():
            m=v['overall'];lines.append(f"| {kind}/{name} | {m['pairs']} | {pct(m['accuracy'])} | {m['auc']} | {pct(v['E_correct_rejection_rate'])} | {pct(m['gold_retention_recall'])} | {pct(m.get('reject_precision'))} |")
    lines += ['', '旧Lite363使用相同iid/function/inputSHA/label，按issue簇2000次bootstrap：','']
    for kind,record in result['models'].items():
        v=record['old_Lite_issue_cluster_paired_accuracy'];interval=v['issue_cluster_percentile_95_interval']
        lines.append(f"- {kind}：C−B {pct(v['difference_C_minus_B'])}，95%探索性区间 {'NA' if interval is None else pct(interval[0])+' 至 '+pct(interval[1])}；{v['issue_count']}个issue簇。")
    lines += ['', '| 底座/val组成（raw .6/.9） | gold直留 | gold直剪 | gold灰区 | 全体灰区 | E直剪率 | 混合集直剪precision |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for kind,record in result['models'].items():
        for name,v in record['gold_three_routes_raw_nominal'].items():
            g=v['gold_routes'];cells=[f"{g[k]['count']}/{v['gold_positive_pairs']} ({pct(g[k]['fraction'])})" for k in ('retain','reject','qwen')]
            lines.append(f"| {kind}/{name} | "+' | '.join(cells)+f" | {pct(v['gray_fraction'])} | {pct(v['E']['direct_correct_rejection_rate'])} | {pct(v['mixed_direct_rejection_precision'])} |")
    lines += ['', 'Gold分母为A/B来源正例pair并集；C邻居正例另列在结构化metrics。E剔除率=TN/(TN+FP)，混合集剔除precision=TN/(TN+FN)，两者分别报告。','',
              '三分是raw默认阈值诊断；未推理灰区Qwen、未部署阈值，不能将灰区计为已正确保留，也不能当正式test安全性或端到端收益。','']
    lines += ['- '+note for note in result['limitations']]
    return '\n'.join(lines)+'\n'


def check_interfaces():
    try: rows(B_DATA/'pruner_test.jsonl','test')
    except PermissionError: pass
    else: raise AssertionError('Test decoder guard failed')
    data=rows(B_DATA/'pruner_val.jsonl','val')
    baseline=rows(B_RUN/'training/reranker/val_epoch_1.jsonl','val')
    assert len(align_predictions(baseline,data))==363
    try: align_predictions([baseline[0],baseline[0]],data[:1])
    except ValueError: pass
    else: raise AssertionError('Duplicate favorable selection accepted')
    wrong={**baseline[0],'label':not baseline[0]['label']}
    try: align_predictions([wrong],data[:1])
    except ValueError: pass
    else: raise AssertionError('Prediction label drift accepted')
    try: complete_state(BASE/'C_missing_actual_results_guard_fixture','C',{})
    except IncompleteInputs: pass
    else: raise AssertionError('Missing C completed inputs accepted')
    if any(module in sys.modules for module in ('torch','transformers','peft')):
        raise AssertionError('Model libraries imported')
    return {'status':'CPU_interfaces_and_refusal_guards_checked','real_C_metric_generated':False,
            'checks':['test_path_refused_before_open','actual_B_363_predictions_source_inputSHA_join',
                      'duplicate_pair_refused','label_drift_refused','missing_C_actual_completion_refused'],
            'model_loaded':False,'GPU_used':False,'test_labels_decoded':False}


def write_new(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check-interfaces',action='store_true')
    group.add_argument('--prepare-binding',type=Path)
    group.add_argument('--execute-binding',type=Path)
    parser.add_argument('--b-run-dir',type=Path,default=B_RUN)
    parser.add_argument('--b-data-dir',type=Path,default=B_DATA)
    parser.add_argument('--c-run-dir',type=Path)
    parser.add_argument('--c-data-dir',type=Path)
    parser.add_argument('--verified-manifest',type=Path,default=OOD)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    if args.check_interfaces:
        print(json.dumps(check_interfaces()));return
    if args.prepare_binding:
        if args.c_run_dir is None or args.c_data_dir is None:
            parser.error('Actual completed C run/data directories required')
        settings={tag+'_run_dir':str(getattr(args,tag.lower()+'_run_dir').resolve()) for tag in ('B','C')}
        settings.update({tag+'_data_dir':str(getattr(args,tag.lower()+'_data_dir').resolve()) for tag in ('B','C')})
        settings['verified_manifest']=str(args.verified_manifest.resolve())
        result=build(settings)
        binding={'schema_version':1,'created_at':now(),'settings':settings,'source_files_sha256':result['source_files_sha256'],
                 'both_real_sequences_and_outcomes_complete':True,'same_profiles_and_old_363_verified':True,
                 'models_loaded':False,'test_labels_decoded':False,'actual_classifiers_only_not_localization':True}
        write_new(args.prepare_binding,binding)
        print(json.dumps({'binding_path':str(args.prepare_binding.resolve()),'binding_sha256':sha(args.prepare_binding),'actual_completed_inputs_verified':True}));return
    if args.output_dir is None or args.output_dir.exists():
        parser.error('A new nonexistent --output-dir is required; earlier outputs never overwritten')
    binding=read_json(args.execute_binding)
    for path,digest in binding['source_files_sha256'].items():
        if sha(path)!=digest:raise ValueError('Frozen B/C report input/code changed; no silent rebind')
    result=build(binding['settings'])
    if result['source_files_sha256']!=binding['source_files_sha256']:
        raise ValueError('Actual input artifact set differs from frozen report binding')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    write_new(args.output_dir/'comparison.json',result)
    with (args.output_dir/'B-C扩后验证对照.md').open('x') as stream:stream.write(render(result))
    write_new(args.output_dir/'report_receipt.json',{'status':'complete_CPU_B_C_val_report', 'created_at':now(),
              'binding_path':str(args.execute_binding.resolve()),'binding_sha256':sha(args.execute_binding),
              'comparison_sha256':sha(args.output_dir/'comparison.json'),'report_sha256':sha(args.output_dir/'B-C扩后验证对照.md'),
              'model_calls':0,'GPU_used':False,'test_labels_decoded':False,'new_matrix_columns':0,
              'complete_v5_or_formal_OOD_success_claimed':False,'root_independent_review_required':True})
    print(json.dumps({'report_dir':str(args.output_dir.resolve()),'receipt_sha256':sha(args.output_dir/'report_receipt.json')}))


if __name__=='__main__':
    main()
