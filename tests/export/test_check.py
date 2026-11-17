from bti.export import check

LOUD = """[Parsed_ebur128_0 @ 0x1] t: 10 M: -20 I: -20.0 LUFS LRA: 0.0 LU
[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -15.0 LUFS
    Threshold: -25.0 LUFS

  Loudness range:
    LRA:         3.6 LU
    Threshold: -35.0 LUFS

  True peak:
    Peak:       -1.7 dBFS
"""

PROBE = {"format": {"duration": "820.83", "size": "900000000"},
         "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "nb_read_packets": "24625"},
                     {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
                     {"codec_type": "subtitle", "codec_name": "mov_text", "tags": {"language": "eng"}}],
         "chapters": [{"start_time": "0.0", "end_time": "80.0", "tags": {"title": "A"}}, {"start_time": "80.0", "end_time": "820.83", "tags": {"title": "B"}}]}


def test_parse_loudness_reads_the_summary_not_the_running_lines():
    assert check.parse_loudness(LOUD) == {"lufs": -15.0, "lra": 3.6, "true_peak": -1.7}
    assert check.parse_loudness("nothing")["lufs"] is None


def test_parse_probe():
    i = check.parse_probe(PROBE)
    assert i["video"]["frames"] == 24625 and i["video"]["fps"] == 30.0 and i["subtitle"]["codec"] == "mov_text"
    assert i["audio"]["codec"] == "aac" and len(i["chapters"]) == 2 and i["size"] == 900000000
    assert check.parse_probe({})["video"] is None


def card(info=None, loud=None, **kw):
    a = dict(expected_frames=24625, expected_duration=820.8333, cues=300)
    a.update(kw)
    return {i["key"]: i for i in check.report_card(check.parse_probe(info or PROBE), loud if loud is not False else None, **a)}


def test_good_file_passes_everything():
    c = card(loud={"lufs": -15.0, "lra": 3.6, "true_peak": -1.7})
    assert all(i["status"] == "ok" for i in c.values())
    assert check.worst(list(c.values())) == "ok"


def test_each_failure_is_named():
    c = card(expected_frames=24624, loud={"lufs": -20.0, "true_peak": -0.2})
    assert c["frames"]["status"] == "fail" and c["frames"]["note"] == "+1"
    assert c["loudness"]["status"] == "warn" and c["true_peak"]["status"] == "warn"
    bad = dict(PROBE, streams=PROBE["streams"][:2])
    assert card(bad, loud=False)["subtitles"]["status"] == "fail"
    assert card(loud=False)["loudness"]["status"] == "warn"
    assert card(cues=0)["cues"]["status"] == "fail"
    assert card(expected_duration=900)["duration"]["status"] == "fail"


def test_audio_length_and_merged_chapters():
    c = card(loud={"lufs": -15.0, "true_peak": -1.7}, audio_duration=810.0, merged_chapters=2)
    assert c["audio_length"]["status"] == "fail" and c["audio_length"]["value"] == 810.0
    assert c["chapters_merged"]["status"] == "warn" and c["chapters_merged"]["value"] == 2
    assert card(loud=False, audio_duration=820.5)["audio_length"]["status"] == "ok"


def test_worst():
    assert check.worst([{"status": "ok"}, {"status": "warn"}]) == "warn"
    assert check.worst([{"status": "warn"}, {"status": "fail"}]) == "fail"
