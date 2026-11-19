"""The project a run works on: a COPY of a sample project, made for the run and removed after it. A project of the owner is never the sample, never touched.

The sample projects are the reference projects of the tests, in the `projects/` folder of the repository (the samples root):

    arnolfini-from-books   a project made from three books (project.json, source/, script/outline.json, a model-made outline that was never approved)
    arnolfini              a finished video made from an earlier edit (storyboard.json, timing.json, audio, media); protected, no book data

A case names the sample and the STATE the copy starts from:

    book               the sample's project.json and sources; no script (the outline is asked for)
    outline_approved   the sample's own outline, approved (the narration is asked for)
    narration_approved the sample's own outline and narration, both approved (needs `script/narration.json` in the sample: the pictures step starts here)
    as_is              everything of the sample but caches, history and proposals (an edit of the storyboard starts here)
    as_is_locked       `as_is` with every fifth shot of the storyboard locked in the copy (a re-draft must leave those shots exactly as they are)
    redraft            `as_is` without storyboard.json, with an approved picks.json (the sample's own, or one made from the finished storyboard when the timing has beat
                       ids): the draft agent has the whole video to make again

The copy gets a folder name `eval-<run>-<n>-<repeat>`, lives under the projects root of the app the bench talks to, and is removed through the app's own delete route
(`DELETE /api/projects/{pid}?confirm={pid}`) unless `--keep`. `tree_hash` says whether a folder changed byte for byte: the run records that the sample did not.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
STARTS = ("book", "outline_approved", "narration_approved", "as_is", "as_is_locked", "redraft")
ALWAYS_SKIP = ("cache", "history", "proposals", "auto_runs", "changes", "auto.json", "agent.json", "__pycache__")


class SampleError(Exception):
    """The sample cannot be used for this start (not a failure of the agent): the repeat is skipped with this sentence."""


def tree_hash(path: Path | str) -> str:
    """One hash of every file under `path` (names and bytes): equal before and after means nothing was written."""
    h = hashlib.sha1()
    root = Path(path)
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(f.relative_to(root).as_posix().encode("utf-8") + b"\0")
        h.update(f.read_bytes())
        h.update(b"\1")
    return h.hexdigest()


def copy_project(samples_root: Path | str, sample: str, start: str, projects_root: Path | str, new_id: str) -> Path:
    """Copy the sample project into `projects_root/new_id` in the shape of `start`; returns the folder. Nothing is ever written under the samples root."""
    if start not in STARTS:
        raise SampleError("unknown start %r (one of %s)" % (start, ", ".join(STARTS)))
    src, dst = Path(samples_root) / sample, Path(projects_root) / new_id
    if not (src / "project.json").is_file() and not (src / "storyboard.json").is_file():
        raise SampleError("the sample project %s is not in %s" % (sample, samples_root))
    if dst.exists():
        raise SampleError("%s already exists in the projects root" % new_id)
    skip = set(ALWAYS_SKIP)
    if start in ("book", "outline_approved"):
        skip |= {"script"} if start == "book" else {"storyboard.json", "picks.json", "timing.json", "voice", "audio"}
    if start == "redraft":
        skip |= {"storyboard.json"}

    def ignore(folder: str, names: list[str]) -> list[str]:
        here = Path(folder)
        rel = here.relative_to(src)
        out = [n for n in names if n in skip and (rel == Path(".") or n in ("__pycache__",))]
        if start == "outline_approved" and rel == Path("script"):
            out += [n for n in names if n != "outline.json"]
        if start == "narration_approved" and rel == Path("script"):
            out += [n for n in names if n not in ("outline.json", "narration.json")]
        return out
    shutil.copytree(src, dst, ignore=ignore)
    _unprotect(dst)
    if start == "narration_approved" and not (dst / "script" / "narration.json").is_file():
        shutil.rmtree(dst)                                   # the copy this function just made (never anything else)
        raise SampleError("the sample project %s has no script/narration.json: the pictures step needs a project with an approved narration" % sample)
    if start == "as_is_locked":
        _lock_every_fifth(dst)
    if start == "redraft":
        _picks_for_redraft(src, dst)
    return dst


def _lock_every_fifth(dst: Path) -> None:
    f = dst / "storyboard.json"
    try:
        sb = json.loads(f.read_text(encoding="utf-8"))
        for i, s in enumerate(sb.get("shots") or []):
            if i % 5 == 4:
                s["locked"] = True
        f.write_text(json.dumps(sb, ensure_ascii=False, indent=1), encoding="utf-8")
    except (OSError, ValueError):
        raise SampleError("the sample has no storyboard.json to lock shots in")


def _unprotect(dst: Path) -> None:
    """A reference project says `protected: true` (the app refuses to delete it): the copy is the bench's own, so it can be removed through the app."""
    f = dst / "project.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.pop("protected", None)
    d["eval_copy"] = True
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _picks_for_redraft(src: Path, dst: Path) -> None:
    """The draft needs an approved picks.json. The sample's own is used; without one it is made from the finished storyboard (the pictures the video shows on
    each line are what the owner would have picked), which needs a timing whose beats have ids (a project made by the app, not an old import)."""
    if (dst / "picks.json").is_file():
        return
    try:
        sb = json.loads((src / "storyboard.json").read_text(encoding="utf-8"))
        tm = json.loads((dst / "timing.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SampleError("the sample has no storyboard.json and timing.json to make the picks from")
    if not all(isinstance(b, dict) and b.get("id") for b in tm.get("beats") or []):
        raise SampleError("the timing of the sample has no beat ids (an old import): use a project made by the app for the draft cases")
    from .criteria import shot_spans
    assets = {k: {f: a[f] for f in ("file", "kind", "title", "artist", "year", "width", "height", "regions", "credit") if f in a} for k, a in (sb.get("assets") or {}).items()}
    main = "A" if "A" in assets else next(iter(assets))
    beats: dict[str, Any] = {}
    spans = shot_spans(sb, tm)
    for b in tm.get("beats") or []:
        first = next(((s, t0) for s, t0, t1 in spans if b["start"] - 0.01 <= t0 < b["end"]), None)
        slot = ((first[0].get("slots") or {}).get("image") or {}) if first else {}
        if slot.get("asset") and (slot["asset"] != main or slot.get("region")):
            beats[b["id"]] = {"items": [{"asset": slot["asset"], "region": slot.get("region"), "role": "detail", "note": ""}], "status": "picked"}
    doc = {"schema": "bti.picks/1", "main_asset": main, "assets": assets, "beats": beats, "approval": {"approved": True}}
    (dst / "picks.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def approve_through_the_app(transport, pid: str, start: str, timeout: float = 60.0) -> None:
    """Put the copy at the gate the start says, with the app's own routes: the copy's `auto.json` lets an agent approve (it is the bench's own copy), then the outline
    and the narration are approved as the actor `agent:eval`."""
    if start not in ("outline_approved", "narration_approved"):
        return
    from urllib.parse import quote
    P = "/api/projects/%s" % quote(pid, safe="")

    def need(method, path, body=None):
        r = transport.request(method, path, body, timeout)
        if not r.ok:
            d = r.data if isinstance(r.data, dict) else {}
            raise SampleError("%s %s: HTTP %s %s" % (method, path, r.status, d.get("code") or d.get("detail") or r.text[:80]))
        return r.data
    auto = need("GET", P + "/auto")
    need("PUT", P + "/auto", {"base_rev": auto["rev"], "enabled": True})
    need("POST", P + "/outline/approve", {"rev": need("GET", P + "/outline")["rev"], "actor": "agent:eval"})
    if start == "narration_approved":
        need("POST", P + "/narration/approve", {"rev": need("GET", P + "/narration")["rev"], "actor": "agent:eval"})
