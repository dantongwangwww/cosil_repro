"""Test context and actual pytest outcome metadata for runtime coverage."""
import pytest
import runtime_coverage_probe as probe


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    probe.set_context(item.nodeid)
    yield
    probe.set_context('<bootstrap>')


def pytest_runtest_logreport(report):
    probe.REPORTS.append({'nodeid': report.nodeid, 'when': report.when,
                          'outcome': report.outcome, 'backend': 'pytest',
                          'message': str(report.longrepr)[:20000] if report.failed else ''})


def pytest_collectreport(report):
    if report.failed:
        probe.REPORTS.append({'nodeid': report.nodeid, 'when': 'collect',
                              'outcome': 'collection_error', 'backend': 'pytest',
                              'message': str(report.longrepr)[:20000]})
