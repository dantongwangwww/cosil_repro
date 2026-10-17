"""Derive weights, register promotion branches, then freeze before any training."""
import json
import math
import shutil
from collections import Counter
from code_v6_round2.common import *


def derive_weights(train, val):
    counts = Counter(r['distribution_group'] for r in train)
    target = Counter(r['distribution_group'] for r in val)
    positive = {'gold_AB', 'C_positive'}
    assert set(counts) == set(target) == positive | {'D_only_negative', 'E_negative'}
    denominators = {True: sum(target[g] for g in positive),
                    False: sum(n for g, n in target.items() if g not in positive)}
    total = len(train)
    return {g: total * .5 * target[g] / denominators[g in positive] / counts[g] for g in counts}


def write_rows(path, rr):
    with path.open('x') as f:
        for r in rr:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')


def run():
    preserve_history()
    assert not CONTROL.exists(), 'Never overwrite a frozen second round'
    CONTROL.mkdir(parents=True); DATA.mkdir(); RACE.mkdir()
    instruction_sha = sha(INSTRUCTION)
    train = rows(PARENT_DATA / 'pruner_train.jsonl'); val = rows(PARENT_DATA / 'pruner_val.jsonl')
    weights = derive_weights(train, val)
    rewritten = [{**r, 'sample_weight': weights[r['distribution_group']]} for r in train]
    for old, new in zip(train, rewritten):
        assert {k:v for k,v in old.items() if k != 'sample_weight'} == {k:v for k,v in new.items() if k != 'sample_weight'}
        factor = 1.5 if old['label'] else .75
        assert math.isclose(new['sample_weight'], old['sample_weight'] * factor, rel_tol=1e-12)
    assert math.isclose(sum(r['sample_weight'] for r in rewritten), len(train), abs_tol=1e-7)
    positive_mass = sum(r['sample_weight'] for r in rewritten if r['label'])
    assert math.isclose(positive_mass, len(train)/2, abs_tol=1e-7)
    write_rows(DATA/'pruner_train.jsonl', rewritten)
    for name in ['pruner_val.jsonl', 'split_manifest.json']:
        shutil.copyfile(PARENT_DATA/name, DATA/name)
        assert sha(DATA/name) == sha(PARENT_DATA/name)
    stats = {'time':now(), 'train_pairs':len(train), 'val_pairs':len(val),
             'train_issues':len({r['instance_id'] for r in train}), 'val_issues':len({r['instance_id'] for r in val}),
             'changed_row_fields':['sample_weight'], 'train_rows_order_and_all_other_values_identical':True,
             'val_bytes_identical':True, 'split_bytes_identical':True, 'new_weights':weights,
             'old_weights':read(PARENT_DATA/'statistics.json')['training_weights'],
             'positive_weighted_mass':positive_mass, 'negative_weighted_mass':len(train)-positive_mass,
             'mean_weight':1.0, 'positive_weight_scale':1.5, 'negative_weight_scale':.75,
             'validation_positive_fraction':sum(r['label'] for r in val)/len(val),
             'effective_sample_size':sum(r['sample_weight'] for r in rewritten)**2/sum(r['sample_weight']**2 for r in rewritten),
             'counts':dict(Counter(r['distribution_group'] for r in train)),
             'new_labels':0, 'new_mining':0, 'new_runtime_tests':0, 'test_contents_opened':False}
    write(DATA/'statistics.json', stats)
    provenance = read(PARENT_DATA/'provenance.json')
    provenance['parent_T2_freeze_sha256'] = sha(PARENT_DATA/'freeze_manifest.json')
    provenance['parent_first_round_delivery_sha256'] = sha(PARENT_RACE/'final_delivery_receipt.json')
    provenance['historical_sha256'].update(read(PARENT_RACE/'final_delivery_receipt.json')['reports_sha256'])
    write(DATA/'provenance.json', provenance)
    write(DATA/'freeze_manifest.json', {'time':now(), 'parent_T2_freeze_sha256':sha(PARENT_DATA/'freeze_manifest.json'),
          'only_intervention':'P:N total training weight 1:2 -> 1:1; conditional source mix unchanged',
          'artifacts_sha256':{str(p):sha(p) for p in sorted(DATA.iterdir()) if p.is_file()}, 'test_opened':False})
    recipe=read(ROUND1_OUT/'T3_user_authorization.json')['training_recipe']
    write(CONTROL/'T3_user_authorization.json', {'time':now(), 'instruction_path':str(INSTRUCTION),
          'instruction_sha256':instruction_sha, 'pre_change_github_commit':PRE_CHANGE_COMMIT,
          'T3_allowed':True, 'round':2, 'round2_data_freeze_sha256':sha(DATA/'freeze_manifest.json'),
          'parent_T2_freeze_sha256':sha(PARENT_DATA/'freeze_manifest.json'), 'training_recipe':recipe,
          'test_contents_allowed':False, 'T4_allowed':False,
          'conditional_canary_authorized':True, 'vLLM_service_changes_authorized':False,
          'note':'canary only after registered promotion; service lifecycle prohibition remains in force'})
    receipt_dir=CONTROL/'T3_model_sources';receipt_dir.mkdir()
    for key in ['reranker4B','swerank7B']:
        shutil.copyfile(ROUND1_OUT/f'T3_model_sources/{key}_download_receipt.json', receipt_dir/f'{key}_download_receipt.json')
    sources=[ROOT/'code_v6_round2'/name for name in ['common.py','prepare.py','train.py','diagnostics.py','report.py','run.py','checks.py']]
    sources += [ROOT/'code_v6'/name for name in ['training_codec.py','input_format.py','qualification.py','assess_T3.py','common.py']]
    sources += [ROOT/'code_v5/judge_models.py',ROOT/'code_v5/metrics.py']
    write(RACE/'protocol.json', {'frozen_at':now(), 'round':2, 'user_authorization_sha256':sha(CONTROL/'T3_user_authorization.json'),
          'T2_freeze_sha256':sha(PARENT_DATA/'freeze_manifest.json'), 'round2_data_freeze_sha256':sha(DATA/'freeze_manifest.json'),
          'code_sha256':{str(p):sha(p) for p in sources}, 'training_recipe':recipe,
          'qualification_protocol_sha256':sha(PARENT_DATA/'qualification_protocol.json'),
          'control':'exact first-round rows/order/input/labels; val byte-identical; only train sample_weight differs',
          'weighted_P_to_N':'1:1', 'conditional_weights':'same T2 formula matching val gold/C within P and E/D within N',
          'epoch_selection':'unchanged code_v6.assess_T3.select; candidates for promotion are each base selected checkpoint only',
          'promotion':{'CI':'unchanged defined nondegenerate bootstrap gold upper<=.15 AND mixed precision lower>=.85',
                       'feasibility':'if no CI-qualified selected model, gold point<=.15 AND mixed precision point>=.85 at low=.6',
                       'ranking':'unchanged gold CI upper, precision CI lower, accuracy, exact ties smaller base',
                       'no_candidate':'stop and report; no pipeline or sealed test',
                       'CI_stability':'winner only, seeds1/2, identical recipe; both must pass same CI gates before canary',
                       'feasibility_is_not_CI_certification':True},
          'safe_threshold':'largest IEEE float low<.9 and below minimum calibrated val gold p; report no-feasible case when min=0; no threshold tuning for formal gate',
          'canary':'default low=.6 and safety low* with high=.9, reuse T1 off20 cohort/results; no main-Qwen baseline rerun',
          'canary_service_constraint':'do not start/stop/change vLLM/CSRSE; if compatible main Qwen unavailable, deliver candidate and commands pending service authorization',
          'models_priority':ORDER, 'SweRank_priority':'start after both priority arms train; separate card/headroom, never displace them',
          'memory_profile':'first-round successful profiles; 7B allocator .90/min free23000MiB, no recipe alteration',
          'seeds':[0], 'optional_CI_stability_seeds':[1,2], 'test_stat_only':test_stats(),
          'interpretation_limits':['no causal estimate of data-axis effect across changed val populations',
              'CI difficulty depends on observed issue clusters; no universal 5/76 or97% threshold claim',
              'same-val calibration/epoch selection and low* are exploratory and optimistic',
              'SweRank pointwise task transfer, shared Qwen ancestry, noncommercial license, contamination unknown'],
          'test_contents_allowed':False, 'T4_allowed':False, 'new_backbones_allowed':False})
    snapshot=DOCS/'指令_v6_T3首轮判读与第二轮_2026-10-17_原始快照.md'
    assert not snapshot.exists();shutil.copyfile(INSTRUCTION,snapshot)
    preserve_history();print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__=='__main__':run()
