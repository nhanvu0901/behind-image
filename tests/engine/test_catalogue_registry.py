"""Worker catalogue (2026-11-20): the registry says which techniques a model is shown (`offered`) and, for every one it is shown, in which case to use it. The 86 entries of
`style/gae/techniques.json`: 26 offered with four texts each (`use_when`, `needs`, `never_when`, `example`), 60 hidden with a reason; the document the model reads
(`inputs/techniques.md`) shows exactly the offered set, grouped by the kind of line it serves, and the examples are real sentences of the two finished narrations."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import bti.engine.api  # noqa: F401  (registers the techniques)
from bti.draft import techniques_md as T
from bti.engine import registry as R
from bti.engine import viewchecks as VC

FIX = Path(__file__).parent / "fixtures" / "catalogue"
BUNDLE = R.load_bundle("gae")
ALL = {t["id"]: t for t in BUNDLE.techniques}
OFFERED = ["CAM-01", "CAM-05", "CAM-03", "CAM-04", "STATIC-01", "X-ANN-01", "AN-01", "HI-01", "KEY-01", "DOC-01", "AN-03", "AN-06", "AN-05", "X-ANN-03", "X-LAY-01", "X-ANN-02",
           "LAY-01", "X-CMP-01", "FOOT-01", "STATE-01", "MAP-01", "TIME-01", "NUM-01", "STATIC-09", "TREE-01", "TR-01"]       # the table of the brief
CODES = {"program", "other_format", "replaced", "no_material", "redundant"}
KINDS = {"detail", "whole", "outside", "compare", "journey", "dates", "figure", "inscription", "construction", "relations", "idea"}


def test_the_catalogue_has_86_entries_and_the_26_of_the_table_are_offered():
    assert len(ALL) == 87
    assert sorted(i for i, t in ALL.items() if t["offered"]) == sorted(OFFERED) and len(OFFERED) == 26
    assert BUNDLE.offered_ids() and sorted(BUNDLE.offered_ids()) == sorted(OFFERED)


def test_every_entry_is_offered_or_has_a_reason_and_never_both():
    for tid, t in ALL.items():
        assert isinstance(t.get("offered"), bool), tid
        assert ("hidden_reason" in t) == (not t["offered"]), tid
        if not t["offered"]:
            hr = t["hidden_reason"]
            assert set(hr) == {"code", "use", "note"} and hr["code"] in CODES and isinstance(hr["use"], list) and len(hr["note"]) >= 20, tid
            assert all(u in OFFERED for u in hr["use"]), (tid, "`use` names offered techniques only")
            if hr["code"] in ("replaced", "redundant"):
                assert hr["use"], (tid, "a replaced or redundant technique names the offered one that does its job")
            if hr["code"] in ("program", "no_material", "other_format"):
                assert not hr["use"], tid
            assert not any(k in t for k in ("use_when", "needs", "never_when", "example", "serves")), (tid, "a hidden technique has no use case")


def test_the_reasons_are_counted_as_decided():
    n = {c: sum(1 for t in ALL.values() if (t.get("hidden_reason") or {}).get("code") == c) for c in CODES}
    assert sum(n.values()) == 61 and n["program"] == 14 and n["no_material"] == 17 and n["other_format"] == 14 and n["replaced"] == 7 and n["redundant"] == 9, n


def test_the_identity_family_and_the_cards_are_written_by_the_program():
    from bti import identity as ID
    cfg = ID.read(BUNDLE.style)
    family = {t for t in ALL if cfg.is_identity_technique(t)}
    assert family == {"ID-OPEN-01", "ID-OPEN-02", "ID-LABEL-01", "ID-BRAND-01", "ID-BRAND-02", "ID-BRAND-03", "ID-BRAND-04", "ID-MARK-01", "ID-MARK-02"}
    for tid in family | {"X-CARD-01", "X-CARD-02", "TXT-01", "X-TR-01", "TR-04"}:
        assert ALL[tid]["hidden_reason"]["code"] == "program", tid


def test_an_offered_technique_has_four_texts_in_full_and_the_kinds_it_serves():
    for tid in OFFERED:
        t = ALL[tid]
        assert t["serves"] and set(t["serves"]) <= KINDS and len(set(t["serves"])) == len(t["serves"]), tid
        for k in ("use_when", "needs", "never_when", "example"):
            assert isinstance(t[k], str) and len(t[k]) >= 20, (tid, k)
        assert len(t["use_when"]) >= 150 and len(t["never_when"]) >= 60, (tid, "written out in full, not a keyword")
        assert "usage_rule" in t and t["evidence"], (tid, "the record of where the technique came from stays in the file")


def test_the_use_texts_say_the_kind_of_line_the_device_serves():
    for tid, kind in (("MAP-01", "journey"), ("TIME-01", "dates"), ("NUM-01", "figure"), ("DOC-01", "inscription"), ("AN-03", "construction"), ("AN-06", "construction"),
                      ("TREE-01", "relations"), ("LAY-01", "compare"), ("X-CMP-01", "compare"), ("X-LAY-01", "outside")):
        assert kind in ALL[tid]["serves"], tid
    for tid, kinds in VC.DEVICE_KINDS.items():
        assert set(kinds) <= set(ALL[tid]["serves"]), (tid, "the check and the catalogue agree on what the device serves")
    assert "one place" in ALL["MAP-01"]["never_when"] or "One place" in ALL["MAP-01"]["never_when"]
    assert "outside" in ALL["MAP-01"]["never_when"] and "Limoges" in ALL["MAP-01"]["never_when"]
    assert "default fit" in ALL["X-LAY-01"]["never_when"] and "1000 px" in ALL["X-LAY-01"]["never_when"]
    assert "thing counted" in ALL["NUM-01"]["needs"].lower() or "THING COUNTED" in ALL["NUM-01"]["needs"]


NARRATIONS = {"St. Eligius": "eligius", "Arnolfini": "arnolfini"}


def beat_texts():
    out = {}
    for label, key in NARRATIONS.items():
        tm = json.loads((FIX / key / "timing.json").read_text(encoding="utf-8"))
        out[label] = {b["id"]: b["text"] for b in tm["beats"]}
    return out


def test_an_example_is_a_real_sentence_of_the_two_narrations_with_its_line_id_or_says_there_is_none():
    texts = beat_texts()["St. Eligius"]
    arnolfini_words = re.compile(r"arnolfini|van\s*eyck|costanza|giovanni|1434|1433|panofsky", re.I)
    real = 0
    for tid in OFFERED:
        ex = ALL[tid]["example"]
        assert not arnolfini_words.search(ex), (tid, "example must not mention the Arnolfini Portrait")
        if ex.startswith("No sentence in the two narrations calls for it"):
            continue
        eligius_quoted = re.findall(r'St\. Eligius (b\d{4}): "([^"]+)"', ex)
        if eligius_quoted:
            for bid, quote in eligius_quoted:
                line = texts.get(bid, "")
                assert " ".join(quote.split()) in " ".join(line.split()), (tid, bid, "the quoted words are in the line")
                real += 1
        else:
            other_quoted = re.findall(r'"([^"]+)"', ex)
            assert other_quoted, (tid, "an example quotes a concrete sample sentence")
            real += len(other_quoted)
    assert real >= 20
    assert sorted(t for t in OFFERED if ALL[t]["example"].startswith("No sentence")) == ["AN-05", "AN-06", "STATE-01", "TREE-01"]


def test_no_arnolfini_mentions_in_offered_technique_text_fields():
    arnolfini_words = re.compile(r"arnolfini|van\s*eyck|costanza|giovanni|1434|1433|panofsky", re.I)
    for tid in OFFERED:
        t = ALL[tid]
        for field in ("description", "usage_rule", "use_when", "needs", "never_when", "example"):
            assert not arnolfini_words.search(t.get(field) or ""), (tid, field)


def test_no_arnolfini_mentions_in_param_defaults():
    banned = re.compile(r"arnolfini|van\s*eyck|costanza|giovanni|bruges|lucca|1434|1433|pelts|van der paele|philip the good", re.I)

    def walk(val):
        if isinstance(val, str):
            assert not banned.search(val), val
        elif isinstance(val, list):
            for x in val:
                walk(x)
        elif isinstance(val, dict):
            for x in val.values():
                walk(x)

    for tid, t in ALL.items():
        for p in t.get("params") or []:
            walk(p.get("default"))
            if p.get("pattern_hint"):
                assert not banned.search(p["pattern_hint"]), (tid, p["name"], "pattern_hint")
            for f in p.get("fields") or []:
                walk(f.get("default"))
                if f.get("pattern_hint"):
                    assert not banned.search(f["pattern_hint"]), (tid, p["name"], f["name"], "pattern_hint")


def test_an_example_never_tells_the_model_what_an_earlier_video_did_not_use():
    """fixes4: on the first real draft the model read, for AN-03, "(the finished video used only a camera move here)" and wrote in its notes "a camera move on the shelves serves this
    line, as it did in the finished reference video": the example named the answer the technique is there to replace. An example is the sentence, never what a video did with it."""
    ex = ALL["AN-03"]["example"]
    assert ex.startswith("St. Eligius b0043: \"Look at the shelves behind the saint.") and "camera move" not in ex and "finished video" not in ex
    for tid in OFFERED:
        assert "used only" not in ALL[tid]["example"] and "did not use" not in ALL[tid]["example"], tid


