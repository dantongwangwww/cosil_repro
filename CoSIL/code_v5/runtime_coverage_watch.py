"""Lightweight persistent watcher that audits only after the collector exits."""
import fcntl
import json
import os
import time
from code_v5.runtime_coverage import OUT, CASES, now, write
from code_v5.runtime_coverage_finalize import main as finalize


def main():
    status = {'started_at': now(), 'pid': os.getpid(), 'state': 'waiting_for_300_completed_cases'}
    write(OUT / 'finalizer_status.json', status)
    while True:
        count = len(list(CASES.glob('*/result.json')))
        status.update(updated_at=now(), completed=count)
        write(OUT / 'finalizer_status.json', status)
        if count == 300:
            with (OUT / 'driver.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    time.sleep(10)
                    continue
                try:
                    finalize()
                    status.update(state='final_audit_passed', finished_at=now())
                except Exception as exc:
                    status.update(state='final_audit_failed', error=repr(exc), finished_at=now())
                    write(OUT / 'finalizer_status.json', status)
                    raise
                write(OUT / 'finalizer_status.json', status)
                return
        time.sleep(10)


if __name__ == '__main__':
    main()
