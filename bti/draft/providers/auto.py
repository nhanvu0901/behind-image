"""The no-model drafter: one shot per beat, the owner's picks first, the core techniques rotated.

It is the fallback when the agent fails or is not signed in, the baseline to compare the agent with, and what the tests use.
Pure function of the inputs: the same inputs give the same specs. The compiler then fills slots and parameters from the engine's
defaults and checks everything, so this module only decides WHICH technique, WHICH picture and WHICH region, and when.

Rules:
  * a beat with picks: its first pick (a beat with several picks and enough time is cut into one shot per pick);
  * a beat without a pick: the main painting; a region of the main painting whose name or label appears in the beat's `show` words
    (or its text) is looked at; otherwise the whole painting moves (push-in, hold, zoom, pull-back in turn);
  * the main painting with a region: zoom-and-shift or push-in to the region, with a spotlight or a ring on it;
  * another image of the project: a context still with a label strip (title, artist, year);
  * two pictures with role `compare`: the two-panel layout;
  * a beat shorter than 1.5 s is not a shot of its own (the previous shot continues).
"""
from __future__ import annotations

from ..inputs import SPEC_SCHEMA, DraftInputs, beat_picks, narration_notes

MIN_BEAT_S = 1.5
MIN_SEGMENT_S = 3.0
WHOLE_CYCLE = ("CAM-01", "STATIC-01", "CAM-05", "CAM-03")
DETAIL_CYCLE = ("CAM-05", "CAM-01")
OVERLAY_MIN_S = 3.5
INTENT = {"CAM-01": "explore", "STATIC-01": "establish", "CAM-03": "establish", "X-LAY-01": "context", "LAY-01": "compare",
          "FOOT-01": "context"}


def _region_for(asset: dict, texts: list[str]) -> str | None:
    regs = (asset or {}).get("regions") or {}
    hay = " ".join(texts).lower()
    for name, r in regs.items():
        label = str((r or {}).get("label") or "").lower()
        if (len(name) >= 3 and name.lower().replace("_", " ") in hay) or (len(label) >= 4 and label in hay):
            return name
    return None


class _State:
    def __init__(self):
        self.whole = 0
        self.detail = 0
        self.last = None


def _shot(beat: str, sw: int, tid: str, slots: dict, overlays=None, note: str = "", intent: str | None = None) -> dict:
    return {"beat": beat, "start_word": sw, "technique": tid, "intent": intent or INTENT.get(tid, "point_at"),
            "slots": slots, "params": {}, "overlays": overlays or [], "note": note}


def draft(inp: DraftInputs) -> dict:
    """chapter id -> spec (`bti.draft/1`) for every chapter of the timing."""
    words = inp.timing["words"]
    picks, assets = inp.picks, inp.picks["assets"]
    main = picks["main_asset"]
    notes = narration_notes(inp.narration)
    st = _State()
    out: dict = {}
    for ch in inp.timing["chapters"]:
        shots: list[dict] = []
        for b in [x for x in inp.timing["beats"] if x["chapter"] == ch["id"]]:
            dur = words[b["w1"] - 1]["e"] - words[b["w0"]]["s"]
            if dur < MIN_BEAT_S and shots:
                continue
            items = beat_picks(picks, b["id"])
            texts = list(notes.get(b["id"], {}).get("show", [])) + [b["text"]]
            if not items:
                reg = _region_for(assets[main], texts)
                items = [{"asset": main, "region": reg, "role": "main" if not reg else "detail", "note": ""}]
            n_seg = max(1, min(len(items), int(dur // MIN_SEGMENT_S))) if len(items) > 1 else 1
            segs = items[:n_seg] if n_seg < len(items) else items
            i = 0
            k = 0
            while i < len(segs):
                it = segs[i]
                sw = b["w0"] + int(round(k * (b["w1"] - b["w0"]) / len(segs))) if len(segs) > 1 else b["w0"]
                seg_end = b["w0"] + int(round((k + 1) * (b["w1"] - b["w0"]) / len(segs))) if len(segs) > 1 else b["w1"]
                seg_dur = words[seg_end - 1]["e"] - words[sw]["s"]
                nxt = segs[i + 1] if i + 1 < len(segs) else None
                a = assets.get(it["asset"]) or {}
                if a.get("kind") == "video":
                    shot = _shot(b["id"], sw, "FOOT-01", {"footage": {"asset": it["asset"]}})
                elif (it.get("role") == "compare" and nxt and nxt["asset"] != it["asset"] and (assets.get(nxt["asset"]) or {}).get("kind") == "image"
                      and a.get("kind") == "image"):
                    shot = _shot(b["id"], sw, "LAY-01", {"left": {"asset": it["asset"]}, "right": {"asset": nxt["asset"]}})
                    i += 1
                elif it["asset"] != main and a.get("kind") == "image":
                    ovs = []
                    title = str(a.get("title") or "").strip()
                    if title and len(title.split()) < 5 and seg_dur >= OVERLAY_MIN_S:
                        ovs = [{"technique": "X-ANN-02", "start_word": sw, "off": 0.5, "dur": 3.2, "params": {}}]
                    shot = _shot(b["id"], sw, "X-LAY-01", {"image": {"asset": it["asset"]}}, ovs)
                else:
                    region = it.get("region") if it.get("region") in (a.get("regions") or {}) else _region_for(a, texts) if it["asset"] == main else None
                    if region:
                        tid = DETAIL_CYCLE[st.detail % len(DETAIL_CYCLE)]
                        if tid == st.last:
                            st.detail += 1
                            tid = DETAIL_CYCLE[st.detail % len(DETAIL_CYCLE)]
                        st.detail += 1
                        ovs = []
                        r = a["regions"][region]
                        if seg_dur >= OVERLAY_MIN_S and r.get("rx"):
                            ovs = [{"technique": "HI-01" if (st.detail % 2) else "AN-01", "start_word": sw, "off": 0.4,
                                    "params": {"at": region}}]
                        shot = _shot(b["id"], sw, tid, {"image": {"asset": it["asset"], "region": region}}, ovs, intent="point_at")
                    else:
                        tid = WHOLE_CYCLE[st.whole % len(WHOLE_CYCLE)]
                        if tid == st.last:
                            st.whole += 1
                            tid = WHOLE_CYCLE[st.whole % len(WHOLE_CYCLE)]
                        st.whole += 1
                        shot = _shot(b["id"], sw, tid, {"image": {"asset": it["asset"]}})
                st.last = shot["technique"]
                shots.append(shot)
                i += 1
                k += 1
        out[ch["id"]] = {"schema": SPEC_SCHEMA, "chapter": ch["id"], "shots": shots}
    return out


NOTES = "Automatic draft: one shot per beat, the owner's picks first, core techniques in turn. No model was used."