# ----------------------------------------------------------------------------------------------------------------- inputs/techniques.md
@pytest.fixture(scope="module")
def md():
    return T.generate(BUNDLE)


def headings(md):
    return re.findall(r"^### (\S+) ", md, re.M)


def test_the_generated_document_shows_exactly_the_offered_set_then_the_program_ones(md):
    body, program = md.split("## Written by the program")
    assert sorted(headings(body)) == sorted(OFFERED) and len(headings(body)) == len(set(headings(body)))
    assert sorted(headings(program)) == sorted(t for t, v in ALL.items() if (v.get("hidden_reason") or {}).get("code") == "program")


def test_a_hidden_technique_is_not_named_as_a_choice_anywhere_before_the_program_section(md):
    body = md.split("## Written by the program")[0]
    hidden = [t for t, v in ALL.items() if not v["offered"] and v["hidden_reason"]["code"] != "program"]
    assert hidden
    for tid in hidden:
        assert not re.search(r"(?<![A-Z0-9-])%s(?![A-Z0-9-])" % re.escape(tid), body), tid


def test_every_offered_entry_carries_its_four_texts_in_its_own_section(md):
    for tid in OFFERED:
        i = md.index("### %s " % tid)
        sec = md[i:md.find("\n### ", i + 5) if md.find("\n### ", i + 5) > 0 else len(md)]
        for label, key in (("use when", "use_when"), ("needs", "needs"), ("never when", "never_when"), ("real sentence", "example")):
            assert "- %s: %s" % (label, " ".join(ALL[tid][key].split())) in sec, (tid, label)
        assert "- serves: " in sec and "- slots:" in sec and "- params:" in sec


