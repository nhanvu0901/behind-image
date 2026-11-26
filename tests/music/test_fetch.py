import pytest
from bti.music.fetch import licence, build_record, seed_plan


def metadata(short, url="", terms=""):
    return {"LicenseShortName": {"value": short}, "LicenseUrl": {"value": url}, "UsageTerms": {"value": terms},
            "Artist": {"value": "A Performer"}, "ObjectName": {"value": "A Piece"}}


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


def test_fetch_stops_when_commons_rate_limits(tmp_path, monkeypatch, capsys):
    from urllib.error import HTTPError
    from bti.music import fetch
    calls = []
    def limited(seed):
        calls.append(seed)
        raise HTTPError("https://commons.wikimedia.org", 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(fetch, "candidates", limited)
    assert fetch.fetch(5, tmp_path, 1000, max_downloads=3) == 0
    assert len(calls) == 1
    assert "rate limit" in capsys.readouterr().out.lower()


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
