"""Anchor TRAIN e_log review evidence to actual base Git blobs and traces."""
import ast
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/v5_pruner/C_preconstruction_actual'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def object_sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def main():
    packet=BASE/'review_source_runtime_evidence_TRAIN30.json';samples_path=BASE/'human_review_pending_TRAIN30.jsonl'
    assert digest(packet)=='b68ecb051e256b17d0540c3f8a9c9ca52b603c1592ac2fb0c573b3056b561af2'
    assert digest(samples_path)=='c78b8a79f87adfc43897853aab910c63355404653b77b00703d6a41490eeef9f'
    records=json.loads(packet.read_text())['records'];samples=[json.loads(x) for x in samples_path.read_text().splitlines()]
    out=BASE/'e_log_source_witnesses';out.mkdir(exist_ok=True)
    assert not any(out.iterdir()),'Do not replace existing witnesses'
    extra={1:['django/db/migrations/state.py','django/db/migrations/operations/models.py','django/db/migrations/autodetector.py'],
           2:['src/_pytest/fixtures.py','src/_pytest/python.py'],
           3:['django/db/backends/base/schema.py','django/db/migrations/operations/fields.py','django/db/migrations/autodetector.py'],
           4:['django/db/migrations/operations/base.py','django/db/migrations/operations/models.py','django/db/migrations/migration.py','django/db/migrations/optimizer.py','django/db/migrations/autodetector.py'],
           5:['sphinx/ext/autosummary/__init__.py','sphinx/ext/autosummary/generate.py'],
           6:['src/_pytest/assertion/rewrite.py'],7:['django/forms/widgets.py'],
           8:['sympy/matrices/expressions/matexpr.py','sympy/matrices/expressions/blockmatrix.py','sympy/core/basic.py'],
           9:['django/db/models/base.py','django/db/models/options.py','django/db/models/fields/__init__.py'],
           10:['sympy/utilities/autowrap.py','sympy/utilities/codegen.py']}
    receipts=[]
    for n,(record,sample) in enumerate(zip(records[:10],samples[:10]),1):
        assert sample['review_family']=='e_log' and sample['label'] is False and sample['split']=='train'
        assert all(record['identity'][k]==sample[k] for k in ['review_family','instance_id','function_id','input_sha256'])
        assert object_sha(sample)==record['source_binding']['candidate_row_sha256']
        issue=record['source_binding']['issue_record'];mirror=ROOT/'mirror_cache'/(issue['repo'].split('/')[-1]+'.git')
        commit=issue['base_commit'];assert commit==record['original_graph']['base_commit']
        graph=Path(record['original_graph']['graph_path']);assert digest(graph)==record['original_graph']['graph_sha256']
        result=Path(record['runtime_evidence']['result_path']);assert digest(result)==record['runtime_evidence']['result_sha256']
        modules={}
        for file in extra[n]:
            raw=subprocess.check_output(['git','-C',str(mirror),'show',commit+':'+file])
            blob=subprocess.check_output(['git','-C',str(mirror),'rev-parse',commit+':'+file],text=True).strip()
            target=out/f'{n:02d}_{file.replace("/","__")}'
            with target.open('xb') as handle:handle.write(raw)
            modules[file]={'path':str(target),'sha256':digest(target),'Git_blob_sha1':blob,'lines':len(raw.decode('utf-8').splitlines()),'base_commit':commit}
        for part in [record['candidate'],*record['gold'].values()]:
            module=modules[part['file']];assert module['Git_blob_sha1']==part['base_blob_sha1']
            text=Path(module['path']).read_text();lines=text.splitlines();line=int(part['function_id'].rsplit('@',1)[1])
            node=next(x for x in ast.walk(ast.parse(text)) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.lineno==line)
            code='\n'.join(lines[node.lineno-1:node.end_lineno])+'\n'
            assert code==part['full_source'] and hashlib.sha256(code.encode()).hexdigest()==part['full_source_sha256']
        runtime=json.loads(result.read_text());fid=record['identity']['function_id'];trace_witnesses=[]
        for trace in runtime.get('trace_files',[]):
            path=Path(trace['path']);assert digest(path)==trace['sha256']
            observed=json.loads(path.read_text());line=int(fid.rsplit('@',1)[1]);file,name=fid.split('::');name=name.rsplit('@',1)[0].split('.')[-1]
            entries=[entry for entry in observed['entries'] if entry[1]==file and entry[2] in {line,line-1,line-2} and entry[3]==name]
            if entries:trace_witnesses.append({'trace_path':str(path),'trace_sha256':trace['sha256'],'entry_witnesses':entries[:20]})
        receipts.append({'index':n,'identity':record['identity'],'record_sha256':object_sha(record),'sample_sha256':object_sha(sample),
                         'sample_actual_train_negative':True,'base_commit':commit,'full_candidate_and_gold_source_verified':True,
                         'modules':modules,'graph_path':str(graph),'graph_sha256':digest(graph),
                         'runtime_result_path':str(result),'runtime_result_sha256':digest(result),
                         'runtime_qualified':record['runtime_evidence']['qualified'],
                         'candidate_in_failed_context':fid in runtime.get('failed_test_function_ids',[]),
                         'candidate_in_bootstrap':fid in runtime.get('bootstrap_function_ids',[]),
                         'candidate_entry_raw_trace_witnesses':trace_witnesses})
    receipt={'status':'source_witnesses_anchored_not_label_review','at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
             'packet_path':str(packet),'packet_sha256':digest(packet),'samples_path':str(samples_path),'samples_sha256':digest(samples_path),
             'audit_script_sha256':digest(__file__),'cases':receipts,'pruner_test_decoded':False,'new_tests_run':0}
    path=out/'source_binding_audit.json'
    with path.open('x') as handle:json.dump(receipt,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print(json.dumps({'source_binding_audit_path':str(path),'sha256':digest(path),'cases':len(receipts)}))


if __name__=='__main__':main()