def test_the_techniques_are_grouped_by_the_first_kind_they_serve(md):
    groups = re.split(r"^## ", md, flags=re.M)
    seen = {}
    for g in groups:
        m = re.match(r"The techniques for lines of kind `(\w+)`", g)
        if m:
            for tid in re.findall(r"^### (\S+) ", g, re.M):
                seen[tid] = m.group(1)
    assert set(seen) == set(OFFERED)
    for tid, kind in seen.items():
        assert kind == ALL[tid]["serves"][0], tid
    assert seen["MAP-01"] == "journey" and seen["NUM-01"] == "figure" and seen["X-LAY-01"] == "outside" and seen["LAY-01"] == "compare" and seen["AN-03"] == "construction"


def test_the_index_by_kind_names_every_kind_and_lists_a_technique_under_each_kind_it_serves(md):
    idx = md[md.index("## Choosing by the kind of line"):md.index("## The channel identity")]
    for kind in T.KIND_ORDER:
        line = next(l for l in idx.splitlines() if l.startswith("- **%s**" % kind))
        for tid in OFFERED:
            assert bool(re.search(r"(?<![A-Z0-9-])%s(?![A-Z0-9-])" % re.escape(tid), line.split("): ", 1)[1])) == (kind in ALL[tid]["serves"]), (kind, tid)
    assert "Choosing by intent" not in md and "SHORTS ONLY" not in md


def test_the_document_says_hidden_techniques_are_errors_and_devices_follow_kinds(md):
    assert "technique_not_offered" in md and "Use a device on every beat whose kinds call for it" in md and "Every beat of `inputs/beats.json` has `kinds`" in md


def test_the_program_section_is_short_and_marks_every_entry_program_only(md):
    sec = md[md.index("## Written by the program"):]
    heads = [l for l in sec.splitlines() if l.startswith("### ")]
    assert len(heads) == 14 and all("PROGRAM ONLY" in l for l in heads)
    assert "- params:" not in sec and len(sec) < 6_000, "no parameters: a model never writes them"


def test_the_document_is_shorter_than_the_one_of_all_86(md):
    assert len(md) < 70_000


def test_the_size_of_the_four_texts_of_all_offered_entries_is_bounded():
    total = sum(len(ALL[t][k]) for t in OFFERED for k in ("use_when", "needs", "never_when", "example"))
    assert 15_000 < total < 40_000, total


# ----------------------------------------------------------------------------------------------------------------- the bundle
def test_the_bundle_says_what_to_use_instead_of_a_hidden_technique():
    assert BUNDLE.offered("CAM-01") and not BUNDLE.offered("STATIC-04") and not BUNDLE.offered("NOPE-99")
    text = BUNDLE.not_offered_text("STATIC-04")
    assert "STATIC-04" in text and "not one of the techniques you are offered" in text and "Use DOC-01 instead." in text
    assert "Use STATIC-01 or X-ANN-01 instead." in BUNDLE.not_offered_text("CAM-06")
    assert "Leave it out." in BUNDLE.not_offered_text("ID-MARK-01") and "writes the chapter marks" in BUNDLE.not_offered_text("ID-MARK-01")
    assert "Use MAP-01 instead." in BUNDLE.not_offered_text("AN-04")
    assert "Needs cut-out figures" in BUNDLE.not_offered_text("CAM-02") and "Use" not in BUNDLE.not_offered_text("CAM-02")


def test_a_registry_without_the_field_offers_everything():
    b = R.StyleBundle("gae")
    for t in b.techniques:
        t.pop("offered", None)
        t.pop("hidden_reason", None)
    assert all(b.offered(t["id"]) for t in b.techniques)
