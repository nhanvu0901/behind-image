"""A one-off proof of `picks.retry_missing` on the saved files of the first real run of the automatic choice of pictures (project `eligius`, 2026-11-20), by the worker fixes4:
`tools/deploy/snapshot_py.sh fixes4 tests/e2e/picks_auto/retry_proof.py` (from the folder of the snapshot; the inputs are read-only copies made by the caller). Not a test:
nothing imports it and no test runs it.

Input (copies; the caller made them): `proof_in/` holds `choice.json`, `choice2.json`, `plan.json`, `search.json`, `last.json` (projects/eligius/cache/picks_auto/), `narration.json`,
`outline.json`, `project.json` (projects/eligius/ and its script/) and `picks.json` (the real picks as they stand now, with the six lines already fixed by hand: used only to compare
the shape of a result with the coordinator's own hand-made batches, never as a starting point).

What it does, in a project of its own under `proof_out/` (nothing outside the snapshot is written, no network, no model, no key):
  1. a project with the real narration and a picks document of only the main painting (a file the size of nothing: the pixels are never read);
  2. the WRITE PART of the agent's job (`bti.picks.auto.write.run`) from the saved plan, search and choices, with the downloads of the lines that the real run lost
     (`last.json` result.missing, code `import_limited`) refused as the real source refused them: it must reproduce the real `missing` list;
  3. `picks.retry_missing` (`bti.picks.auto.retry.run`) with the source giving its pictures: which candidate it downloads for each of the six lines, and how each line is written;
  4. the lines compared with the real `picks.json` (the hand-made batches `ops_*.json`): the same pictures in the same order, nothing missing."""
import json
import re
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from PIL import Image                                                           # noqa: E402

from bti.media import assets as media_assets                                    # noqa: E402
from bti.picks import context, doc, service                                     # noqa: E402
from bti.picks.auto import inputs as ainputs, retry, search as asearch, store, webround, write as awrite       # noqa: E402
from bti.picks.errors import PicksError                                         # noqa: E402

IN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "proof_in"
OUT = REPO / "proof_out"
PID = "eligius"
EXPECTED = {                                                                    # the brief's answer: line -> the file the agent chose
    "b0029": "File:Philipp the Good - Van der Weyden.jpg",
    "b0035": "File:Charles the Bold 1460.jpg",
    "b0051": "File:Portrait of a Man by Jan van Eyck.jpg",
    "b0042": "File:The Arnolfini Portrait, détail (2).jpg",
    "b0025": "File:Jacques de Guise, Chroniques de Hainaut, frontispiece, KBR 9242 (cropped).jpg",
    "b0055": "File:Pluenderung Grandson.jpg",
}


def read(name):
    return json.loads((IN / name).read_text(encoding="utf-8"))


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------------------------- the project
if OUT.exists():
    shutil.rmtree(OUT)                                                          # the snapshot's own proof folder, made by an earlier run of this script
pdir = OUT / PID
(pdir / "script").mkdir(parents=True)
(pdir / "media").mkdir()
for src, dst in (("narration.json", "script/narration.json"), ("outline.json", "script/outline.json"), ("project.json", "project.json")):
    shutil.copy(IN / src, pdir / dst)
real = read("picks.json")
main_key = real["main_asset"]
main = dict(real["assets"][main_key])
Image.new("RGB", (8, 8), (90, 80, 70)).save(pdir / main["file"])                # a file of the right name; its pixels are never read (the size is the document's)
plan_regions = set(json.loads((IN / "plan.json").read_text(encoding="utf-8"))["plan"]["regions"])      # the boxes that run proposed (the plan leaves out the ones the painting already had)
main["regions"] = {n: r for n, r in main["regions"].items() if n not in plan_regions and not any(re.fullmatch(re.escape(p) + r"_\d+", n) for p in plan_regions)}      # the painting as that run found it
start = doc.empty()
start["main_asset"] = main_key
start["assets"][main_key] = main
with doc.Held(pdir):
    doc.save(pdir, start)
