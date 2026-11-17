"""Fail fast on native-tool infrastructure rejection, never reclassify it as a miss."""
from pathlib import Path
import argparse
from code_multiswe_java_20261117.controller import Controller as Original
from code_multiswe_java_20261117.common import read,write

NATIVE_SERVER_ERRORS=('requires --enable-auto-tool-choice','--tool-call-parser to be set')


def native_server_rejection(directory):
    for path in Path(directory).glob('samples/sample_*/requests/*response.txt'):
        text=path.read_text(errors='replace')
        if any(phrase in text for phrase in NATIVE_SERVER_ERRORS):return str(path)
    return None


class Controller(Original):
    def run_arm(self,row,arm,stage,public,shared=None):
        result=super().run_arm(row,arm,stage,public,shared)
        if arm=='locagent':
            evidence=native_server_rejection(self.root/'run'/row['instance_id']/arm)
            if evidence:
                write(self.root/'audits/native_server_fail_fast.json',{'status':'FAIL','evidence':evidence,
                    'reason':'Server configuration rejection; no automatic replay or model capability classification'})
                raise RuntimeError('Native-tool server rejected request: '+evidence)
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--main-model',type=Path,required=True);p.add_argument('--judge-socket',type=Path,required=True)
    p.add_argument('--canary-only',action='store_true');a=p.parse_args()
    Controller(a.root,a.main_model,a.judge_socket).run(canary_only=a.canary_only)


if __name__=='__main__':main()
