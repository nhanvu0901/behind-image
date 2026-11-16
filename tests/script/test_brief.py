import json
import shutil

from bti.script.brief import build_brief, parse_source_text, render_brief, save_options
from script_helpers import make_project


def test_real_project_brief(real_project):
    b = build_brief(real_project)
    assert b["code_map"] == {"PAY": "payne_gae/002", "HOD": "hodge_aid/003", "MAD": "brookehitching_mad/011"}
    assert b["painting"]["title"] == "The Arnolfini Portrait" and b["painting"]["year"] == "1434"
    ids = b["paragraph_ids"]
    assert "PAY-01" in ids and "HOD-05" in ids and "MAD-01" in ids
    names = [d["name"] for d in b["details"]]
    assert "THE MIRROR" in names and "SIGNATURE" in names
    mirror = next(d for d in b["details"] if d["name"] == "THE MIRROR")
    assert {w["src"] for w in mirror["where"]} == {"PAY", "HOD"}          # headings merged across books
    assert [d["id"] for d in b["details"]][:2] == ["D1", "D2"]
    txt = render_brief(b)
    assert "[PAY-01]" in txt and "NAMED DETAILS" in txt and "D1 " in txt
    assert all(s["included"] and not s["low_trust"] for s in b["sources"])


def test_real_project_without_dossier_shapes(real_project):
    (real_project / "source" / "dossier.json").unlink()
    pj = json.loads((real_project / "project.json").read_text())
    pj.pop("dossier", None)
    (real_project / "project.json").write_text(json.dumps(pj))
    b = build_brief(real_project)
    assert b["shape"] == "project" and set(b["code_map"]) == {"PAY", "HOD", "MAD"}
    assert next(d for d in b["details"] if d["name"] == "THE MIRROR")
    # only the text files, no sources list
    pj.pop("sources")
    (real_project / "project.json").write_text(json.dumps(pj))
    b = build_brief(real_project)
    assert b["shape"] == "files" and len(b["sources"]) == 3


def test_paragraph_ids_are_numbered_per_source_and_stable(tproj):
    b = build_brief(tproj)
    pay = next(s for s in b["sources"] if s["code"] == "PAY")
    assert [p["id"] for p in pay["paragraphs"]] == ["PAY-01", "PAY-02", "PAY-03"]
    assert pay["paragraphs"][0]["section"] == "THE MIRROR" and pay["paragraphs"][2]["section"] == "THE LAMP"
    assert [p["kind"] for p in next(s for s in b["sources"] if s["code"] == "HOD")["paragraphs"]] == ["body", "quote", "body"]


def test_conflicts_and_low_trust(tproj):
    b = build_brief(tproj)
    assert b["conflicts"][0]["field"] == "year" and {v["src"] for v in b["conflicts"][0]["values"]} == {"PAY", "HOD"}
    gro = next(s for s in b["sources"] if s["code"] == "GRO")
    assert gro["low_trust"] and not gro["included"]
    txt = render_brief(b)
    assert "unreliable edition" not in txt and "NOT INCLUDED" in txt and "CONFLICTS BETWEEN SOURCES" in txt
    save_options(tproj, {"include_low": ["grovier_nws"]})
    b2 = build_brief(tproj)
    assert next(s for s in b2["sources"] if s["code"] == "GRO")["included"]
    t2 = render_brief(b2)
    assert "unreliable edition" in t2 and "LOW TRUST" in t2
    assert build_brief(tproj, include_low=[])["sources"][2]["included"] is False


def test_source_text_parser_ignores_tagged_lines():
    p = parse_source_text("# T\n\n[caption] a picture\n\n## S\n\nBody one.\n[meta] x\n> quote\n")
    assert [x["text"] for x in p["paragraphs"]] == ["Body one.", "quote"] and p["paragraphs"][1]["kind"] == "quote"


def test_missing_project_files_do_not_crash(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    b = build_brief(d)
    assert b["sources"] == [] and b["paragraph_ids"] == []
