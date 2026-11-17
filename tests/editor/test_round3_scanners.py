"""R3B-002: the hand-written scanners are linear (and bounded) on hostile input; R3B-012/013: the model list can not break a job."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import pytest

from bti.editor.common import DepthLimitMiddleware, MAX_BODY_DEPTH
from bti.script import models as models_mod, parse, validate
from bti import textfold


def timed(f, *a):
    t = time.perf_counter()
    r = f(*a)
    return r, time.perf_counter() - t


def _best(f, body, n=3):
    return min(timed(f, body)[1] for _ in range(n))


def _legit(n):
    return json.dumps({"shots": [{"id": "s%d" % i, "p": {"c": [{"at": {"t": 1.0}}] * 3}, "n": 'say "x"'} for i in range(n)]}).encode()


def test_depth_scan_is_linear_and_still_right():
    m = DepthLimitMiddleware(None)
    # linearity as a ratio (best of three per size): ten times the body takes far less than twenty-five times as long
    small, big = _legit(2_000), _legit(20_000)
    assert len(big) > 2_000_000 and len(big) > 9 * len(small)
    t_small, t_big = _best(m.too_deep, small), _best(m.too_deep, big)
    assert t_big < 25 * max(t_small, 0.001), (t_small, t_big)
    # a generous absolute cap: the quadratic scan took a minute for 160 KB, so this still fails loudly if it comes back
    assert m.too_deep(big) is False and t_big < 0.5, t_big
    for n in (20_000, 160_000, 1_000_000):
        assert timed(m.too_deep, b'"' + b'\\"' * n)[1] < 1.5
    assert m.too_deep(b"[" * (MAX_BODY_DEPTH + 1)) and not m.too_deep(b"[" * MAX_BODY_DEPTH + b"]" * MAX_BODY_DEPTH)
    assert not m.too_deep(b'["' + b"[" * 500 + b'"]')            # brackets inside a string do not count
    assert m.too_deep(b"[" * 30 + b'"' + b"x" * 700_000 + b'"' + b"[" * 30)    # a string longer than a chunk
    assert not m.too_deep(b'"a",' * 500_000)


def test_depth_scan_never_holds_the_event_loop_for_long():
    m = DepthLimitMiddleware(None)
    worst = 0.0

    async def ticker(stop):
        nonlocal worst
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0)
            now = time.perf_counter()
            worst = max(worst, now - last)
            last = now

    async def main():
        stop = asyncio.Event()
        tk = asyncio.create_task(ticker(stop))
        await m.too_deep_async(b'"a",' * 2_000_000)
        stop.set()
        await tk
    asyncio.run(main())
    assert worst < 0.1, worst


def test_body_over_8_mb_is_413():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.add_middleware(DepthLimitMiddleware)

    @app.post("/x")
    def x(body: dict):
        return {"ok": True}
    c = TestClient(app)
    assert c.post("/x", content=b'{"a":"' + b"x" * (8 * 1024 * 1024) + b'"}', headers={"content-type": "application/json"}).status_code == 413
    assert c.post("/x", json={"a": "x" * 1000}).status_code == 200


@pytest.mark.parametrize("text", ["## a" + " " * 30000 + "x", "\n\n" * 30000 + "x", "word count" + " " * 30000 + "x",
                                  "hook" + " " * 30000 + "x", ">> show: " + "a, " * 30000, "hook options" + " " * 30000,
                                  "facts" + " " * 30000, "(pause" * 30000, "## c01 " + "\t" * 30000 + "x"])
def test_script_parsers_and_validators_are_linear_on_hostile_text(text):
    for f in (parse.parse_script, parse.parse_outline, validate.markup_in, textfold.fold, textfold.tokens):
        _, t = timed(f, text)
        assert t < 1.0, (f.__name__, text[:12], t)


def test_heading_parse_is_unchanged():
    assert parse.HEAD_RE.match("## c01 COLD OPEN ##").group(1) == "c01 COLD OPEN"
    assert parse.HEAD_RE.match("  ### x  ").group(1) == "x"
    assert parse.HEAD_RE.match("#### x") is None and parse.HEAD_RE.match("# x") is None and parse.HEAD_RE.match("##x") is None


# ------------------------------------------------------------------ R3B-012 / R3B-013
@pytest.fixture()
def fake_agy(tmp_path, monkeypatch):
    models_mod.reset_cache()
    mf = tmp_path / "models.json"
    mf.write_text(json.dumps([{"id": "mock", "provider": "mock", "label": "Mock"},
                              {"id": "agy", "provider": "antigravity", "label": "Antigravity", "default": True}]))
    monkeypatch.setenv("BTI_MODELS_FILE", str(mf))

    def make(script: str):
        py = tmp_path / "fake_agy.py"                      # a python script started through the interpreter, both systems
        py.write_text("import sys, time\n" + script + "\n", encoding="utf-8")
        if os.name == "nt":
            exe = tmp_path / "agy.cmd"
            exe.write_text(f'@"{sys.executable}" "{py}" %*\r\n', encoding="utf-8")
        else:
            exe = tmp_path / "agy"
            exe.write_text(f"#!{sys.executable}\n" + py.read_text(encoding="utf-8"), encoding="utf-8")
            exe.chmod(0o755)
        monkeypatch.setenv("BTI_AGY_BIN", str(exe))
        models_mod.reset_cache()
        return exe
    yield make
    models_mod.reset_cache()


def test_non_utf8_output_is_a_failure_answer_not_an_exception(fake_agy):
    fake_agy("sys.stdout.buffer.write(b'\\xf6\\xff\\n')")
    ms = models_mod.public_models()
    agy = next(m for m in ms if m["provider"] == "antigravity")
    assert agy["agy"]["ok"] is False
    t = time.time()
    models_mod.public_models()                                  # cached failure: no second CLI call
    assert time.time() - t < 0.5


def test_valid_rows_with_odd_bytes_and_duplicates(fake_agy):
    fake_agy("sys.stdout.buffer.write(b'a\\tA \\xf6\\nb\\tB\\na\\tdup\\n../x\\tbad\\n')")
    rows, err = models_mod.agy_models()
    assert err is None and [r["slug"] for r in rows] == ["a", "b"]


def test_a_mock_job_never_calls_the_cli(fake_agy, tmp_path):
    marker = tmp_path / "called"
    fake_agy(f"open({str(marker)!r}, 'w').close(); time.sleep(3); print('x\\tX')")
    t = time.time()
    assert models_mod.resolve("mock")["id"] == "mock"
    assert models_mod.get_model("mock")["provider"] == "mock"
    assert time.time() - t < 0.5 and not marker.exists()
    spec = models_mod.resolve("agy:some-slug")                    # no fresh list: built from the slug, still no CLI call
    assert spec["model"] == "some-slug" and not marker.exists()


def test_slug_is_checked_against_a_fresh_list(fake_agy):
    fake_agy("print('x\\tX')")
    models_mod.agy_models()
    assert models_mod.resolve("agy:x")["model"] == "x"
    assert models_mod.resolve("agy:zzz") is None


def test_no_lock_is_held_while_the_cli_runs(fake_agy):
    import threading
    fake_agy("time.sleep(2); print('x\\tX')")
    th = threading.Thread(target=models_mod.agy_models)
    th.start()
    time.sleep(0.4)
    t = time.time()
    assert models_mod.resolve("mock")["id"] == "mock" and models_mod._cached()[0] is False
    assert time.time() - t < 0.3
    th.join()
