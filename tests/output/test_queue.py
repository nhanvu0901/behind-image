"""The queue table (tools/paintings_table.py) with a copy of the server's output/index.json: the artworks of the index are `done` or `in-progress` with what the index says, instead of the
fixed list of projects."""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ARTWORKS = {
    "eyck-the-arnolfini-portrait": {"title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434", "works": ["payne_gae/002"]},
    "munch-the-scream": {"title": "The Scream", "artist": "Edvard Munch", "year": "1893", "works": ["payne_gae/015"]},
    "tour-the-fortune-teller": {"title": "The Fortune Teller", "artist": "Georges de La Tour", "year": "", "works": ["hagen_wgps/001"]},
    "other-an-obscure-panel": {"title": "An Obscure Panel", "artist": "Somebody", "year": "1500", "works": ["hagen_wgps/002"]},
}


def make_library(root: Path) -> None:
    lib = root / "library"
    (lib / "dossiers").mkdir(parents=True)
    (lib / "artworks.json").write_text(json.dumps(ARTWORKS), encoding="utf-8")
    for key in ARTWORKS:
        (lib / "dossiers" / key).mkdir()
        (lib / "dossiers" / key / "dossier.json").write_text(json.dumps({"kind": "artwork", "sources": [{"book_id": "payne_gae", "n": 2, "words": 3000, "trust": "normal"}],
                                                                        "images": [], "rights": {"status": "pd_likely"}}), encoding="utf-8")
    (root / "docs").mkdir()


def tool(root: Path):
    spec = importlib.util.spec_from_file_location("paintings_table_under_test", REPO / "tools" / "paintings_table.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.LIB, m.OUT = root / "library", root / "docs" / "PAINTINGS.md"
    return m


def rows(root: Path) -> dict:
    out = {}
    for ln in (root / "docs" / "PAINTINGS.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) > 10 and cells[0].isdigit():
            out[cells[2].strip("`")] = {"status": cells[1].strip("`"), "project": cells[10]}
    return out


def test_the_fixed_list_is_used_without_an_index(tmp_path):
    make_library(tmp_path)
    assert tool(tmp_path).main([]) == 0
    r = rows(tmp_path)
    assert r["eyck-the-arnolfini-portrait"]["status"] == "in-progress" and "arnolfini-opus" in r["eyck-the-arnolfini-portrait"]["project"]
    assert r["munch-the-scream"]["status"] == "in-progress" and r["tour-the-fortune-teller"]["status"] == "recommended-1"
    text = (tmp_path / "docs" / "PAINTINGS.md").read_text(encoding="utf-8")
    assert "`done`" not in text.split("## Counts")[0]


def test_an_index_marks_the_artworks_it_lists(tmp_path):
    make_library(tmp_path)
    index = {"schema": "bti.output.index/1", "folders": [
        {"key": "eyck-the-arnolfini-portrait", "project": "arnolfini-opus", "status": "done", "step": "export", "length_seconds": 764.47, "last_run": "2026-11-19T12:50:00-0800", "out_of_date": []},
        {"key": "tour-the-fortune-teller", "project": "fortune", "status": "in_progress", "step": "picks", "length_seconds": None, "last_run": "2026-11-19T13:00:00-0800", "out_of_date": ["narration"]}]}
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    assert tool(tmp_path).main([str(path)]) == 0
    r = rows(tmp_path)
    assert r["eyck-the-arnolfini-portrait"]["status"] == "done" and "arnolfini-opus (video 12:44, 2026-11-19)" == r["eyck-the-arnolfini-portrait"]["project"]
    assert r["tour-the-fortune-teller"]["status"] == "in-progress" and "at step: picks" in r["tour-the-fortune-teller"]["project"] and "out of date: narration" in r["tour-the-fortune-teller"]["project"]
    assert r["munch-the-scream"]["status"] != "in-progress", "an artwork that is not in the index is not in progress, whatever the fixed list says"
    assert r["other-an-obscure-panel"]["status"] in ("candidate", "thin-text")
    text = (tmp_path / "docs" / "PAINTINGS.md").read_text(encoding="utf-8")
    assert "an `output/index.json`" in text and "| `done` | 1 |" in text and "| `in-progress` | 1 |" in text
    first = [ln for ln in text.splitlines() if ln.startswith("| 1 |")][0]
    assert "`done`" in first, "the finished videos come first"
