import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from code_deepseek_direct import common as C
from code_deepseek_direct.continuation import remaining,next_budget,continue_loop
from code_deepseek_direct.tools import RepoTools
from code_deepseek_direct.tests.test_runner import reply,call


class ContinuationTests(unittest.TestCase):
    def test_provider_remaining_not_a_total_token_cap(self):
        error={'error':{'message':"This model's maximum context length is 1048576 tokens. However, you requested 1048678 tokens (655462 in the messages, 393216 in the completion)."}}
        self.assertEqual(remaining(error),(393114,655462,393216))
        with self.assertRaises(RuntimeError):remaining({'error':{'message':'other failure'}})

    def test_next_budget_retains_all_messages(self):
        messages=[dict(role='tool',content='完整结果'*100)]
        frozen=copy.deepcopy(messages)
        budget=next_budget({'usage':{'prompt_tokens':700000}},messages)
        self.assertGreater(budget,300000);self.assertLess(budget,393216)
        self.assertEqual(messages,frozen)

    def test_resume_preserves_prefix_and_real_tool_delivery(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as directory:
            root=Path(directory);repo=root/'repo';repo.mkdir();(repo/'example.py').write_text('def example():\n    return 4\n')
            messages=[dict(role='user',content='Original neutral issue')];prefix=copy.deepcopy(messages)
            class Fake:
                def __init__(self):self.requests=[]
            fake=Fake()
            def ask(request,turn):
                fake.requests.append(copy.deepcopy(request))
                return (reply(calls=[call()]) if turn==609 else reply('Final localization')),{'usage':{'prompt_tokens':700000}}
            fake.ask=ask
            with patch.object(C,'RUN',root/'run'),patch.object(C,'WORK',root),RepoTools(repo) as tools:
                result=continue_loop(fake,tools,messages,608,615,393114)
                record=C.read(root/'run/tools/0616.json')
            self.assertEqual(fake.requests[0]['messages'],prefix)
            self.assertEqual(fake.requests[1]['messages'][:1],prefix)
            self.assertEqual(fake.requests[1]['messages'][-1]['content'],record['wire_content'])
            self.assertEqual(result['final_response'],'Final localization')
            self.assertEqual(result['last_http_turn'],610)
            self.assertEqual(fake.requests[0]['thinking'],{'type':'disabled'})

    def test_context_rejection_reduces_only_output_reservation(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as directory:
            root=Path(directory);messages=[dict(role='user',content='Unchanged issue')];requests=[]
            class Fake:
                def ask(self,request,turn):
                    requests.append(copy.deepcopy(request))
                    if turn==608:
                        C.write(C.RUN/'calls/0608/attempt_0_error.json',{'error':{'message':
                          "maximum context length is 1048576 tokens (655462 in the messages, 393216 in the completion)"}})
                        raise RuntimeError('DeepSeek API HTTP 400')
                    return reply('Finished'),{'usage':{'prompt_tokens':655462}}
            with patch.object(C,'RUN',root/'run'),patch.object(C,'WORK',root):
                result=continue_loop(Fake(),None,messages,607,615,393216)
            self.assertEqual(result['last_http_turn'],609)
            self.assertEqual(requests[0]['messages'],requests[1]['messages'])
            self.assertEqual(requests[1]['max_tokens'],393114)


if __name__=='__main__':unittest.main()
