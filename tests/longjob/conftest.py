def pytest_configure(config):
    config.addinivalue_line("markers", "server: real machine probes; only on the Windows server, light and read-only")
