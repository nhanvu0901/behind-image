"""The title through the `bti` command: `bti status` names it, `bti do <p> title.generate` is a costed long job, `bti do <p> title.set --set text=...` sets one (the answer of the
generic action call), `bti doc title` prints the skill. The app is the one of the tests, the title agent a fake; the actions are those of the state answer."""
import pytest
from cli_helpers import AppTransport, run_bti
from run_helpers import state
from title_helpers import FakeTitleAgent, install_agent

from bti.cli import render as R
from bti.title import store as T

ARN = "arn"
TITLE = "The Saint Who Was Also an Advertisement"


def bti(c, *argv):
    return run_bti(AppTransport(c), *argv)


def test_status_names_the_title_and_the_next_command(client, world):
    world.build("narration_approved")
    r = bti(client, "status", ARN)
    assert r.code == 0
    lines = r.out.splitlines()
    assert "title: none yet (title.generate has an agent write one once the narration is approved; title.set sets your own)" in lines
    assert lines[-1] == "next: bti do arn title.generate --yes-cost --wait   (Viết tựa video)"
    assert any(l.startswith("  title.generate ") and "costs model (about 1 minute)" in l and "long job: add --wait" in l for l in lines)
    assert any(l.startswith("also (other steps): ") and "title.set (give)" in l for l in lines)         # the current step is the voice: the title's own box is listed with the other steps


def test_status_names_the_agents_title_and_who_set_it_and_says_when_it_is_stale(client, world, monkeypatch):
    world.build("narration_approved")
    install_agent(monkeypatch, FakeTitleAgent())
    r = bti(client, "do", ARN, "title.generate", "--yes-cost", "--wait")
    assert r.code == 0, r
    assert 'title: "%s" (agent:mock, done)' % TITLE in bti(client, "status", ARN).out
    T.write_generated(client.root / ARN, T.read(client.root / ARN)[0]["candidates"], by="agent:mock", narration_rev_="0" * 40, written={})
    assert 'title: "%s" (agent:mock, stale; the narration changed since an agent wrote it: title.generate writes it again)' % TITLE in bti(client, "status", ARN).out


def test_status_text_has_no_title_line_for_an_app_that_does_not_know_it():
    assert R.title_line({"project": "x"}) is None and R.title_line({"title": "nope"}) is None
    assert R.title_line({"title": {"state": "done", "text": "T", "by": None}}) == 'title: "T" ((not recorded), done)'


def test_do_title_generate_is_refused_without_the_cost_confirmation_and_runs_with_it(client, world, monkeypatch):
    world.build("narration_approved")
    install_agent(monkeypatch, FakeTitleAgent())
    r = bti(client, "do", ARN, "title.generate")
    assert r.code == 3 and "cost_not_confirmed" in r.err and "title.generate costs model (about 1 minute)" in r.err
    assert not (client.root / ARN / "title.json").exists()
    r = bti(client, "do", ARN, "title.generate", "--yes-cost", "--wait", "--set", "note=make it about the saint")
    assert r.code == 0 and r.out.splitlines()[0].startswith("started job ") and "done: " in r.out
    doc, _ = T.read(client.root / ARN)
    assert doc["chosen"]["text"] == TITLE and doc["written"]["note"] == "make it about the saint"
    assert doc["written"]["requested_by"] == "cli:bti"                                              # the command named itself (`--actor` or `cli:bti`)
    assert doc["chosen"]["by"] == "agent:mock"


def test_do_title_set_sets_the_title_as_the_command_and_it_is_never_stale(client, world):
    world.build("narration_approved")
    r = bti(client, "do", ARN, "title.set", "--set", "text=Why Is a Saint Weighing a Ring?")
    assert r.code == 0 and r.out.splitlines()[0] == "ok: title.set", r
    doc, _ = T.read(client.root / ARN)
    assert doc["chosen"] == {**doc["chosen"], "text": "Why Is a Saint Weighing a Ring?", "by": "cli:bti", "source": "person"}
    assert state(client)["title"]["state"] == "done"
    r = bti(client, "--actor", "cli:owner", "do", ARN, "title.set", "--set", "text=Another One")
    assert r.code == 0 and T.read(client.root / ARN)[0]["chosen"]["by"] == "cli:owner" and T.read(client.root / ARN)[0]["history"][0]["text"] == "Why Is a Saint Weighing a Ring?"


def test_do_title_set_without_a_text_is_a_usage_error_and_a_bad_text_is_refused_with_its_code(client, world):
    world.build("narration_approved")
    r = bti(client, "do", ARN, "title.set")
    assert r.code == 2 and "title.set needs content: give text" in r.err
    r = bti(client, "do", ARN, "title.set", "--set", "text=" + "x" * 61)
    assert r.code == 4 and "title_too_long" in r.err and "at most 60 characters" in r.err
    assert not (client.root / ARN / "title.json").exists()


def test_json_status_carries_the_title_and_the_action_shapes(client, world):
    world.build("narration_approved")
    st = bti(client, "status", ARN, "--json").json
    assert st["title"]["state"] == "none" and {a["id"] for a in st["next_actions"]} >= {"title.generate", "title.set"}


def test_bti_doc_title_prints_the_skill(client):
    r = bti(client, "doc", "title")
    assert r.code == 0 and "name: bti-title" in r.out and "TASK.template.md" in r.out and r.out.rstrip().endswith("|")


def test_a_title_job_is_followed_like_any_other_job(client, world, monkeypatch):
    world.build("narration_approved")
    install_agent(monkeypatch, FakeTitleAgent())
    r = bti(client, "do", ARN, "title.generate", "--yes-cost")
    assert r.code == 0 and "started job" in r.out
    import re
    jid = re.search(r"started job ([0-9a-f]{16})", r.out).group(1)
    assert bti(client, "job", jid, "--wait").code == 0
