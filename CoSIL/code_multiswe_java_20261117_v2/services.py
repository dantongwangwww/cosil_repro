"""Restore previously verified LocAgent Hermes flags on the shared Qwen server.

No model, tokenizer, sampling or search adaptation changes. The text-only
CoSIL endpoint and native LocAgent endpoint share the same pinned weights.
"""
from pathlib import Path
import argparse
import json
import time
import urllib.request
from unittest.mock import patch

from code_multiswe_java_20261117 import services as old
from code_multiswe_java_20261117.common import ROOT,RUN,read,write

BASE_MAIN_COMMAND=old.base.main_command
DEFAULT_ROOT=ROOT/'results/multiswe_java_qwen3_20261117_v2'


def native_command(model):
    argv=BASE_MAIN_COMMAND(model)
    if '--enable-auto-tool-choice' in argv or '--tool-call-parser' in argv:
        raise RuntimeError('Base service command changed; independently review tool parser')
    return argv+['--enable-auto-tool-choice','--tool-call-parser','hermes']


def native_http_probe(work):
    """One separate public toy readiness request, not a benchmark prediction."""
    payload={'model':'qwen3-8b','messages':[{'role':'user','content':'Call probe once with message ready.'}],
        'tools':[{'type':'function','function':{'name':'probe','description':'Return a readiness marker; no code execution.',
            'parameters':{'type':'object','properties':{'message':{'type':'string'}},'required':['message']}}}],
        'tool_choice':'auto','max_tokens':64,'temperature':0,'seed':0,'stream':False,
        'parallel_tool_calls':False,'chat_template_kwargs':{'enable_thinking':False}}
    folder=Path(work)/'native_http_readiness';folder.mkdir(exist_ok=False)
    write(folder/'request.json',payload);began=time.monotonic()
    req=urllib.request.Request('http://127.0.0.1:7343/v1/chat/completions',data=json.dumps(payload).encode(),
        headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=120) as response:
        raw=response.read();status=response.status
    result=json.loads(raw);write(folder/'response.json',result)
    if status!=200 or result.get('model')!='qwen3-8b' or not isinstance(result.get('usage'),dict):
        raise RuntimeError('Native HTTP readiness rejected or usage unknown')
    write(folder/'receipt.json',{'status':'HTTP_NATIVE_REQUEST_ACCEPTED','http_status':status,
        'usage':result['usage'],'seconds':time.monotonic()-began,'thinking_enabled':False,
        'tool_calls_returned':len(result['choices'][0]['message'].get('tool_calls') or []),
        'benchmark_result':False,'real_tools_executed':False,'billable_api_usd':0.0})


class Supervisor(old.Supervisor):
    def spawn(self,role,argv,env):
        if role in ('canary','full'):
            argv=list(argv);pos=argv.index('code_multiswe_java_20261117.controller')
            argv[pos]='code_multiswe_java_20261117_v2.controller'
        if role=='canary':native_http_probe(self.work)
        return super().spawn(role,argv,env)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--run',action='store_true');a=p.parse_args()
    if not a.run:
        print(json.dumps({'main_command':native_command(old.MAIN_MODEL),'services_started':False}));return
    supervisor=Supervisor(a.root)
    try:
        with patch.object(old.base,'main_command',native_command):supervisor.run()
    except BaseException as error:
        supervisor.status('STOPPED',error=type(error).__name__+': '+str(error));raise
    finally:supervisor.shutdown()


if __name__=='__main__':main()
