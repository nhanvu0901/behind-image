"""A7 safety switch (`BTI_NO_REAL_MODELS=1`) for the media package.

Every place where a REAL request or program would start refuses with `RealModelsOff` (code `real_models_off`), and nothing
reaches the network or starts a program. The refusal sits behind the injection points: a fake opener, a fake runner or a
fake client still work under the switch (every other test in this folder proves that, the switch is on in conftest).
"""
import json
import subprocess
import urllib.request

import pytest

from bti.media import api, clips, http, research
from bti.media.errors import MediaError, RealModelsOff
from bti.media.safety import refuse_if_real_models_off
from bti.media.sources.commons import CommonsSource
from bti.media.sources.met import MetSource
from bti.media.sources.osm import OsmSource
from bti.media.sources.pexels import PexelsSource
from bti.media.sources.pixabay import PixabaySource
from bti.media.youcom import YouComClient

URL = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
CC_INFO = {"id": "aaaaaaaaaaa", "title": "Clip", "license": "Creative Commons Attribution license (reuse allowed)", "channel": "Demo"}
CTX = {"title": "The Arnolfini Portrait", "artist": "Jan van Eyck"}


@pytest.fixture(autouse=True)
def switch_on(monkeypatch):
    """Switch on, and a tripwire under it: a request or a program that gets through fails the test."""
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    monkeypatch.setenv("YDC_API_KEY", "dummy-key")

    def net(*a, **k):
        raise AssertionError("the network was reached under the safety switch")

    def prog(*a, **k):
        raise AssertionError("a program was started under the safety switch")
    monkeypatch.setattr(urllib.request, "urlopen", net)
    monkeypatch.setattr(subprocess, "Popen", prog)
    monkeypatch.setattr(subprocess, "run", prog)
    monkeypatch.setattr(clips, "_ytdlp_cmd", lambda: ["yt-dlp"])      # "installed", so the refusal is what stops it
    monkeypatch.setattr(api, "_SOURCES", {})                           # fresh sources with no injected transport


def refuses(fn, *a, **k):
    with pytest.raises(RealModelsOff) as e:
        fn(*a, **k)
    assert e.value.code == "real_models_off" and "BTI_NO_REAL_MODELS" in str(e.value)
    return e.value


# ---------------------------------------------------------------- the switch itself
def test_the_exception_is_a_media_error_with_the_code():
    e = RealModelsOff("x")
    assert isinstance(e, MediaError) and e.code == "real_models_off" and e.kind == "real_models_off"
    assert isinstance(e, ValueError)          # the shape the picks and editor layers turn into an error that keeps the code


def test_the_http_layers_keep_the_code():
    from bti.editor.media_adapter import _translate as editor_translate
    from bti.picks.service import _translate as picks_translate
    p = picks_translate(RealModelsOff("x"))
    assert p.code == "real_models_off"
    ed = editor_translate(RealModelsOff("x"))
    assert ed.extra.get("code") == "real_models_off"


def test_the_helper_follows_the_variable(monkeypatch):
    refuses(refuse_if_real_models_off, "something")
    for off in ("0", "", "true"):                          # same test as the providers: exactly "1" switches it on
        monkeypatch.setenv("BTI_NO_REAL_MODELS", off)
        assert refuse_if_real_models_off("something") is None
    monkeypatch.delenv("BTI_NO_REAL_MODELS")
    assert refuse_if_real_models_off() is None


# ---------------------------------------------------------------- You.com client and research
def test_youcom_research_refuses():
    refuses(YouComClient("k").research, "prompt", {}, {"domains": []})


def test_youcom_search_refuses():
    refuses(YouComClient("k").search, "a query", {"include_domains": ["youtube.com"]})


def test_youcom_without_a_key_still_answers_with_an_error_and_no_request():
    call = YouComClient("").research("p", {}, None)          # no request would start, so nothing to refuse
    assert not call.ok and "YDC_API_KEY" in call.error


