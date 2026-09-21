import sys
def pytest_sessionfinish(session, exitstatus):
    third = sorted(m for m in ('numpy','torch','boto3','pandas','scipy') if m in sys.modules)
    print('\nTHIRD_PARTY_LOADED:', third or 'none')
