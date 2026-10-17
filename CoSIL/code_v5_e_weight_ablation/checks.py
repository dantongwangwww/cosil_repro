"""Targeted numerical/gradient equivalence and val/test-boundary checks."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

from code_v5_e_weight_ablation.policy import ROOT, BASELINE, DATA, validate_runtime_config, read_metadata, protected_paths


def run_checks():
    import torch
    from code_v5.judge_models import reranker_loss, response_sft_loss
    from code_v5_e_weight_ablation.losses import (sample_weight, weighted_reranker_loss,
                                                  weighted_response_sft_loss)
    from code_v5_e_weight_ablation.report import read_val, summarize, route
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    check('protected input/source/baseline/current workbook paths exist before launch',
          all(p.is_file() for p in protected_paths() if p.name != 'CPU_checks.json'))
    class Dummy(torch.nn.Module):
        def __init__(self, logits):
            super().__init__(); self.logits = torch.nn.Parameter(logits.clone())
        def forward(self, **kwargs):
            return SimpleNamespace(logits=self.logits[:, -kwargs['logits_to_keep']:, :])
    def value_grad(function, logits, batch, **kw):
        model = Dummy(logits); loss = function(model, batch, **kw); loss.backward()
        return loss.detach(), model.logits.grad
    torch.manual_seed(19)
    logits = torch.randn(5, 8, 13)
    ids, mask = torch.zeros((5, 8), dtype=torch.long), torch.ones((5, 8), dtype=torch.long)
    labels = torch.tensor([1, 0, 0, 1, 0])
    batch = {'input_ids': ids, 'attention_mask': mask, 'labels': labels}
    a, ag = value_grad(reranker_loss, logits, batch, no_id=3, yes_id=7)
    b, bg = value_grad(weighted_reranker_loss, logits, batch, no_id=3, yes_id=7, sample_weights=[1]*5)
    check('reranker E=1 loss and gradients equal original', torch.allclose(a,b,atol=1e-7) and torch.allclose(ag,bg,atol=1e-7))
    weights = [1., .5, .5, 1., .5]
    _, wg = value_grad(weighted_reranker_loss, logits, batch, no_id=3, yes_id=7, sample_weights=weights)
    check('reranker E=.5 only halves E gradient; non-E coefficient unchanged', torch.allclose(wg, ag*torch.tensor(weights)[:,None,None],atol=1e-7))
    # Response targets differ in length; prompt/padding positions must stay masked.
    targets = torch.full((5, 8), -100, dtype=torch.long)
    for i, n in enumerate([2, 4, 1, 3, 2]):
        targets[i, -n:] = torch.arange(n) + 2
    sft = {'input_ids':ids, 'attention_mask':mask, 'labels':targets}
    a, ag = value_grad(response_sft_loss, logits, sft)
    b, bg = value_grad(weighted_response_sft_loss, logits, sft, sample_weights=[1]*5)
    check('response SFT E=1 token-normalized loss and gradients equal original', torch.allclose(a,b,atol=1e-6) and torch.allclose(ag,bg,atol=1e-7))
    _, wg = value_grad(weighted_response_sft_loss, logits, sft, sample_weights=weights)
    check('response SFT only scales E response tokens', torch.allclose(wg,ag*torch.tensor(weights)[:,None,None],atol=1e-7))
    check('response SFT ignored prompt positions have zero gradient', bool((wg[:, :3, :] == 0).all()))
    for kind, batch, loss, kwargs in [('reranker',batch,weighted_reranker_loss,{'no_id':3,'yes_id':7}),
                                      ('instruct',sft,weighted_response_sft_loss,{})]:
        full, full_grad = value_grad(loss,logits,batch,sample_weights=weights,**kwargs)
        denominator = len(weights) if kind=='reranker' else int((batch['labels'][:,1:]!=-100).sum())
        pieces=[]; gradient=torch.zeros_like(logits)
        for start in range(0,5,2):
            sub={k:v[start:start+2] for k,v in batch.items()}
            l,g=value_grad(loss,logits[start:start+2],sub,sample_weights=weights[start:start+2],**kwargs)
            size=len(sub['labels']) if kind=='reranker' else int((sub['labels'][:,1:]!=-100).sum())
            pieces.append(l*size/denominator);gradient[start:start+2]=g*size/denominator
        check(kind+' uneven microbatch accumulation equals fixed full-group denominator',
              torch.allclose(sum(pieces),full,atol=1e-6) and torch.allclose(gradient,full_grad,atol=1e-7))
    check('multi-family E/D overlap weighted once', sample_weight({'label':False,'label_sources':['e_log','e_bm25','D']},.5)==.5)
    check('non-E positive/D weights unchanged', all(sample_weight({'label':b,'label_sources':[s]},.5)==1 for b,s in [(True,'A'),(True,'C'),(False,'D')]))
    try:
        sample_weight({'label':True,'label_sources':['e_anchor']},.5)
        raise AssertionError('E positive must fail')
    except ValueError:
        checks.append('conflicting E-positive label rejected')
    check('fixed route endpoints preserved', [route(p) for p in [0,.6,.600001,.899999,.9,1]]==['reject','reject','gray','gray','retain','retain'])
    old = ast.parse((ROOT/'code_v5_expanded_resources_v3/train_judges.py').read_text())
    new = ast.parse((ROOT/'code_v5_e_weight_ablation/train_judges.py').read_text())
    old_functions={n.name:n for n in old.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    new_functions={n.name:n for n in new.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    names=set(old_functions)-{'train','main'}
    check('all '+str(len(names))+' helper functions preserve original AST including codec/val/selection/LoRA',
          all(ast.dump(old_functions[n],include_attributes=False)==ast.dump(new_functions[n],include_attributes=False) for n in names))
    from code_v5_e_weight_ablation.train_judges import validate_epoch
    try:
        validate_epoch(None,None,'instruct',[{'split':'test'}],'cpu',4096,split='test')
        raise AssertionError('test scoring must fail before model call')
    except PermissionError:
        checks.append('test scoring refused before model access')
    try:
        read_metadata(DATA/'pruner_test.jsonl')
        raise AssertionError('test decoder must fail')
    except PermissionError:
        checks.append('test sample metadata decoder refused before opening')
    truth_rows=[json.loads(x) for x in (DATA/'pruner_val.jsonl').read_text().splitlines() if x.strip()]
    truth={(x['instance_id'],x['function_id']):x for x in truth_rows}
    for kind, rejected in [('reranker',28),('instruct',33)]:
        p=BASELINE/'training'/kind
        summary=json.loads((p/'training_summary.json').read_text());epoch=summary['checkpoint_assessments']['best']['epoch']
        metrics=summarize(read_val(p/f'val_epoch_{epoch}.jsonl',truth))
        check(kind+' baseline AUC/accuracy and gold route counts reproduce',
              metrics['overall']==summary['checkpoint_assessments']['best']['val']['overall']
              and metrics['gold_routes_raw_low06_high09']['reject']==rejected)
        config=json.loads((p/'training_manifest.json').read_text());validate_runtime_config(config)
        bad=dict(config,learning_rate=1e-4)
        try:
            validate_runtime_config(bad);raise AssertionError('changed learning rate must fail')
        except RuntimeError:
            checks.append(kind+' non-E learning-rate change rejected')
    return {'passed':True,'checks':checks,'count':len(checks),'actual_model_loaded':False,
            'paid_api_calls':0,'test_labels_decoded_or_scored':False}


if __name__=='__main__':
    result=run_checks()
    target=ROOT/'results/v5_pruner/E_weight05_ablation_authorization_exploratory/CPU_checks.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
