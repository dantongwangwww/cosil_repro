"""Pure command/error tests; no service or model starts."""
from pathlib import Path
import tempfile
import unittest
from .services import native_command,BASE_MAIN_COMMAND
from .controller import native_server_rejection


class RecoveryTests(unittest.TestCase):
    def test_only_restore_native_tool_server_flags(self):
        model='/synthetic/model';old=BASE_MAIN_COMMAND(model);new=native_command(model)
        self.assertEqual(new[:-3],old)
        self.assertEqual(new[-3:],['--enable-auto-tool-choice','--tool-call-parser','hermes'])
        self.assertEqual(new[new.index('--max-num-seqs')+1],'1')
        self.assertEqual(new[new.index('--max-model-len')+1],'65536')

    def test_infrastructure_rejection_recognized(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'samples/sample_01/requests/request_001_attempt_1_response.txt'
            p.parent.mkdir(parents=True);p.write_text('"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set')
            self.assertEqual(native_server_rejection(td),str(p))

    def test_model_tool_error_not_a_server_parser_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'samples/sample_01/requests/request_001_attempt_1_response.txt'
            p.parent.mkdir(parents=True);p.write_text('{"tool_calls":[],"content":"unknown function"}')
            self.assertIsNone(native_server_rejection(td))


if __name__=='__main__':unittest.main()
