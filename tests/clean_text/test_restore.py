"""The restore tool for the machine-translated book, tested with the `mock` provider and canned answers on invented pages.
No real model, no network, no real book text."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import restore_helpers as H  # noqa: E402
from bti.script.providers import ProviderError, mock  # noqa: E402
from tools.clean_text.restore import __main__ as cli  # noqa: E402
from tools.clean_text.restore import checks, run as R  # noqa: E402
from tools.clean_text.restore.pages import parse_page  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _mock_clean():
    mock.CALLS.clear()
    mock.clear_canned()
    yield
    mock.clear_canned()


@pytest.fixture
def book(tmp_path):
    clean = tmp_path / "clean"
    out = tmp_path / "out"
    H.write_clean(clean)

    def make(**kw) -> R.Settings:
        args = dict(book_id="inv_book", book_title="An Invented Book", works=H.WORKS, clean_dir=clean, out_dir=out,
                    model_id="mock", log=lambda s: None)
        args.update(kw)
        return R.Settings(**args)
    make.clean, make.out = clean, out
    return make


def report(out: Path) -> dict:
    return json.loads((out / "report.json").read_text(encoding="utf-8"))


def read(p: Path) -> str:
    return p.read_bytes().decode("utf-8")


# ----------------------------------------------------------------- a good work
def test_good_work_is_written(book):
    mock.set_canned([H.answer([1, 2, 3])])
    res = R.restore_book(book(only={1}))
    assert res["ok"] == [1] and res["failed"] == [], json.dumps(report(book.out)["works"], indent=1)
    assert len(mock.CALLS) == 1
    out = book.out
    p1 = read(out / "page_0001.txt")
    assert "Pell's lamp-lighting man" in p1 and "Bel" not in p1.replace("Pell", "")
    # structural lines are as they were; the layout of blank lines is the original's
    orig = H.PAGE1.split("\n")
    assert p1.split("\n")[:5] == orig[:5]
    assert [i.kind for i in parse_page(p1)] == [i.kind for i in parse_page(H.PAGE1)]
    assert p1.count("\n") == H.PAGE1.count("\n") + 0 or abs(p1.count("\n") - H.PAGE1.count("\n")) <= 2
    p2 = read(out / "page_0002.txt")
    assert "[caption] Odran Pell, The Lamplighter (1871)" in p2
    assert p2.rstrip().endswith("[continues]")
    assert "[quote] The lamps are lit.\n[quote] The ladder is still." in p2
    # the plate page is copied byte for byte
    assert read(out / "page_0003.txt") == H.PAGE3
    rep = report(out)
    w = rep["works"]["1"]
    assert w["ok"] is True and w["result"] == "ok" and w["model"] == "mock" and w["attempts"] == 1
    assert {"from": "Bel", "to": "Pell"} in w["names"] and {"from": "Odran Bel", "to": "Odran Pell"} in w["names"]
    assert w["unclear"] == 1 and w["unclear_by_page"] == {"page_0001": 1}
    assert 0.9 < w["length_ratio"] < 1.2 and isinstance(w["seconds"], float)
    assert w["input_hash"] and rep["summary"]["ok"] == 1 and rep["summary"]["not_run"] == 2
    assert not (out / "_failed").exists()


def test_prompt_given_to_the_model(book):
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))
    prompt = mock.CALLS[0]["user"]
    assert "{{" not in prompt
    for needle in ("ADD NOTHING, DROP NOTHING", "[[?", "=== names ===", "=== page_0001 ===", "=== page_0002 ===",
                   "Odran Pell", "An Invented Book", "old form => new form"):
        assert needle in prompt
    assert "=== page_0003 ===" not in prompt          # a plate is not sent
    assert H.P1 in prompt and H.P5 in prompt


def test_whole_book_and_plate_only_work(book):
    mock.set_canned([H.answer([1, 2, 3]), H.answer([4, 5])])
    res = R.restore_book(book())
    assert res["ok"] == [1, 2, 3] and res["failed"] == []
    assert len(mock.CALLS) == 2                      # work 3 has no prose: no call
    rep = report(book.out)
    assert rep["works"]["3"]["note"].startswith("no prose")
    assert read(book.out / "page_0006.txt") == H.PAGE6
    s = rep["summary"]
    assert s["ok"] == 3 and s["failed"] == 0 and s["not_run"] == 0 and s["unclear_passages"] == 1
    assert s["names_all"]["Bel => Pell"] == 2


# ----------------------------------------------------------------- failures
def drop_paragraph(text: str) -> str:
    return text.replace(H.fix(H.P2) + "\n\n", "") if H.fix(H.P2) in text else text


def failed(book, answers, **kw):
    mock.set_canned(answers)
    res = R.restore_book(book(only={1}, **kw))
    assert res["failed"] == [1], res
    return report(book.out)["works"]["1"]


def test_dropped_paragraph_fails_after_the_retry(book):
    bad = H.answer([1, 2, 3], transform=lambda t: drop_paragraph(H.fix(t)))
    w = failed(book, [bad, bad])
    assert w["ok"] is False and w["result"] == "failed_checks" and w["attempts"] == 2
    assert any("2 paragraphs returned, the original has 3" in f for f in w["failures"])
    assert any("probably missing" in f for f in w["failures"])
    assert len(mock.CALLS) == 2
    # nothing of the work was written, the raw answers are kept for the analyst
    assert not (book.out / "page_0001.txt").exists() and not (book.out / "page_0003.txt").exists()
    assert (book.out / "_failed" / "work_001_try1.txt").is_file() and (book.out / "_failed" / "work_001_try2.txt").is_file()


def test_changed_structural_line_fails(book):
    def alter(t):
        t = H.fix(t).replace("# 01 Odran Pell, The Lamplighter", "# 01 The Man Who Lit the Lamps")
        return t.replace("[caption] Odran Pell, The Lamplighter (1871)", "[caption] A picture of a lamplighter, painted in 1872")
    bad = H.answer([1, 2, 3], transform=alter)
    w = failed(book, [bad, bad])
    msg = " ".join(w["failures"])
    assert "structural line [#] was rewritten" in msg
    assert "structural line [caption]" in msg and "numbers changed" in msg


def test_changed_page_type_and_invented_tag_fail(book):
    bad = H.answer([1, 2, 3], transform=lambda t: H.fix(t).replace("[page-type] body", "[page-type] plate", 1)
                   .replace("[meta] (1871)", "[note] (1871)"))
    w = failed(book, [bad, bad])
    msg = " ".join(w["failures"])
    assert "structural lines differ" in msg or "first difference" in msg


def test_page_returned_twice_fails(book):
    one = H.answer([1, 2, 3], names=None)
    page1 = one.split("=== page_0002 ===")[0]
    bad = page1 + one + "\n=== names ===\nBel => Pell\n"
    w = failed(book, [bad, bad])
    assert any("page_0001 was returned 2 times" in f for f in w["failures"])


def test_far_too_short_fails(book):
    def shorten(t):
        out = []
        for line in H.fix(t).split("\n"):
            out.append(line[:len(line) // 4] + "." if len(line) > 200 else line)
        return "\n".join(out)
    bad = H.answer([1, 2, 3], transform=shorten)
    w = failed(book, [bad, bad])
    msg = " ".join(w["failures"])
    assert "too short: something was dropped" in msg and "of its original length" in msg


def test_far_too_long_fails(book):
    def pad(t):
        return "\n".join(l + " " + l if len(l) > 200 else l for l in H.fix(t).split("\n"))
    w = failed(book, [H.answer([1, 2, 3], transform=pad)] * 2)
    assert "something was added" in " ".join(w["failures"])


def test_default_mock_answer_is_rejected(book):
    w = failed(book, [])                     # the mock answers "mock response"
    assert any("missing page(s): page_0001, page_0002" in f for f in w["failures"])
    assert any("names" in f for f in w["failures"])
    assert w["warnings"] == [] or isinstance(w["warnings"], list)


def test_retry_path_succeeds_and_lists_the_failures(book):
    bad = H.answer([1, 2, 3], transform=lambda t: drop_paragraph(H.fix(t)))
    good = H.answer([1, 2, 3])
    mock.set_canned([bad, good])
    res = R.restore_book(book(only={1}))
    assert res["ok"] == [1]
    w = report(book.out)["works"]["1"]
    assert w["attempts"] == 2 and w["ok"] is True and "failures" not in w
    assert [c["retry"] for c in mock.CALLS] == [False, True]
    second = mock.CALLS[1]["user"]
    assert R.RETRY_HEAD in second and "2 paragraphs returned, the original has 3" in second
    assert second.startswith(mock.CALLS[0]["user"])          # the same prompt, then the problems
    assert "Pell's lamp-lighting man" in read(book.out / "page_0001.txt")
    assert not (book.out / "_failed").exists() or not list((book.out / "_failed").glob("work_001*"))


def test_instruction_lines_leaking_into_the_answer_fail(book):
    template = R.PROMPT_PATH.read_text(encoding="utf-8")
    leak = "THE MOST IMPORTANT RULE: ADD NOTHING, DROP NOTHING"
    assert checks.norm_line(leak) in checks.prompt_lines_of(template)
    leaky = H.answer([1, 2, 3], transform=lambda t: H.fix(t).replace("The artist Odran Pell", leak + " The artist Odran Pell"))
    w = failed(book, [leaky, leaky])
    assert any("lines of the instructions came back" in f for f in w["failures"])
    in_names = H.answer([1, 2, 3], names=H.NAMES + "\n" + leak)
    mock.clear_canned()
    w = failed(book, [in_names, in_names], force=True)
    assert any("names block" in f for f in w["failures"])


def test_provider_errors_fail_only_that_work(book):
    calls = []

    def flaky(spec, system, user, **kw):
        calls.append(user)
        if len(calls) <= 2:
            raise ProviderError("timeout", "no answer in time")
        return H.answer([4, 5])
    res = R.restore_book(book(only={1, 2}, complete=flaky))
    assert res["failed"] == [1] and res["ok"] == [2]
    rep = report(book.out)["works"]
    assert rep["1"]["result"] == "failed_model_call" and "timeout" in rep["1"]["failures"][0]
    assert rep["1"]["attempts"] == 2
    assert calls[0] == calls[1]                           # no failure list to give: the same prompt again


def test_one_provider_error_then_good_answer(book):
    n = []

    def once(spec, system, user, **kw):
        n.append(1)
        if len(n) == 1:
            raise ProviderError("rate_limit", "slow down")
        return H.answer([1, 2, 3])
    res = R.restore_book(book(only={1}, complete=once))
    assert res["ok"] == [1] and report(book.out)["works"]["1"]["attempts"] == 2


def test_missing_input_page_is_reported(book):
    (book.clean / "page_0002.txt").unlink()
    res = R.restore_book(book(only={1}))
    assert res["failed"] == [1] and not mock.CALLS
    assert report(book.out)["works"]["1"]["result"].startswith("input_missing: page_0002")


# ----------------------------------------------------------------- resume
def test_resume_skips_done_works_and_redoes_changed_ones(book):
    mock.set_canned([H.answer([1, 2, 3]), H.answer([4, 5])])
    R.restore_book(book())
    assert len(mock.CALLS) == 2
    before = read(book.out / "page_0001.txt")
    res = R.restore_book(book())                          # nothing new: no call at all
    assert res["skipped"] == [1, 2, 3] and res["ok"] == [] and len(mock.CALLS) == 2
    assert read(book.out / "page_0001.txt") == before
    # the input of work 2 changes: only work 2 is done again
    (book.clean / "page_0004.txt").write_bytes((H.PAGE4 + "\nA new closing paragraph about nothing in particular.\n").encode())
    pages = dict(H.PAGES)
    pages[4] = H.PAGE4 + "\nA new closing paragraph about nothing in particular.\n"
    mock.set_canned([H.answer([4, 5], pages=pages)])
    res = R.restore_book(book())
    assert res["ok"] == [2] and res["skipped"] == [1, 3] and len(mock.CALLS) == 3


def test_resume_redoes_work_with_missing_output_and_failed_works(book):
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))
    (book.out / "page_0002.txt").unlink()
    mock.set_canned([H.answer([1, 2, 3])])
    assert R.restore_book(book(only={1}))["ok"] == [1]
    assert (book.out / "page_0002.txt").is_file()
    # a failed work is tried again by the next run
    mock.clear_canned()
    res = R.restore_book(book(only={2}))
    assert res["failed"] == [2]
    mock.set_canned([H.answer([4, 5])])
    assert R.restore_book(book(only={2}))["ok"] == [2]
    assert report(book.out)["works"]["2"]["ok"] is True
    n = len(mock.CALLS)
    mock.set_canned([H.answer([1, 2, 3])])
    assert R.restore_book(book(only={1}, force=True))["ok"] == [1] and len(mock.CALLS) == n + 1


def test_report_and_pages_are_written_atomically(book, monkeypatch):
    seen = []
    real = R.atomic_replace
    monkeypatch.setattr(R, "atomic_replace", lambda src, dst: (seen.append((Path(src).name, Path(dst).name)), real(src, dst))[1])
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))
    dsts = {d for _, d in seen}
    assert {"page_0001.txt", "page_0002.txt", "page_0003.txt", "report.json"} <= dsts
    assert all(s == d + ".part" for s, d in seen)
    assert not list(book.out.glob("*.part"))


# ----------------------------------------------------------------- safety switch
def test_real_models_refused_when_switch_is_on(book, monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    with pytest.raises(R.RestoreError) as e:
        R.restore_book(book(model_id="agy:gemini-3.8-flash-high"))
    assert e.value.code == "real_models_off"
    assert not book.out.exists() or not any(book.out.iterdir())
    assert not mock.CALLS


def test_provider_refusal_stops_the_whole_run(book, monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")

    def refuse(spec, system, user, **kw):
        raise ProviderError("real_models_off", "real models are disabled")
    with pytest.raises(R.RestoreError) as e:
        R.restore_book(book(complete=refuse))
    assert e.value.code == "real_models_off"


def test_mock_still_works_with_the_switch_on(book, monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    mock.set_canned([H.answer([1, 2, 3])])
    assert R.restore_book(book(only={1}))["ok"] == [1]


def test_cli_refuses_a_real_model_with_exit_3(book, monkeypatch, capsys):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    code = cli.main(["--book", "inv_book", "--model", "agy:gemini-3.8-flash-high", "--out", str(book.out)])
    assert code == 3
    assert "real_models_off" in capsys.readouterr().err
    assert not book.out.exists()


# ----------------------------------------------------------------- the command line
def fake_catalogue(monkeypatch):
    from bti.library import catalogue
    monkeypatch.setattr(catalogue, "load_works", lambda b: [dict(w) for w in H.WORKS] if b == "inv_book" else [])
    monkeypatch.setattr(catalogue, "load_books", lambda: [{"id": "inv_book", "title": "An Invented Book"}])


def test_cli_runs_selected_works(book, monkeypatch, capsys):
    fake_catalogue(monkeypatch)
    mock.set_canned([H.answer([4, 5])])
    code = cli.main(["--book", "inv_book", "--work", "2", "--model", "mock", "--out", str(book.out), "--clean-dir", str(book.clean)])
    assert code == 0
    assert (book.out / "page_0004.txt").is_file() and not (book.out / "page_0001.txt").exists()
    assert "1 restored" in capsys.readouterr().out


def test_cli_exit_1_when_a_work_fails_and_dry_run_writes_nothing(book, monkeypatch, capsys):
    fake_catalogue(monkeypatch)
    code = cli.main(["--book", "inv_book", "--work", "1-2", "--model", "mock", "--out", str(book.out), "--clean-dir", str(book.clean)])
    assert code == 1
    assert "failed works: 1, 2" in capsys.readouterr().out
    out2 = book.out.parent / "dry"
    n = len(mock.CALLS)
    code = cli.main(["--book", "inv_book", "--model", "mock", "--out", str(out2), "--clean-dir", str(book.clean), "--dry-run", "--print-prompt"])
    assert code == 0 and not out2.exists() and len(mock.CALLS) == n
    assert "ADD NOTHING" in capsys.readouterr().out


def test_cli_unknown_work_and_unknown_book(book, monkeypatch, capsys):
    fake_catalogue(monkeypatch)
    assert cli.main(["--book", "inv_book", "--work", "9", "--model", "mock", "--out", str(book.out), "--clean-dir", str(book.clean)]) == 2
    assert cli.main(["--book", "nope", "--model", "mock", "--out", str(book.out), "--clean-dir", str(book.clean)]) == 2


def test_parse_works():
    assert cli.parse_works("5") == {5} and cli.parse_works("5,7") == {5, 7} and cli.parse_works("3-5") == {3, 4, 5}
    assert cli.parse_works(None) is None


# ----------------------------------------------------------------- the checks on their own
ORIG = {"page_0001": H.PAGE1}


def check(answer, **kw):
    return checks.check_answer(ORIG, answer, **kw)


def good_text():
    return H.answer([1])


def test_good_answer_passes_and_a_fenced_one_too():
    r = check(good_text())
    assert r.ok and r.names == [("Odran Bel", "Odran Pell"), ("Bel", "Pell")] and r.unclear == {"page_0001": 1}
    r = check("```\n" + good_text() + "```\n")
    assert r.ok


def test_text_before_first_marker_is_a_warning_only():
    r = check("Here is the restored chapter:\n\n" + good_text())
    assert r.ok and any("before the first page marker" in w for w in r.warnings)


def test_missing_names_block_fails():
    r = check(H.answer([1], names=None))
    assert not r.ok and any("names" in f for f in r.failures)


def test_empty_names_block_is_fine():
    r = check(H.answer([1], names="", transform=lambda t: t))
    assert r.ok and r.names == []


def test_added_number_fails_and_dropped_number_warns():
    r = check(H.answer([1], transform=lambda t: H.fix(t).replace("one by one", "one by one, about 400 of them")))
    assert not r.ok and any("added" in f and "400" in f for f in r.failures)
    pages = {"page_0001": H.PAGE1.replace("lighting", "lighting 1871 times")}
    r = checks.check_answer(pages, H.answer([1], pages={1: H.PAGE1}))
    assert r.ok and any("missing from the result" in w and "1871" in w for w in r.warnings)


def test_unbalanced_unclear_marker_fails():
    r = check(H.answer([1], transform=lambda t: H.fix(t).replace("[[? the hand", "[[? the hand").replace(" ?]],", ",")))
    assert not r.ok and any("unbalanced" in f for f in r.failures)


def test_invented_tag_and_markdown_heading_fail():
    r = check(H.answer([1], transform=lambda t: H.fix(t).replace("[meta] (1871)", "[date] (1871)")))
    assert not r.ok and any("[unknown:date]" in f or "unknown:date" in f for f in r.failures)
    r = check(H.answer([1], transform=lambda t: H.fix(t).replace("# 01 Odran", "### 01 Odran")))
    assert not r.ok


def test_hard_wrapped_paragraph_fails():
    def wrap(t):
        out = []
        for l in H.fix(t).split("\n"):
            if len(l) > 200:
                k = l.rfind(" ", 0, len(l) // 2)
                l = l[:k] + "\n" + l[k + 1:]
            out.append(l)
        return "\n".join(out)
    r = check(H.answer([1], transform=wrap))
    assert not r.ok and any("paragraphs returned" in f for f in r.failures)


def test_pages_out_of_order_missing_and_extra():
    two = {"page_0001": H.PAGE1, "page_0002": H.PAGE2}
    one, tw = H.answer([1], names=None), H.answer([2], names=None)
    swapped = tw + "\n" + one + "\n=== names ===\n"
    r = checks.check_answer(two, swapped)
    assert not r.ok and any("out of order" in f for f in r.failures)
    r = checks.check_answer(two, one + "\n=== page_0009 ===\nhello\n\n=== names ===\n")
    assert any("missing page(s): page_0002" in f for f in r.failures) and any("not part of the input: page_0009" in f for f in r.failures)


def test_names_block_hygiene():
    names = "Bel => Pell\nQuentin => Quill\nnot a name line\nBel => Bel\n(none)"
    r = check(H.answer([1], names=names))
    assert r.ok and r.names == [("Bel", "Pell")]
    assert any("not in the input" in w for w in r.warnings) and any("not of the form" in w for w in r.warnings)


def test_name_listed_but_left_in_text_warns_and_new_capital_words_are_reported():
    def keep_wen(t):
        return H.fix(t).replace("Pell's lamp-lighting man", "Bel's lamp-lighting man").replace("a baker", "a baker named Orlando")
    r = check(H.answer([1], transform=keep_wen))
    assert any('name "Bel" is listed as corrected but still occurs' in w for w in r.warnings)
    assert "Orlando" in r.new_names


def test_short_pages_get_a_wider_length_band():
    tiny = {"page_0001": "[page-type] body\n\n# 01 A Heading\n\nShort text here.\n"}
    ans = "=== page_0001 ===\n[page-type] body\n\n# 01 A Heading\n\nShort text here, said plainly.\n\n=== names ===\n"
    assert checks.check_answer(tiny, ans).ok


# ----------------------------------------------------------------- configuration
def test_role_is_configured_and_output_is_ignored():
    agents = json.loads((REPO / "config" / "agents.json").read_text(encoding="utf-8"))
    assert agents["library.restore"] == "agy:gemini-3.8-flash-high"
    from bti.settings import model_for
    assert model_for("library.restore")
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "library/restored/" in ignore


def test_prompt_template_has_what_the_model_needs():
    t = R.PROMPT_PATH.read_text(encoding="utf-8")
    for needle in ("{{BOOK}}", "{{CHAPTER}}", "{{PAGES}}", "[[?", "?]]", "=== names ===", "=== page_", "=> ", "[page-type]", "[sidebar-start]",
                   "[sidebar-end]", "[continues]", "[caption]", "[credit]", "[note]", "[quote]", "[meta]", "Add nothing", "statement of facts",
                   "=== readings ===", "three cases", "curly", "literal form in the input => what you wrote"):
        assert needle.lower() in t.lower(), needle


# ----------------------------------------------------------------- declared readings
def rfixed_answer(readings=H.READINGS, **kw):
    return H.answer([1, 2, 3], transform=H.rfix, readings=readings, **kw)


def test_declared_reading_is_accepted_and_reported(book):
    mock.set_canned([rfixed_answer()])
    res = R.restore_book(book(only={1}))
    assert res["ok"] == [1]
    assert "truly sombre" in read(book.out / "page_0002.txt") and "truly festive" not in read(book.out / "page_0002.txt")
    rep = report(book.out)
    assert rep["works"]["1"]["readings"] == [{"from": H.READING_FROM, "to": H.READING_TO}]
    s = rep["summary"]
    assert s["readings"] == 1 and s["readings_all"] == {H.READINGS: 1} and s["names_all"]["Bel => Pell"] == 1
    assert not any("reading" in w for w in rep["works"]["1"]["warnings"])


def test_no_readings_block_is_fine_and_gives_an_empty_list(book):
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))
    assert report(book.out)["works"]["1"]["readings"] == [] and report(book.out)["summary"]["readings_all"] == {}


def test_readings_block_may_say_none_and_may_come_before_names():
    r = check(H.answer([1], readings="(none)"))
    assert r.ok and r.readings == []
    base = H.answer([1], names=None)
    r = check(base + "\n=== readings ===\nhangs down => sinks\n\n=== names ===\n" + H.NAMES + "\n")
    assert r.ok and r.readings == [("hangs down", "sinks")]


@pytest.mark.parametrize("line,part", [
    ("hangs down sinks", "not of the form"),
    ("the sun hangs low => the sun sinks", "old form is not in the input"),
    ("hangs down => sets slowly", "new form is not in the output"),
    ("hangs down => hangs down", "the same"),
    ("\"Hangs down.\" => hangs down", "the same"),
    (" => sinks", "empty side"),
])
def test_bad_readings_lines_are_dropped_and_never_reject(line, part):
    r = check(H.answer([1], readings=line))
    assert r.ok and r.readings == [], r.failures
    assert len(r.readings_dropped) == 1 and part in r.readings_dropped[0]["why"] and r.readings_dropped[0]["line"] == line.strip()
    assert any("readings line dropped" in w and line.strip()[:20] in w for w in r.warnings)


def test_bad_reading_line_does_not_cost_a_retry_and_is_counted(book):
    mock.set_canned([rfixed_answer(readings=H.READINGS + "\ntruly joyful => truly sombre\nexultant carnival => exultant carnival")])
    res = R.restore_book(book(only={1}))
    assert res["ok"] == [1] and len(mock.CALLS) == 1
    w = report(book.out)["works"]["1"]
    assert w["attempts"] == 1 and w["attempt_problems"] == []
    assert w["readings"] == [{"from": H.READING_FROM, "to": H.READING_TO}]
    assert [d["why"] for d in w["readings_dropped"]] == ["the old form is not in the input", "old and new are the same"]
    assert report(book.out)["summary"]["readings_dropped"] == 2


def test_readings_and_names_are_found_tolerantly():
    src = {"page_0001": "[page-type] body\n\nHe saw a false visualization (or \u201cfalse eyes\u201d) in the  glass, and the exultant  carnival "
                        "of Dr. Wen's  street that was lit all evening long, with the lamps burning to the end of the night.\n"}

    def ans(reading, new_text, name=""):
        body = ("He saw a false vision (or \u201cfalse eyes\u201d) in the glass, and the " + new_text
                + " of Dr. Pell's street that was lit all evening long, with the lamps burning to the end of the night.")
        return f"=== page_0001 ===\n[page-type] body\n\n{body}\n\n=== names ===\n{name}\n=== readings ===\n{reading}\n"
    # straight quotes for curly ones, surrounding quotes, final punctuation, case, whitespace
    r = checks.check_answer(src, ans('"false visualization (or "false eyes")". => "false vision (or "false eyes")."', "joyful carnival"))
    assert len(r.readings) == 1 and not r.readings_dropped, r.readings_dropped
    # an ellipsis in the middle of a long form
    r = checks.check_answer(src, ans("false visualization ... false eyes => false vision ... false eyes", "joyful carnival"))
    assert len(r.readings) == 1 and not r.readings_dropped
    r = checks.check_answer(src, ans("false visualization \u2026 glass => false vision (or \u201cfalse eyes\u201d) in the glass", "joyful carnival"))
    assert len(r.readings) == 1, r.readings_dropped
    # the parts must come in this order
    r = checks.check_answer(src, ans("glass ... false visualization => false vision ... false eyes", "joyful carnival"))
    assert r.ok and r.readings == [] and "old form is not in the input" in r.readings_dropped[0]["why"]
    # whitespace and a line break in the input are not a difference
    r = checks.check_answer(src, ans("exultant carnival => joyful carnival", "joyful carnival"))
    assert len(r.readings) == 1
    # a names line gets the same tolerance for its old form; one that cannot be found is dropped with a warning, no rejection
    r = checks.check_answer(src, ans("", "joyful carnival", name="dr. wen's => Dr. Pell's\nDr. Zork => Dr. Pell"))
    assert r.ok and r.names == [("dr. wen's", "Dr. Pell's")]
    assert [d["why"] for d in r.names_dropped] == ["the old form is not in the input"]
    assert any("names line dropped" in w for w in r.warnings)


def test_readings_in_the_instruction_lines_leak_check():
    leak = "THE MOST IMPORTANT RULE: ADD NOTHING, DROP NOTHING"
    pl = checks.prompt_lines_of(R.PROMPT_PATH.read_text(encoding="utf-8"))
    r = checks.check_answer(ORIG, H.answer([1], readings=leak), pl)
    assert not r.ok and any("readings block" in f for f in r.failures)


def _many(n_phrases, filler):
    para = " ".join(f"The thing{i} was odd." for i in range(n_phrases)) + " " + filler
    pages = {"page_0001": f"[page-type] body\n\n{para}\n"}
    ans = f"=== page_0001 ===\n[page-type] body\n\n{para.replace('was odd', 'was strange')}\n\n=== names ===\n"
    return pages, ans


def test_many_readings_and_a_large_share_are_warnings_only():
    pages, ans = _many(13, "x" * 3000)
    lines = "\n".join(f"thing{i} was odd => thing{i} was strange" for i in range(13))
    r = checks.check_answer(pages, ans + "=== readings ===\n" + lines + "\n")
    assert r.ok and len(r.readings) == 13 and any("more than 12" in w for w in r.warnings)
    pages, ans = _many(3, "y" * 150)
    lines = "\n".join(f"thing{i} was odd => thing{i} was strange" for i in range(3))
    r = checks.check_answer(pages, ans + "=== readings ===\n" + lines + "\n")
    assert r.ok and any("percent of the input" in w for w in r.warnings) and not any("more than 12" in w for w in r.warnings)
    pages, ans = _many(1, "z" * 3000)
    r = checks.check_answer(pages, ans + "=== readings ===\nthing0 was odd => thing0 was strange\n")
    assert r.ok and not r.warnings
    # 7 short readings in about 5 percent of a chapter: normal, no warning (the limit is 8 percent)
    pages, ans = _many(7, "z" * 1500)
    lines = "\n".join(f"thing{i} was odd => thing{i} was strange" for i in range(7))
    r = checks.check_answer(pages, ans + "=== readings ===\n" + lines + "\n")
    assert r.ok and len(r.readings) == 7 and not any("percent" in w for w in r.warnings), r.warnings
    assert checks.MAX_READINGS_SHARE == 0.08


def test_straight_quotes_where_the_input_had_curly_ones_warn():
    curly = {"page_0001": "[page-type] body\n\nHe said \u201cit is late\u201d and left the room at once, without a word more.\n"}
    straight = '=== page_0001 ===\n[page-type] body\n\nHe said "it is late" and left the room at once, without a word more.\n\n=== names ===\n'
    r = checks.check_answer(curly, straight)
    assert r.ok and any("straight double quotes" in w for w in r.warnings)
    ok = straight.replace('"', "\u201c", 1).replace('"', "\u201d", 1)
    assert not any("straight" in w for w in checks.check_answer(curly, ok).warnings)
    plain = {"page_0001": curly["page_0001"].replace("\u201c", '"').replace("\u201d", '"')}
    assert not any("straight" in w for w in checks.check_answer(plain, straight).warnings)


# ----------------------------------------------------------------- the prompt is part of the input hash
def test_changing_the_prompt_makes_every_work_run_again(book, tmp_path):
    prompt2 = tmp_path / "PROMPT2.md"
    prompt2.write_text(R.PROMPT_PATH.read_text(encoding="utf-8") + "\nAn extra sentence for this test.\n", encoding="utf-8")
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))
    h1 = report(book.out)["works"]["1"]["input_hash"]
    sha1 = report(book.out)["prompt_sha"]
    assert R.restore_book(book(only={1}))["skipped"] == [1]               # same prompt, same input: skipped
    mock.set_canned([H.answer([1, 2, 3])])
    res = R.restore_book(book(only={1}, prompt_path=prompt2))
    assert res["ok"] == [1] and res["skipped"] == []
    assert report(book.out)["works"]["1"]["input_hash"] != h1 and report(book.out)["prompt_sha"] != sha1
    assert "An extra sentence for this test." in mock.CALLS[-1]["user"]
    assert R.restore_book(book(only={1}, prompt_path=prompt2))["skipped"] == [1]
    assert R.input_hash("a", [(1, "x")]) != R.input_hash("b", [(1, "x")]) != R.input_hash("b", [(1, "y")])


# ----------------------------------------------------------------- every attempt is recorded
def test_attempt_problems_are_kept_when_the_retry_passes_and_logged(book):
    log = []
    bad = H.answer([1, 2, 3], transform=lambda t: drop_paragraph(H.fix(t)))
    mock.set_canned([bad, H.answer([1, 2, 3])])
    R.restore_book(book(only={1}, log=log.append))
    w = report(book.out)["works"]["1"]
    assert w["ok"] and w["attempts"] == 2 and len(w["attempt_problems"]) == 1
    assert any("2 paragraphs returned, the original has 3" in p for p in w["attempt_problems"][0])
    line = [l for l in log if "attempt 1 rejected" in l][0]
    assert "2 paragraphs returned" in line                       # the problems, not only their count


def test_attempt_problems_of_a_failed_work_and_of_a_model_error(book):
    bad = H.answer([1, 2, 3], transform=lambda t: drop_paragraph(H.fix(t)))
    mock.set_canned([bad, bad])
    R.restore_book(book(only={1}))
    w = report(book.out)["works"]["1"]
    assert len(w["attempt_problems"]) == 2 and w["failures"] == w["attempt_problems"][1]
    n = []

    def err_then_good(spec, system, user, **kw):
        n.append(1)
        if len(n) == 1:
            raise ProviderError("timeout", "too slow")
        return H.answer([4, 5])
    R.restore_book(book(only={2}, complete=err_then_good))
    w = report(book.out)["works"]["2"]
    assert w["ok"] and len(w["attempt_problems"]) == 1 and "timeout" in w["attempt_problems"][0][0]


def test_clean_first_attempt_has_an_empty_problem_list(book):
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))
    assert report(book.out)["works"]["1"]["attempt_problems"] == []


# ----------------------------------------------------------------- a saved answer is not paid for twice
def padded(t):
    """Paragraphs cut to a quarter: rejected by the length checks as they are now, accepted when they are loosened."""
    t = H.fix(t).replace("[[? ", "").replace(" ?]]", "")          # a cut must not fall inside an unclear marker
    return "\n".join(l[:len(l) // 4] + "." if len(l) > 200 else l for l in t.split("\n"))


def test_saved_answer_that_passes_now_is_used_without_a_model_call(book, monkeypatch):
    log = []
    bad = H.answer([1, 2, 3], transform=padded)
    w = failed(book, [bad, bad], log=log.append)
    assert w["result"] == "failed_checks" and len(mock.CALLS) == 2
    assert (book.out / "_failed" / "work_001_try2.txt").is_file()
    # the checks are loosened (as a new version of the tool would): the saved answer now passes
    monkeypatch.setattr(checks, "PAGE_RATIO", (0.1, 9.0))
    monkeypatch.setattr(checks, "PARA_RATIO", (0.1, 9.0))
    res = R.restore_book(book(only={1}, log=log.append))
    assert res["ok"] == [1] and len(mock.CALLS) == 2, json.dumps(report(book.out)["works"]["1"], indent=1)  # no new call
    w = report(book.out)["works"]["1"]
    assert w["from_saved"] is True and w["saved_file"].startswith("work_001_try") and w["attempts"] == 0 and w["ok"]
    assert any("saved earlier answer" in l and "no model call" in l for l in log)
    assert (book.out / "page_0001.txt").is_file()
    assert not list((book.out / "_failed").glob("work_001*"))


def test_saved_answer_is_not_used_when_the_input_or_prompt_changed_or_it_still_fails(book, monkeypatch, tmp_path):
    bad = H.answer([1, 2, 3], transform=padded)
    failed(book, [bad, bad])
    # still failing under the current checks: the model is called
    mock.set_canned([H.answer([1, 2, 3])])
    res = R.restore_book(book(only={1}))
    assert res["ok"] == [1] and len(mock.CALLS) == 3 and not report(book.out)["works"]["1"].get("from_saved")
    # a different prompt: the saved answers belong to another input hash
    failed(book, [bad, bad], force=True)
    monkeypatch.setattr(checks, "PAGE_RATIO", (0.1, 9.0))
    monkeypatch.setattr(checks, "PARA_RATIO", (0.1, 9.0))
    p2 = tmp_path / "P2.md"
    p2.write_text(R.PROMPT_PATH.read_text(encoding="utf-8") + "\nOther.\n", encoding="utf-8")
    n = len(mock.CALLS)
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}, prompt_path=p2))
    assert len(mock.CALLS) == n + 1 and not report(book.out)["works"]["1"].get("from_saved")


def test_saved_answer_of_a_work_that_is_not_failed_is_ignored(book, monkeypatch):
    bad = H.answer([1, 2, 3], transform=padded)
    failed(book, [bad, bad])
    mock.set_canned([H.answer([1, 2, 3])])
    R.restore_book(book(only={1}))                                 # now ok; raws are cleared
    (book.out / "_failed").mkdir(exist_ok=True)
    (book.out / "_failed" / "work_001_try1.txt").write_text(bad, encoding="utf-8")
    monkeypatch.setattr(checks, "PAGE_RATIO", (0.1, 9.0))
    monkeypatch.setattr(checks, "PARA_RATIO", (0.1, 9.0))
    mock.set_canned([H.answer([1, 2, 3])])
    n = len(mock.CALLS)
    assert R.restore_book(book(only={1}, force=True))["ok"] == [1] and len(mock.CALLS) == n + 1


def test_dry_run_tells_what_the_next_run_would_do_with_saved_answers(book, monkeypatch, capsys):
    fake_catalogue(monkeypatch)
    bad = H.answer([1, 2, 3], transform=padded)
    failed(book, [bad, bad])
    args = ["--book", "inv_book", "--work", "1", "--model", "mock", "--out", str(book.out), "--clean-dir", str(book.clean), "--dry-run"]
    capsys.readouterr()
    assert cli.main(args) == 0
    assert "still rejected" in capsys.readouterr().out
    monkeypatch.setattr(checks, "PAGE_RATIO", (0.1, 9.0))
    monkeypatch.setattr(checks, "PARA_RATIO", (0.1, 9.0))
    before = {p.name: p.read_bytes() for p in book.out.rglob("*") if p.is_file()}
    n = len(mock.CALLS)
    assert cli.main(args) == 0
    assert "PASSES the current checks" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in book.out.rglob("*") if p.is_file()} == before and len(mock.CALLS) == n
