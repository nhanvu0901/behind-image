import pytest
from bti.music.fetch import licence, build_record, seed_plan


def metadata(short, url="", terms=""):
    return {"LicenseShortName": {"value": short}, "LicenseUrl": {"value": url}, "UsageTerms": {"value": terms},
            "Artist": {"value": "A Performer"}, "Performer": {"value": "A Performer"}, "ObjectName": {"value": "A Piece"}}


@pytest.mark.parametrize("short,url", [("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
                                        ("Public domain", "https://creativecommons.org/publicdomain/mark/1.0/")])
def test_accepts_recording_public_domain(short, url):
    assert licence(metadata(short, url))[0]


@pytest.mark.parametrize("short,url", [("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
                                        ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
                                        ("unknown", ""), ("Public domain", "https://creativecommons.org/licenses/by-sa/4.0/")])
def test_rejects_unsafe_or_conflicting_recording_licence(short, url):
    ok, reason = licence(metadata(short, url))
    assert not ok and reason


def test_build_record_includes_measured_and_credit_metadata():
    seed = {"title": "Piece", "composer": "Composer", "composed": "1700", "period": "baroque", "forces": "harpsichord"}
    result = build_record(seed, "id", "id.flac", metadata("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"), "https://commons.wikimedia.org/wiki/File:Test.ogg", 42.5, -21.0)
    assert result["duration"] == 42.5 and result["loudness"] == -21.0
    assert result["license"] == "CC0" and "A Performer" in result["credit"]


def test_seed_plan_covers_periods_and_sixty_distinct_recordings():
    seeds = seed_plan()
    assert len(seeds) >= 60
    assert len({s["query"] for s in seeds}) == len(seeds)
    assert {s["period"] for s in seeds} == {"medieval", "renaissance", "baroque", "classical", "romantic", "modern"}


def test_category_fetch_waits_for_retry_after_and_resumes(tmp_path, monkeypatch):
    from urllib.error import HTTPError
    from bti.music import fetch
    calls, waits = [], []
    def request(url):
        calls.append(url)
        if len(calls) == 1:
            raise HTTPError(url, 429, "Too Many Requests", {"Retry-After": "7"}, None)
        return {"query": {"pages": []}}
    monkeypatch.setattr(fetch, "_json", request)
    monkeypatch.setattr(fetch.time, "sleep", waits.append)
    assert fetch.fetch(5, tmp_path, 1000, categories=["Category:Example"]) == 0
    assert len(calls) == 2 and 7 in waits
    assert "Category%3AExample" in calls[-1]


def test_category_fetch_follows_continuation(tmp_path, monkeypatch):
    from bti.music import fetch
    calls = []
    def request(url):
        calls.append(url)
        return {"query": {"pages": []}, **({"continue": {"gcmcontinue": "next", "continue": "-||"}} if len(calls) == 1 else {})}
    monkeypatch.setattr(fetch, "_json", request)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    fetch.fetch(5, tmp_path, 1000, categories=["Category:Example"])
    assert len(calls) == 2 and "gcmcontinue=next" in calls[1]


def test_record_uses_actual_recording_title():
    seed = {"title": "Dido's lament", "composer": "Henry Purcell", "composed": "1600-1750", "period": "baroque", "forces": "instrumental"}
    row = build_record(seed, "one", "one.opus", metadata("Public domain"), "https://commons.wikimedia.org/wiki/File:Purcell%2C_Dido%27s_Lament_ground_bass_01.wav", 2, -37)
    assert "ground bass" in row["title"] and "ground bass" in row["credit"]


def test_rejects_conflicting_usage_terms_even_if_short_licence_claims_public_domain():
    ok, reason = licence(metadata("Public domain", terms="Attribution required"))
    assert not ok and reason


def test_search_filename_cannot_confuse_numbered_works():
    from bti.music.fetch import _matches
    seed = {"composer": "Johann Sebastian Bach", "title": "Cello suite 1 prelude"}
    assert not _matches({"title": "File:Bach Cello Suite 5 Prelude.ogg"}, seed)
    assert _matches({"title": "File:Bach Cello Suite 1 Prelude.ogg"}, seed)


def test_existing_commons_api_fixture_licence_answers_are_filtered():
    import json
    from pathlib import Path
    fixture = Path(__file__).resolve().parents[1] / "media" / "fixtures" / "commons_search.json"
    pages = json.loads(fixture.read_text(encoding="utf-8"))["query"]["pages"]
    results = [licence(page["imageinfo"][0]["extmetadata"])[0] for page in pages]
    assert results == [True, False, False, True, False]


def test_refuses_licence_url_that_only_looks_like_cc0():
    ok, _ = licence(metadata("CC0", "https://creativecommons.org/publicdomain/zero/1.0-not-a-licence"))
    assert not ok


def test_performer_must_not_be_inferred_from_composer_artist():
    seed = {"title": "Piece", "composer": "Johann Sebastian Bach", "composed": "1700", "period": "baroque", "forces": "piano"}
    meta = metadata("CC0")
    meta["Artist"] = {"value": "Johann Sebastian Bach"}
    meta.pop("Performer")
    row = build_record(seed, "id", "id.opus", meta, "https://commons.wikimedia.org/wiki/File:Piece.ogg", 60, -20)
    assert not row.get("performer")
    assert "performed by" not in row["credit"]


def test_composer_surname_is_not_a_performer_credit(tmp_path, monkeypatch):
    from bti.music import export
    from bti.music import library, store
    path = tmp_path / 'recording.opus'
    path.write_bytes(b'audio')
    row = {'id': 'one', 'file': path.name, 'title': 'Piece', 'composer': 'Henry Purcell',
           'performer': 'Purcell', 'license': 'Public domain', 'duration': 60}
    monkeypatch.setattr(library, 'directory', lambda: tmp_path)
    monkeypatch.setattr(library, 'index', lambda: {'one': row})
    monkeypatch.setattr(store, 'read', lambda _: {'cues': [{'recording': 'one', 'start': {'t': 0}, 'end': {'t': 5},
        'offset': 0, 'role': 'bed', 'level': 'normal', 'fade_in': 0, 'fade_out': 0, 'why': 'Quiet.'}]})
    assert 'performed by' not in export.prepare(tmp_path, {}, {}, 10)['credits'][0]


def test_performer_can_be_read_from_recording_description():
    seed = {"title": "Piece", "composer": "Johann Sebastian Bach", "composed": "", "period": "baroque", "forces": "piano"}
    meta = metadata("CC0")
    meta.pop("Performer")
    meta["Artist"] = {"value": "Johann Sebastian Bach"}
    meta["ImageDescription"] = {"value": "Kimiko Ishizaka - Bach- Well-Tempered Clavier"}
    row = build_record(seed, "id", "id.opus", meta, "https://commons.wikimedia.org/wiki/File:Example.ogg", 60, -20)
    assert row["performer"] == "Kimiko Ishizaka"


def test_repeated_rate_limits_back_off_beyond_retry_after(monkeypatch):
    from urllib.error import HTTPError
    from bti.music import fetch
    waits, calls = [], []
    def request():
        calls.append(1)
        if len(calls) < 4:
            raise HTTPError("https://commons.wikimedia.org", 429, "limited", {"Retry-After": "1"}, None)
        return "ok"
    monkeypatch.setattr(fetch.time, "sleep", waits.append)
    assert fetch._retry(request) == "ok"
    assert waits == [5, 10, 20]


def test_category_fetch_resumes_unprocessed_files_in_same_page(tmp_path, monkeypatch):
    from bti.music import fetch, library
    calls = []
    def page(n):
        source = f"https://commons.wikimedia.org/wiki/File:{n}.ogg"
        return {"ns": 6, "title": f"File:{n}.ogg", "imageinfo": [{"descriptionurl": source,
                "url": f"https://upload.wikimedia.org/{n}.ogg", "size": 10, "mime": "audio/ogg", "extmetadata": metadata("CC0")}]}
    def request(url):
        calls.append(url)
        return {"query": {"pages": [page(1), page(2)]}}
    def download(url, destination, limit):
        destination.write_bytes(b"audio")
    def convert(source, destination):
        destination.write_bytes(b"opus")
        return 90, -20
    monkeypatch.setattr(fetch, "_json", request)
    monkeypatch.setattr(fetch, "_download", download)
    monkeypatch.setattr(fetch, "_convert", convert)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    assert fetch.fetch(1, tmp_path, 100, categories=["Category:Test"]) == 1
    assert fetch.fetch(1, tmp_path, 100, categories=["Category:Test"]) == 1
    assert len(calls) == 1
    assert len(library.read(tmp_path)) == 2


def test_resume_uses_current_category_character_metadata(tmp_path, monkeypatch):
    import json
    from bti.music import fetch, library
    page = {"ns": 6, "title": "File:One.ogg", "imageinfo": [{"descriptionurl": "https://commons.wikimedia.org/wiki/File:One.ogg",
            "url": "https://upload.wikimedia.org/one.ogg", "size": 10, "mime": "audio/ogg", "extmetadata": metadata("CC0")}]}
    state = {"queue": [], "seen": ["Category:Test"], "bytes": 0,
             "pending": [{"page": page, "category": "Category:Test", "composer": "", "period": "", "forces": "piano"}]}
    (tmp_path / "fetch-state.json").write_text(json.dumps(state), encoding="utf8")
    monkeypatch.setattr(fetch, "_download", lambda url, dest, limit: dest.write_bytes(b"audio"))
    monkeypatch.setattr(fetch, "_convert", lambda source, dest: (dest.write_bytes(b"opus") and (90, -20)))
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    assert fetch.fetch(1, tmp_path, 100, categories=[("Category:Test", "", "", "unknown")]) == 1
    assert library.read(tmp_path)[0]["forces"] == "unknown"
