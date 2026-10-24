import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from code_deepseek_direct import common as C
from code_deepseek_direct.runner import initial_messages, run_loop, protocol
from code_deepseek_direct.tools import RepoTools, TOOLS
from code_deepseek_direct.transport import Transport, estimated_cost


def reply(content=None,calls=None,model=C.MODEL,reasoning=None):
    message={'content':content,'role':'assistant'}
    if calls:message['tool_calls']=calls
    if reasoning:message['reasoning_content']=reasoning
    return {'model':model,'id':'synthetic','choices':[{'message':message,
        'finish_reason':'tool_calls' if calls else 'stop'}],
        'usage':{'prompt_tokens':100,'completion_tokens':20,'prompt_cache_hit_tokens':40}}


def call(arguments='{"path":"example.py"}'):
    return {'id':'synthetic-call','type':'function','function':{'name':'read_file','arguments':arguments}}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='direct_tests_',dir='/tmp')
        self.root=Path(self.temporary.name);self.run=self.root/'run';self.repo=self.root/'repo'
        self.repo.mkdir();(self.repo/'example.py').write_text('def example():\n    return 4\n')
        self.job=dict(instance_id='synthetic',repo='org/example',base_commit='synthetic-sha',
                      problem_statement='A synthetic issue with no labels.')
        self.patches=[patch.object(C,'RUN',self.run),patch.object(C,'WORK',self.root)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temporary.cleanup()

    def fake(self,responses):
        class Fake:
            def __init__(self):self.requests=[]
            def ask(self,request,turn):
                self.requests.append(copy.deepcopy(request))
                return responses[turn-1],{'usage':None,'cost':{'usd':None}}
        return Fake()

    def test_actual_tool_bytes_are_in_next_native_request(self):
        transport=self.fake([reply(calls=[call()]),reply('{"files":[],"functions":[]}')])
        with RepoTools(self.repo) as tools:result=run_loop(self.job,tools,transport,schemas=TOOLS)
        record=C.read(self.run/'tools/0001.json')
        tool=transport.requests[1]['messages'][-1]
        self.assertEqual(tool,dict(role='tool',tool_call_id='synthetic-call',content=record['wire_content']))
        self.assertIn('return 4',tool['content']);self.assertTrue(record['output']['ok'])
        self.assertEqual(record['output_sha256'],C.digest(json.loads(tool['content'])))
        self.assertEqual(result['model_turns'],2)
        for request in transport.requests:
            self.assertEqual(request['thinking'],{'type':'disabled'})
            self.assertEqual(request['max_tokens'],393216)
            self.assertEqual(request['tool_choice'],'auto')
        self.assertEqual(len(transport.requests[0]['messages']),2)

    def test_invalid_arguments_return_error_to_model(self):
        transport=self.fake([reply(calls=[call('{broken')]),reply('Finished without a candidate.')])
        with RepoTools(self.repo) as tools:run_loop(self.job,tools,transport,schemas=TOOLS)
        output=json.loads(transport.requests[1]['messages'][-1]['content'])
        self.assertFalse(output['ok']);self.assertIn('Invalid',output['error']['message'])

    def test_no_frozen_loop_or_total_budget(self):
        p=protocol()
        for name in ('cumulative_tokens_cap','wall_time_cap','turn_cap','cost_cap_usd'):
            self.assertIsNone(p[name])

    def test_only_clean_issue_inputs(self):
        messages=initial_messages(self.job)
        self.assertIn(self.job['problem_statement'],messages[1]['content'])
        with self.assertRaises(ValueError):initial_messages(dict(self.job,gold=['secret']))

    def client(self,raw):
        def handle(request):return httpx.Response(200,json=raw)
        return httpx.Client(base_url=C.API,transport=httpx.MockTransport(handle))

    def request(self):return dict(model=C.MODEL,thinking={'type':'disabled'},messages=[])

    def test_transport_saves_usage_and_refuses_paid_replay(self):
        with self.client(reply('Done',model='DeepSeek-V4.1-Flash-1017')) as client:
            transport=Transport(run=self.run,client=client)
            raw,receipt=transport.ask(self.request(),1)
            self.assertEqual(receipt['usage']['prompt_tokens'],100)
            self.assertTrue((self.run/'calls/0001/request.json').exists())
            with self.assertRaises(FileExistsError):transport.ask(self.request(),1)
        self.assertNotIn('Authorization',(self.run/'calls/0001/request.json').read_text())

    def test_thinking_contract_preserves_response_before_stop(self):
        with self.client(reply('Done',reasoning='Unexpected thinking')) as client:
            with self.assertRaises(RuntimeError):Transport(run=self.run,client=client).ask(self.request(),1)
        self.assertTrue((self.run/'calls/0001/result.json').is_file())

    def test_wrong_model_stops(self):
        with self.client(reply('Done',model='other-model')) as client:
            with self.assertRaises(RuntimeError):Transport(run=self.run,client=client).ask(self.request(),1)

    def test_usage_missing_is_not_zero_cost(self):
        self.assertIsNone(estimated_cost(None,'','')['usd'])
        u=dict(prompt_tokens=100,completion_tokens=20,prompt_tokens_details=None)
        c=estimated_cost(u,'2026-10-24T01:00:00+00:00','2026-10-24T01:01:00+00:00')
        self.assertEqual(c['price_tier'],'off_peak');self.assertEqual(c['estimate_or_upper'],'upper')
        self.assertAlmostEqual(c['usd'],(100*.15+20*.6)/1e6)


if __name__=='__main__':unittest.main()
