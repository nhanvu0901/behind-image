import json

from bti.export import describe

from conftest import REPO


def load(name):
    return json.loads((REPO / "projects" / "arnolfini" / name).read_text(encoding="utf-8"))


def test_arnolfini_description():
    sb, tm, meta = load("storyboard.json"), load("timing.json"), load("project.json")
    meta = {"title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434", "sources": [{"book_id": "payne_gae"}, {"book_id": "payne_gae"}, {"book_id": "hodge_aid"}]}
    r = describe.build_description(sb, tm, meta, duration=820.8333, titles={"payne_gae": {"title": "Great Art Explained", "author": "James Payne"}})
    d = r["description"]
    assert d.startswith("The Arnolfini Portrait\n")
    assert "Jan van Eyck, The Arnolfini Portrait (1434)" in d
    assert "Chapters:\n00:00 Cold Open\n" in d
    assert "Great Art Explained \u2014 James Payne" in d and "hodge_aid" in d
    assert "Images and credits:" in d and "https://commons.wikimedia.org/wiki/File:Van_Eyck" in d and "(PD)" in d
    assert "Subtitles available" not in d
    assert r["chapters"].splitlines()[0] == "00:00 Cold Open" and len(r["chapters"].splitlines()) == 8
    assert r["notes"] == []


def test_empty_sections_are_dropped():
    r = describe.build_description({"title": "T", "shots": [], "assets": {}}, {"chapters": []}, {}, duration=10)
    assert "Chapters" not in r["description"] and "Sources" not in r["description"] and "credits" not in r["description"]
    assert r["description"].startswith("T\n") and "Subtitles available" not in r["description"]


def test_flagged_asset_gets_a_note_and_nothing_is_refused():
    sb = {"title": "T", "assets": {"A": {"title": "Pic", "credit": {"author": "X", "licence": "unknown", "flag": "unknown"}}},
          "shots": [{"slots": {"image": {"asset": "A"}}}]}
    r = describe.build_description(sb, {}, {}, duration=10)
    assert "Note: \u201cPic\u201d" in r["description"] and "could not be confirmed" in r["description"]
    assert len(r["notes"]) == 1


def test_only_assets_that_appear_in_a_shot_are_credited():
    sb = {"assets": {"A": {"title": "a"}, "B": {"title": "b"}, "C": {"title": "c"}},
          "shots": [{"slots": {"image": {"asset": "B"}}, "overlays": [{"slots": {"x": {"asset": "A"}}}]}]}
    assert describe.used_assets(sb) == ["B", "A"]


def test_custom_template():
    out = describe.render_template("Hello {{a}}\n\nGone {{b}}\n\nFixed", {"a": "x", "b": ""})
    assert out == "Hello x\n\nFixed\n"


def test_clock_format():
    assert describe.clock(75) == "01:15" and describe.clock(3725) == "1:02:05"


def test_template_file_has_the_placeholders():
    t = describe.TEMPLATE.read_text(encoding="utf-8")
    for n in ("title", "artwork", "chapters", "books", "credits", "notes"):
        assert "{{%s}}" % n in t
