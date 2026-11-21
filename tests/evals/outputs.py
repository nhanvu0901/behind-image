"""Prepared outputs for the tests of the criteria: documents of the shape the app's routes give, small, with one thing wrong at a time."""
import copy


def paragraph_ids(n=6, prefix="PAY"):
    return ["%s-%02d" % (prefix, i + 1) for i in range(n)]


def brief():
    return {"sources": [{"code": "PAY", "author": "James Payne", "included": True, "paragraphs": [{"id": i, "text": "t"} for i in paragraph_ids(6, "PAY")]},
                        {"code": "HOD", "author": "Susie Hodge", "included": True, "paragraphs": [{"id": i, "text": "t"} for i in paragraph_ids(4, "HOD")]},
                        {"code": "MAD", "author": "Edward Brooke-Hitching", "included": False, "paragraphs": [{"id": i, "text": "t"} for i in paragraph_ids(3, "MAD")]}]}


def outline():
    facts = [{"id": "f%02d" % i, "claim": "claim %d" % i, "sources": ["PAY-%02d" % i, "HOD-01"], "certainty": "established", "conflict": None} for i in range(1, 6)]
    facts[2].update(certainty="disputed", conflict="PAY-03 against HOD-01")
    roles = ["cold_open", "chapter", "chapter", "chapter", "chapter", "closing"]
    chapters = [{"id": "c%02d" % (i + 1), "role": r, "title": "T%d" % i, "word_budget": 333, "facts": ["f%02d" % ((i % 5) + 1)], "purpose": "p"} for i, r in enumerate(roles)]
    return {"thesis": "Is this a wedding or a memorial?", "hook_options": [{"id": "h1", "text": "a"}, {"id": "h2", "text": "b"}, {"id": "h3", "text": "c"}], "hook_choice": "h2",
            "chapters": chapters, "facts": facts, "target_words": 2000}


def outline_outputs():
    return {"outline": outline(), "issues": [{"level": "info", "code": "x", "message": "m"}], "brief": brief()}


def narration_text(words, sentence=10):
    return " ".join(("w%d" % i) + ("." if (i + 1) % sentence == 0 else "") for i in range(words))


def narration(per_chapter=333, sentence=10):
    o = outline()
    chapters = []
    for c in o["chapters"]:
        beats = [{"id": "b%s%d" % (c["id"], k), "text": narration_text(per_chapter // 4, sentence), "facts": c["facts"], "show": ["D1"]} for k in range(4)]
        chapters.append({"id": c["id"], "title": c["title"], "beats": beats})
    return {"chapters": chapters}


def narration_outputs():
    return {"narration": narration(), "outline": outline(), "brief": brief(),
            "issues": [{"level": "info", "code": "overlap", "message": "12% of the words sit in runs of 8 or more words"}]}


def timing():
    words = [{"w": "w%d" % i, "s": i * 0.5, "e": i * 0.5 + 0.4} for i in range(200)]
    beats = [{"id": "b%04d" % (k + 1), "chapter": "c01" if k < 2 else "c02", "text": "t", "start": k * 25.0, "end": k * 25.0 + 24.5, "w0": k * 50, "w1": k * 50 + 50} for k in range(4)]
    return {"duration": 100.0, "words": words, "beats": beats, "chapters": [{"id": "c01", "name": "A", "start": 0.0, "end": 50.0}, {"id": "c02", "name": "B", "start": 50.0, "end": 100.0}]}


def shot(i, t0, tech="CAM-01", asset="A", region=None, intent="explore", note="reason", camera=None, overlays=None, locked=False):
    s = {"id": "s%04d" % i, "start": {"t": t0}, "technique": tech, "slots": {"image": {"asset": asset, **({"region": region} if region else {})}}, "params": {},
         "intent": intent, "note": note, "overlays": overlays or [], "locked": locked}
    if camera:
        s["params"]["camera"] = camera
    return s


def storyboard(n=14, step=7.0, techniques=None):
    techniques = techniques or ["CAM-01", "CAM-05", "STATIC-01", "CAM-03", "X-LAY-01", "LAY-01", "CAM-04"]
    shots = [shot(i + 1, i * step, techniques[i % len(techniques)], intent="context" if techniques[i % len(techniques)] == "X-LAY-01" else "explore",
                  asset="B" if techniques[i % len(techniques)] == "X-LAY-01" else "A") for i in range(n)]
    return {"schema": "bti.storyboard/1", "shots": shots, "end": {"t": n * step}, "assets": {"A": {}, "B": {}}}


def draft_outputs(**kw):
    sb = storyboard(**kw)
    picks = {"main_asset": "A", "assets": {"A": {}, "B": {}}, "beats": {"b0002": {"items": [{"asset": "B", "region": None}], "status": "picked"}}}
    tm = timing()
    tm["duration"] = sb["end"]["t"]
    return {"storyboard": sb, "timing": tm, "issues": [], "picks": picks, "before": None}


def zoom_camera(z0, z1):
    return [{"at": {"rel": 0.0}, "cx": 1, "cy": 1, "zoom": z0}, {"at": {"rel": 1.0}, "cx": 1, "cy": 1, "zoom": z1}]


def edit_outputs():
    before = storyboard(n=6, step=10.0)
    for i in (3, 4):
        before["shots"][i]["params"]["camera"] = zoom_camera(0.7, 1.4)
    after = copy.deepcopy(before)
    for i in (3, 4):
        after["shots"][i]["params"]["camera"] = zoom_camera(0.7, 1.0)
    return {"before": before, "after": after, "storyboard": after, "timing": None, "issues": [], "scope": {"shots": ["s0004", "s0005"]},
            "answer": {"code": "applied", "state": "done", "reason": "", "summary": "ok"}}


def picks_doc(n=8, assets=7):
    keys = ["MAIN"] + ["P%d" % i for i in range(assets - 1)]
    beats = {"b%04d" % (i + 1): {"items": [{"asset": keys[(i % (len(keys) - 1)) + 1] if i % 2 else keys[0], "region": None}], "status": "picked"} for i in range(n)}
    return {"main_asset": "MAIN", "assets": {k: {"kind": "image", "credit": {"source": "commons", "licence": "PD"}} for k in keys}, "beats": beats}


def picks_outputs():
    return {"picks": picks_doc(), "issues": [], "beat_ids": ["b%04d" % (i + 1) for i in range(8)]}
