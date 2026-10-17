"""CPU-only progress document refresh while the persistent scheduler runs."""
import time
from code_v6.common import OUT,read
from code_v6.report_progress import run

def main():
    state=OUT/'T3_round1_exploratory/race_status.json'
    while True:
        run()
        if state.exists() and read(state)['stage'] in ['first_round_complete_awaiting_user','first_round_has_failures']:break
        time.sleep(45)

if __name__=='__main__':main()
