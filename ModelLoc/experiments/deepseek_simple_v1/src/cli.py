import argparse,sys
from .common import COSIL
sys.path.insert(0,str(COSIL))

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','preflight','test-chain','run-localization','report'])
    p.add_argument('--cohort',choices=['smoke','lite_pilot'],default='smoke');a=p.parse_args()
    if a.command=='prepare':
        from .dataset_adapter import prepare
        prepare()
    elif a.command=='preflight':
        from .preflight import run
        print({'frozen':run()['run_id']})
    elif a.command=='test-chain':
        from .test_chain import run
        run()
    elif a.command=='run-localization':
        from .execution import run
        run(a.cohort)
    elif a.command=='report':
        from .reporting import run
        run(a.cohort)

if __name__=='__main__':main()