nv = context.narration_view(pdir)
assert nv["present"] and nv["approved"], "the real narration must be approved: %s" % nv["reason"]
say("project: %d lines, main painting %s (%d x %d)" % (len(nv["beat_ids"]), main_key, main["width"], main["height"]))

# ---------------------------------------------------------------------------------------------------------------- the saved files, as the write part read them
plan_d, search, c1 = read("plan.json"), read("search.json"), read("choice.json")
c2 = read("choice2.json")
plan = plan_d["plan"]
choice = webround.merge_choice(c1["choice"], c2["choice"], search)             # the job's own merge of the first and the second choice
last = read("last.json")["result"]
lost_wants = sorted({m["want"] for m in last["missing"] if m["code"] == "import_limited"})
say("the real run lost the download of %d chosen pictures (last.json, import_limited): %s" % (len(lost_wants), ", ".join(lost_wants)))

# ---------------------------------------------------------------------------------------------------------------- a source that gives pictures (fake files, no network)
DOWNLOADS: list[tuple[str, str]] = []
STATE = {"refuse_wants": set(), "rows": {}}


def fake_fetch(pdir_, source, sid):
    """`bti.picks.service.fetch_asset` without the network: a small file, registered in the project's index like the real import does. The pictures of the lines that the real
    run lost are refused with "too many requests" while STATE says so."""
    ident = "%s:%s" % (source, sid)
    idx = media_assets.load_index(pdir_)
    hit = idx["items"].get(ident)
    if hit and (Path(pdir_) / hit["asset"]["file"]).is_file():
        return {"asset_key": hit["key"], "asset": hit["asset"]}
    wants = {r["id"] for r in STATE["rows"].values() if r["pick"] and (r["pick"]["source"], r["pick"]["source_id"]) == (source, sid)}
    if wants & STATE["refuse_wants"]:
        raise PicksError(503, "the image source limits downloads", "source_rate_limited", retryable=True, retry_after=None)
    DOWNLOADS.append((source, sid))
    title = sid.split(":", 1)[-1].rsplit(".", 1)[0][:80]
    key = media_assets.make_key(title, ident, media_assets.taken_keys(pdir_, idx))
    dest = media_assets.media_dir(pdir_, True) / (key + ".jpg")
    Image.new("RGB", (8, 8), (120, 110, 100)).save(dest)
    asset = media_assets.build_asset("media/" + dest.name, "image", title, "", "", 1500, 1200, {"source": source, "source_url": "", "author": "", "licence": "", "flag": None})
    media_assets.register(pdir_, ident, key, asset, True)
    return {"asset_key": key, "asset": asset}


service.fetch_asset = fake_fetch                                                # the batches of the write part reach the source through the module's own name
STATE["rows"] = awrite.resolve_picks(plan, search, choice, search.get("books") or [])
STATE["refuse_wants"] = set(lost_wants)

# ---------------------------------------------------------------------------------------------------------------- 2. the write part
for name, d in (("plan.json", plan_d), ("search.json", search), ("choice.json", c1), ("choice2.json", c2)):
    store.write(pdir, name, d)                                                  # the project's own cache folder, as the real run left it
inp = ainputs.load(pdir, None)
run_state = {}
res = awrite.run(pdir, inp, plan, search, choice, run_state, actor="agent:proof", cancelled=lambda: False, progress=lambda f, n: None, fetch_asset=fake_fetch)
mine = sorted((m["beat"], m["code"]) for m in res["missing"])
theirs = sorted((m["beat"], m["code"]) for m in last["missing"])
say("\n== the write part from the saved files: %d lines written, %d pictures imported (the real run: %d lines, %d pictures)" %
    (res["lines_done"], res["pictures_imported"], last["lines_done"], last["pictures_imported"]))
say("   lines without: %s" % res["lines_without"][:3])
say("its `missing` list equals the real run's: %s (%d entries)" % (mine == theirs, len(mine)))
assert mine == theirs, (mine, theirs)
before = doc.load(pdir)
for b in EXPECTED:
    v = before["beats"][b]
    say("   before %s: items %s | missing %s" % (b, [(i["role"], i["region"]) for i in v["items"]], v.get("missing")))
