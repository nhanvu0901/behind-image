import os

os.environ["BTI_NO_REAL_MODELS"] = "1"


def pytest_configure(config):
    config.addinivalue_line("markers", "server: real machine probes; only on the Windows server, light and read-only")
