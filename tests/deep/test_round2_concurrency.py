"""Round 2: concurrency. Mock model only."""
from __future__ import annotations

import copy
import itertools
import threading
import time

from fastapi.testclient import TestClient

from conftest import wait_job

_n = itertools.count()


def test_R2B_005_delete_during_saves_is_clean(app, client, make_project, projects_root):
    """DELETE while the page is saving: the answer must be 200 (gone) or 409 (busy), never 500, and no folder may be left behind."""
    bad = []
    for _ in range(10):
        pid = make_project("arnolfini-from-books", f"t_r2_del{next(_n)}")
        S = f"/api/projects/{pid}"
        r = client.post(S + "/outline/generate", json={"model": "mock"})
        assert wait_job(client, r.json()["job_id"])["state"] == "done"
        o = client.get(S + "/outline").json()
        stop = threading.Event()
        codes = []

        def writer():
            cl = TestClient(app, raise_server_exceptions=False)
            rev, i = o["rev"], 0
            while not stop.is_set():
                od = copy.deepcopy(o["outline"])
                od["thesis"] = f"x{i}"
                i += 1
                rr = cl.put(S + "/outline", json={"outline": od, "base_rev": rev})
                codes.append(rr.status_code)
                if rr.status_code == 200:
                    rev = rr.json()["rev"]
                else:
                    g = cl.get(S + "/outline")
                    if g.status_code == 200:
                        rev = g.json()["rev"]
        ts = [threading.Thread(target=writer) for _ in range(3)]
        [t.start() for t in ts]
        time.sleep(0.15)
        d = client.delete(S + f"?confirm={pid}")
        time.sleep(0.3)
        stop.set()
        [t.join() for t in ts]
        if d.status_code not in (200, 409):
            bad.append((pid, "delete", d.status_code))
        if 500 in codes:
            bad.append((pid, "a save answered 500"))
        if d.status_code == 200 and (projects_root / pid).exists():
            bad.append((pid, "folder resurrected: " + ",".join(str(x.relative_to(projects_root / pid)) for x in (projects_root / pid).rglob("*"))[:80]))
    assert not bad, bad
