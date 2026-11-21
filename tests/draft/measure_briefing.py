"""How big is the briefing of the prompt box? (worker c2box) Builds the real briefings of both boxes on the fixture projects and prints their size in
characters, by part. No model is called. Run on the server through the snapshot helper:

    BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_py.sh c2box tests/draft/measure_briefing.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "tests" / "ops", REPO / "tests" / "picks", REPO / "tests" / "script"):
    sys.path.insert(0, str(p))

from bti.draft import boxops as B, fastedit, picksedit          # noqa: E402
from bti.draft.inputs import load_inputs                          # noqa: E402
from bti.picks import context                                     # noqa: E402


def parts(text: str) -> dict:
    """Characters of each `##` section of a briefing."""
    out, cur, buf = {}, "head", []
    for ln in text.splitlines(True):
        m = re.match(r"^#{2,3} (.+)", ln)
        if m and ln.startswith("## "):
            out[cur] = out.get(cur, 0) + len("".join(buf))
            cur, buf = m.group(1)[:50], []
        buf.append(ln)
    out[cur] = out.get(cur, 0) + len("".join(buf))
    return out


def storyboard(pdir: Path, label: str, payloads: dict, instruction: str):
    be = B.Backend(pdir)
    for name, payload in payloads.items():
        inp = load_inputs(pdir, for_edit=True)
        doc, _ = be.read("storyboard")
        scope = fastedit.storyboard_scope(inp, doc, payload)
        facts = be.adapter("storyboard").facts(doc)
        text = fastedit.build_briefing(inp, doc, facts, scope, instruction, [])
        print("storyboard %-10s %-22s %6d chars, %d shots in scope" % (label, name, len(text), len(scope.ids)))
        if name == list(payloads)[0]:
            for k, v in parts(text).items():
                print("      %-48s %6d" % (k, v))


def pictures(pdir: Path, label: str, payloads: dict, instruction: str):
    be = B.Backend(pdir)
    for name, payload in payloads.items():
        doc, _ = be.read("picks")
        facts = be.adapter("picks").facts(doc)
        nv = context.narration_view(pdir)
        scope = picksedit.picks_scope(facts, doc, payload, nv)
        text = picksedit.build_briefing(facts, nv, doc, scope, instruction, [])
        print("picks      %-10s %-22s %6d chars, %d lines in scope" % (label, name, len(text), len(scope.ids)))
        if name == list(payloads)[0]:
            for k, v in parts(text).items():
                print("      %-48s %6d" % (k, v))


def main():
    from ops_helpers import make_project
    tmp = Path(tempfile.mkdtemp(prefix="bti-measure-"))
    try:
        ops1 = make_project(tmp / "p")
        storyboard(ops1, "ops1", {"one shot": {"shots": ["s0002"]}, "two shots": {"shots": ["s0002", "s0004"]}, "chapter": {"chapter": "c02"},
                                   "all (10)": {"all": True}}, "làm vòng sáng ở cảnh này to hơn")
        pictures(ops1, "ops1", {"one line": {"beats": ["b0003"]}, "all": {"all": True}}, "dòng này chỉ cho xem khuôn mặt rồi cả bức tranh")
        src = REPO / "projects" / "arnolfini"
        if (src / "storyboard.json").is_file():
            dst = tmp / "arn"
            dst.mkdir()
            shutil.copytree(src / "media", dst / "media")
            for f in ("timing.json", "storyboard.json"):
                shutil.copyfile(src / f, dst / f)
            sb = json.loads((src / "storyboard.json").read_text(encoding="utf-8"))
            tm = json.loads((src / "timing.json").read_text(encoding="utf-8"))
            (dst / "picks.json").write_text(json.dumps({"schema": "bti.picks/1", "main_asset": "A", "assets": sb["assets"],
                                                         "beats": {"b%04d" % i: {"items": [], "status": "todo"} for i, _ in enumerate(tm["beats"], 1)},
                                                         "approval": {"approved": True}}), encoding="utf-8")
            ids = [s["id"] for s in sb["shots"]]
            storyboard(dst, "arnolfini", {"one shot": {"shots": [ids[10]]}, "two shots": {"shots": ids[10:12]}, "12 shots": {"shots": ids[10:22]}},
                       "làm chậm cú zoom ở cảnh này")
        else:
            print("projects/arnolfini is not on this machine")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
