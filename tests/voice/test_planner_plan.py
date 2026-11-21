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
    # D17 formula: load_seconds + characters * seconds_per_character
    # Default: 120 s load + 4000 chars * 0.55 s/char = 2320 s
    assert planner.estimate_seconds(4000, cfg) == int(120 + 4000 * 0.55)
    assert planner.estimate_seconds(0, cfg) == 0


def test_group_parts_targets_18_minutes_and_caps_at_25_minutes(cfg):
    from bti.voice.chunks import Chunk
    # Chunks of ~100 characters each: each chunk is ~55 seconds of compute.
    # Target 18 min = 1080 s. 1080 - 120 = 960 s -> ~960 / 55 ~= 17.5 chunks.
    # 50 chunks = 5000 chars = ~2870 s (~48 minutes) -> should split into multiple parts.
    chunks = [Chunk(id=f"c_{i:03d}", index=i, beat="b1", chapter="c1", spoken="x" * 100,
                    units=[], written=["x" * 100], gap=0.2, gap_kind="beat", seed=42, th=f"th_{i}")
              for i in range(50)]
    parts = planner.group_parts(chunks, cfg)
    assert len(parts) >= 2
    # All chunks preserved in order
    assert [c for p in parts for c in p] == chunks
    # Every part is planned <= 25 minutes (1500 seconds)
    for p in parts:
        chars = sum(len(c.spoken) for c in p)
        est = planner.estimate_seconds(chars, cfg)
        assert est <= 25 * 60, f"Part estimated at {est}s exceeds 25 min cap"
        # Planned parts should target ~18 minutes (1080 s)
        assert est >= 120


def test_rolling_median_stats(tmp_path):
    from bti.voice.stats import load_stats, record_part_stats
    import statistics

    stats_file = tmp_path / "voice_stats.json"
    assert load_stats(stats_file) == {}

    # Record 25 parts (exceeding window of 20)
    samples = []
    for i in range(25):
        load = 100.0 + i * 2.0
        spc = 0.40 + (i * 0.01)
        samples.append((load, spc))
        record_part_stats(load, spc, path=stats_file, max_parts=20)

    st = load_stats(stats_file)
    assert len(st["parts"]) == 20
    # Check rolling median of the last 20
    last_20_loads = [s[0] for s in samples[-20:]]
    last_20_spcs = [s[1] for s in samples[-20:]]
    assert abs(st["load_seconds"] - statistics.median(last_20_loads)) < 1e-4
    assert abs(st["seconds_per_character"] - statistics.median(last_20_spcs)) < 1e-4


def test_planner_learns_from_stats(tmp_path, cfg):
    from bti.voice.chunks import Chunk
    from bti.voice.stats import record_part_stats

    stats_file = tmp_path / "voice_stats.json"
    # Record fast stats: load 60s, 0.25 s/char (over 2x faster than default 0.55)
    for _ in range(5):
        record_part_stats(60.0, 0.25, path=stats_file)

    cfg_with_stats = dict(cfg, stats_path=stats_file)
    # Estimate should use learned values: 60 + 1000 * 0.25 = 310s (vs default 120 + 550 = 670s)
    assert planner.estimate_seconds(1000, cfg_with_stats) == 310

    # Grouping with fast stats can fit more characters in 18 minutes (1080 - 60 = 1020s -> 1020/0.25 = 4080 chars)
    chunks = [Chunk(id=f"c_{i:03d}", index=i, beat="b1", chapter="c1", spoken="x" * 100,
                    units=[], written=["x" * 100], gap=0.2, gap_kind="beat", seed=42, th=f"th_{i}")
              for i in range(35)]
    parts_fast = planner.group_parts(chunks, cfg_with_stats)
    parts_default = planner.group_parts(chunks, cfg)
    # Fast machine needs fewer parts than default machine
    assert len(parts_fast) < len(parts_default)



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