DOWNLOADS.clear()
STATE["refuse_wants"] = set()                                                   # the source gives its pictures again (the coordinator's batches worked at once)

# ---------------------------------------------------------------------------------------------------------------- 3. the retry
facts = retry.facts(pdir, before)
say("\n== the state answer would say: lines %s, saved files there: %s, not looked at yet: %s" % (facts["lines"], facts["files"], facts["untried"]))
r = retry.run(pdir, actor="cli:proof", cancelled=lambda: False, progress=lambda f, n: None, fetch_asset=fake_fetch)
say("== picks.retry_missing: %s" % retry.result_sentence(r))
say("   fixed %s | still limited %s | left alone %s | pictures imported %d | batches %d" % (r["lines_fixed"], r["lines_still_limited"], r["lines_left"], r["pictures_imported"], len(r["batches"])))
say("\nWHICH CANDIDATE IT TAKES FOR EACH LINE (downloaded, in order):")
by_line = {}
for src, sid in DOWNLOADS:
    for b in {x["beat"] for x in STATE["rows"].values() if x["pick"] and (x["pick"]["source"], x["pick"]["source_id"]) == (src, sid)}:
        by_line[b] = sid
ok = True
for b, want in EXPECTED.items():
    got = by_line.get(b)
    row = next(x for x in STATE["rows"].values() if x["beat"] == b and x["pick"] and x["pick"]["source_id"] == want)
    in1 = c1["choice"]["wants"].get(row["id"]) or {}
    in2 = c2["choice"]["wants"].get(row["id"]) or {}
    pick2 = in2.get("pick")
    where = ("choice2.json pick %s -> round2.map[%s][%d] = candidate %d" % (pick2, row["id"], pick2[1] - 1, search["round2"]["map"][row["id"]][pick2[1] - 1])
             if pick2 and in1.get("pick") is None else "choice.json pick %s" % (in1.get("pick"),))
    say("  %s  %-6s %s   [%s]  %s" % ("OK " if got == want else "BAD", b, got, where, row["what"]))
    ok = ok and got == want
assert ok and set(by_line) == set(EXPECTED), by_line

# ---------------------------------------------------------------------------------------------------------------- 4. the result, line by line, against the real picks
after = doc.load(pdir)
shape = lambda d, b: [(i["role"], i["region"], d["assets"][i["asset"]]["title"] if i["role"] != "main" and i["asset"] != main_key else i["asset"]) for i in d["beats"][b]["items"]]
say("\nTHE LINES AS WRITTEN (role, region, asset)  vs  the real picks.json after the coordinator's hand-made batches:")
same = True
for b in EXPECTED:
    a, h = after["beats"][b], real["beats"][b]
    roles_a = [(i["role"], i["region"]) for i in a["items"]]
    roles_h = [(i["role"], i["region"]) for i in h["items"]]
    titles_a = [after["assets"][i["asset"]]["title"] for i in a["items"] if i["role"] == "context"]            # the picture that was missing: the same file
    titles_h = [real["assets"][i["asset"]]["title"] for i in h["items"] if i["role"] == "context"]
    row_ok = roles_a == roles_h and titles_a == titles_h and "missing" not in a and "Chưa tìm được" not in a["note"]
    same = same and row_ok
    say("  %s %s\n     items   %s\n     real    %s\n     note    %s\n     first item's note: %s" %
        ("OK " if row_ok else "BAD", b, shape(after, b), shape(real, b), a["note"], (a["items"][0]["note"] if a["items"] else "")[:110]))
say("\nlines with `missing` after the retry (all lines): %s" % sorted(b for b, v in after["beats"].items() if v.get("missing")))
say("lines still saying import_limited: %s" % retry.lines_with_limit(after))
assert same
assert not retry.lines_with_limit(after)
say("\nPROOF OK: the six lines get the candidates of the brief, nothing else is touched (%d other lines unchanged: %s)" % (
    sum(1 for b in after["beats"] if b not in EXPECTED and after["beats"][b] == before["beats"][b]), "yes" if all(after["beats"][b] == before["beats"][b] for b in after["beats"] if b not in EXPECTED) else "NO"))