def test_youcom_with_an_injected_opener_works_under_the_switch():
    class Resp:
        status = 200

        def read(self):
            return json.dumps({"output": {"content": {}, "sources": []}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass
    seen = []
    call = YouComClient("k", opener=lambda req, timeout=None: seen.append(req.full_url) or Resp()).search("q", None)
    assert call.ok and call.payload["output"] == {"content": {}, "sources": []} and "api.you.com" in seen[0]


def test_visual_research_refuses():
    refuses(research.visual_research, "A beat of narration.", CTX, live=True)


def test_confirm_claim_refuses():
    refuses(research.confirm_claim, "A claim.", CTX, live=True)


def test_resolve_suggestion_does_not_swallow_the_refusal():
    refuses(research.resolve_suggestion, {"what": "w", "kind": "artwork", "search_terms": ["a"]})


def test_resolve_suggestion_still_skips_an_ordinary_failure():
    def fake(term, source="commons", kind="image", limit=6):
        raise RuntimeError("down")
    assert research.resolve_suggestion({"what": "w", "kind": "artwork", "search_terms": ["a"]}, search_fn=fake) == []


# ---------------------------------------------------------------- the clip module
def test_youtube_search_refuses():
    refuses(clips.youtube_search, "oil glazing")                         # the key comes from the environment
    refuses(clips.youtube_search, "oil glazing", client=YouComClient("k"))


def test_video_metadata_refuses():
    refuses(clips.video_metadata, URL)


def test_subtitle_fetch_does_not_swallow_the_refusal(monkeypatch, tmp_path):
    monkeypatch.setattr(clips, "video_metadata", lambda url, timeout=0: {"id": "aaaaaaaaaaa", "subtitles": {"en": [{}]}})
    refuses(clips.video_metadata_with_cues, URL, tmp_path)


def test_inspect_video_url_refuses():
    refuses(clips.inspect_video_url, URL, "glazing")


def test_moment_search_refuses_at_the_search_step():
    refuses(clips.moment_search, "glazing")                              # real You.com search: gather_candidates must not turn it into a MediaError


def test_moment_search_refuses_at_the_metadata_step():
    rows = [{"url": URL, "title": "T", "snippet": "", "is_video": True}]
    refuses(clips.moment_search, "glazing", search=lambda q: rows)       # fake search, real yt-dlp: the row must not hide it as an "error"


def test_fetch_section_refuses_without_a_runner_and_leaves_no_file(tmp_path):
    refuses(clips.fetch_section, tmp_path, URL, 1, 5, info=CC_INFO, sheet=False, strict_licence=False)
    assert not list(tmp_path.rglob("*.mp4"))


def test_import_clip_refuses_without_a_runner_and_leaves_no_file(tmp_path):
    refuses(clips.import_clip, tmp_path, URL, 1, 5, info=CC_INFO, strict_licence=False)
    refuses(api.import_clip, tmp_path, URL, 1, 5, info=CC_INFO)
    assert not list(tmp_path.rglob("*.mp4"))


def test_a_fake_runner_still_works_under_the_switch(tmp_path, monkeypatch):
    def fake_dl(cmd, *, timeout=None):
        p = tmp_path / "cache" / "clips" / "src" / "aaaaaaaaaaa_sec_1.0_5.0.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"raw")
        return subprocess.CompletedProcess(cmd, 0, str(p) + "\n", "")
    monkeypatch.setattr(clips, "normalize", lambda raw, out: out.write_bytes(b"mp4") or out)
    res = clips.fetch_section(tmp_path, URL, 1, 5, info=CC_INFO, sheet=False, strict_licence=False, runner=fake_dl)
    assert res["file"].endswith(".mp4")


# ---------------------------------------------------------------- the shared HTTP layer
def test_open_url_get_json_and_download_refuse_without_an_opener(tmp_path):
    refuses(http.open_url, "https://example.org/x")
    refuses(http.get_json, "https://example.org/x", {"a": 1})
    dest = tmp_path / "sub" / "f.bin"
    refuses(http.download_file, "https://example.org/x", dest, max_bytes=100)
    assert not dest.exists() and not dest.parent.exists() and not dest.with_name("f.bin.part").exists()


def test_an_injected_opener_works_under_the_switch():
    class Resp:
        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass
    assert http.get_json("https://example.org/x", opener=lambda req, timeout=None: Resp()) == {"ok": True}


# ---------------------------------------------------------------- the picture sources, one by one
IMG = {"url": "https://example.org/a.jpg", "kind": "image", "source_id": "File:A.jpg", "width": 2000, "height": 2000, "mime": "image/jpeg"}
VID = {**IMG, "url": "https://example.org/a.mp4", "kind": "video", "mime": "video/mp4"}


def _osm(tmp_path):
    return OsmSource(sleep=lambda s: None, cache_dir=tmp_path / "osm")


CASES = {
    "commons.search": lambda t: CommonsSource().search("rocks"),
    "commons.search_video": lambda t: CommonsSource().search("rocks", "video"),
    "commons.fetch_meta": lambda t: CommonsSource().fetch_meta("File:A.jpg"),
    "commons.download": lambda t: CommonsSource().download(IMG, t / "a.jpg"),
    "met.search": lambda t: MetSource().search("rocks"),
    "met.fetch_meta": lambda t: MetSource().fetch_meta("436535"),
    "met.download": lambda t: MetSource().download({**IMG, "source_id": "1"}, t / "a.jpg"),
    "pexels.search": lambda t: PexelsSource(key="k").search("rocks"),
    "pexels.search_video": lambda t: PexelsSource(key="k").search("rocks", "video"),
    "pexels.fetch_meta": lambda t: PexelsSource(key="k").fetch_meta("857251"),
    "pexels.download": lambda t: PexelsSource(key="k").download(IMG, t / "a.jpg"),
    "pexels.download_video": lambda t: PexelsSource(key="k").download(VID, t / "a.mp4"),
    "pixabay.search": lambda t: PixabaySource(key="k").search("rocks"),
    "pixabay.search_video": lambda t: PixabaySource(key="k").search("rocks", "video"),
    "pixabay.fetch_meta": lambda t: PixabaySource(key="k").fetch_meta("195893"),
    "pixabay.download": lambda t: PixabaySource(key="k").download(IMG, t / "a.jpg"),
    "pixabay.download_video": lambda t: PixabaySource(key="k").download(VID, t / "a.mp4"),
    "osm.search": lambda t: _osm(t).search("Oslo"),
    "osm.download": lambda t: _osm(t).download({"source_id": "1:12", "_place_id": "1", "_zoom": 12, "_lat": 59.9, "_lon": 10.7}, t / "m.jpg"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_source_refuses(case, tmp_path):
    refuses(CASES[case], tmp_path)
    assert not list(tmp_path.rglob("*.jpg")) and not list(tmp_path.rglob("*.mp4")) and not list(tmp_path.rglob("*.part"))


def test_a_key_never_reaches_a_refusal_message():
    e = refuses(PixabaySource(key="SECRET-KEY-123").search, "rocks")        # Pixabay takes its key in the query string
    assert "SECRET-KEY-123" not in str(e) and "SECRET-KEY-123" not in repr(e)


def test_osm_does_not_compose_and_cache_a_blank_map(tmp_path):
    """compose_map skips a tile that fails; a refusal must not be one of those, or a grey canvas would be cached as the map."""
    src = _osm(tmp_path)
    refuses(src.compose_map, 59.9, 10.7, 12, tmp_path / "osm" / "m.jpg")
    assert not (tmp_path / "osm" / "m.jpg").exists()


def test_osm_serves_a_cached_map_without_any_request(tmp_path):
    (tmp_path / "osm").mkdir()
    (tmp_path / "osm" / "1_z12.jpg").write_bytes(b"cached map")
    dest = _osm(tmp_path).download({"source_id": "1:12", "_place_id": "1", "_zoom": 12}, tmp_path / "out.jpg")
    assert dest.read_bytes() == b"cached map"                      # no request was needed, so there is nothing to refuse


# ---------------------------------------------------------------- the facade
def test_facade_search_and_import_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_SOURCES", {"pexels": PexelsSource(key="k"), "pixabay": PixabaySource(key="k"),
                                          "osm": _osm(tmp_path)})
    proj = tmp_path / "proj"
    proj.mkdir()
    for source in ("commons", "met", "pexels", "pixabay", "osm"):
        refuses(api.search, "rocks", source=source)
    for source, sid in (("commons", "File:A.jpg"), ("met", "436535"), ("pexels", "857251"), ("pixabay", "195893"), ("osm", "1:12")):
        refuses(api.import_candidate, proj, source, sid)
    assert not list(proj.rglob("*.jpg")) and not list(proj.rglob("*.mp4"))


def test_the_book_source_is_local_and_not_touched():
    assert api.get_source("book").name == "book"          # reads page images from the project's own files: no request
