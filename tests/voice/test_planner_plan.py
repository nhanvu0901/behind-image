from bti.voice import files, planner
from bti.voice.errors import VoiceError
from bti.voice.plan import make_plan
from bti.voice.providers.fake import FakeProvider
from conftest import FakeCtx, write_project

import pytest


def test_group_parts_by_size(project, cfg):
    plan = make_plan(project, cfg=cfg, provider="fake")
    parts = planner.group_parts(plan.chunks, 120)
    assert [c for p in parts for c in p] == plan.chunks
    assert len(parts) >= 2
    assert all(sum(len(c.spoken) for c in p) >= 1 for p in parts)


def test_estimate_matches_the_measured_speed(cfg):
    # 4000 characters: 4000/15 s of audio * 4.1 + 60 s load
    assert planner.estimate_seconds(4000, cfg) == int(4000 / 15 * 4.1 + 60)
    assert 1000 < planner.estimate_seconds(4000, cfg) < 1300


def test_missing_and_forced(project, cfg, tmp_path):
    plan = make_plan(project, cfg=cfg, provider="fake")
    assert len(planner.missing(project, plan.chunks)) == len(plan.chunks)
    ctx = FakeCtx(tmp_path / "w")
    FakeProvider().synth(plan.chunks[:2], files.chunks_dir(project), ctx)
    left = planner.missing(project, plan.chunks)
    assert len(left) == len(plan.chunks) - 2
    ids = {plan.chunks[0].id}
    assert planner.missing(project, plan.chunks, ids, since=2 ** 40)[0].id == plan.chunks[0].id     # forced: done before `since`
    assert plan.chunks[0] not in planner.missing(project, plan.chunks, ids, since=0)


def test_plan_needs_an_approved_narration(tmp_path, cfg):
    d = write_project(tmp_path, "unap", approve=False)
    with pytest.raises(VoiceError) as e:
        make_plan(d, cfg=cfg, provider="fake")
    assert e.value.code == "narration_not_approved"
    with pytest.raises(VoiceError) as e:
        make_plan(tmp_path / "nothing", cfg=cfg, provider="fake")
    assert e.value.code == "narration_missing"


def test_assemble_signature_follows_tempo_and_pad_not_chunk_ids(project, cfg):
    a = make_plan(project, cfg=cfg, provider="fake")
    files.write_settings(project, {"tempo": 1.1})
    b = make_plan(project, cfg=cfg, provider="fake")
    assert [c.id for c in a.chunks] == [c.id for c in b.chunks]
    assert a.assemble_sig != b.assemble_sig and a.text_hash == b.text_hash


def test_pronounce_table_changes_only_the_chunks_with_that_word(project, cfg):
    a = make_plan(project, cfg=cfg, provider="fake")
    files.write_pronounce(project, {"mirror": "mir-ror"})
    b = make_plan(project, cfg=cfg, provider="fake")
    changed = [x.id for x, y in zip(a.chunks, b.chunks) if x.id != y.id]
    assert 0 < len(changed) < len(a.chunks)
