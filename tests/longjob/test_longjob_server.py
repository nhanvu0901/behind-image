"""Light, read-only checks of the real probes. Only on the Windows server; never touches D:\\bench."""
import os

import pytest

from bti.longjob.heavy import SystemProbes

pytestmark = [pytest.mark.server, pytest.mark.skipif(os.name != "nt", reason="the real probes are checked on the server")]


def test_free_virtual_memory_is_sane():
    kb = SystemProbes().free_virtual_kb()
    assert isinstance(kb, int) and 1_000_000 < kb < 200_000_000        # between 1 GB and 200 GB, in KB


def test_process_list_is_sane():
    p = SystemProbes()
    procs = p.processes()
    assert len(procs) > 20
    mine = [x for x in procs if x.pid == os.getpid()]
    assert mine and "python" in mine[0].name.lower() and mine[0].ppid > 0
    assert all(isinstance(x.pid, int) and isinstance(x.cmdline, str) for x in procs)


def test_pid_alive_and_host():
    p = SystemProbes()
    assert p.pid_alive(os.getpid()) is True
    assert p.pid_alive(0) is False
    assert p.pid_alive(4_000_000) is False
    assert p.host() and p.own_pid() == os.getpid()
