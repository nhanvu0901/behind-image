"""The canned answers of the mock model to the briefings of the two prompt boxes (worker c2box): `answer(prompt)` is None for any other prompt.
Used by the browser launchers (tests/e2e/stages/launch.py, tests/e2e/agent/launch_agent.py); no network, no real model.

Step 5 ("change a few shots of a video's storyboard"): the request decides:
    "tranh mới"      -> cannot (Vietnamese reason)           "[mock:escalate]" -> escalate (Vietnamese reason)
    "[mock:refuse]"  -> an operation on a shot that does not exist, twice: the turn fails with a plain sentence
    "[mock:broken]"  -> not JSON, twice                      anything else -> the first shot of the scope that has a camera gets a slower last key
Step 4 ("change the pictures of a few narration lines"):
    "bản đồ"         -> escalate (a picture the project does not have)       "[mock:refuse]" -> a line that does not exist, twice
    anything else    -> the first line of the scope shows the first picture whole, then its first region (when it has one)"""
from __future__ import annotations

import json
import re

STORYBOARD_HEADING = "change a few shots of a video's storyboard"
PICTURES_HEADING = "change the pictures of a few narration lines"


def _request(user: str) -> str:
    m = re.search(r"## The request\n(.*?)\n\n## The last turns", user, re.S)
    return m.group(1) if m else ""


def _section(user: str, start: str, end: str) -> list[dict]:
    """The JSON objects on the lines between two headings of the briefing."""
    i = user.find(start)
    j = user.find(end, i + 1)
    out = []
    for ln in user[i:j if j > 0 else len(user)].splitlines():
        if ln.startswith("{"):
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def _json(status: str, summary: str = "", reason: str = "", ops: list | None = None) -> str:
    return json.dumps({"status": status, "summary": summary, "reason": reason, "ops": ops or []}, ensure_ascii=False)


def storyboard_answer(user: str) -> str:
    ask = _request(user)
    if "[mock:broken]" in ask:
        return "Xin lỗi, tôi không làm được việc này {{{"
    if "[mock:escalate]" in ask:
        return _json("escalate", reason="Chi tiết này chưa có vùng nào trên tranh, cần bước xem tranh kỹ hơn.")
    if "tranh mới" in ask:
        return _json("cannot", reason="Yêu cầu này cần một bức tranh mới mà dự án chưa có. Hãy thêm tranh ở bước Chọn hình.")
    if "[mock:refuse]" in ask:
        return _json("applied", "Đã làm chậm cảnh này.", ops=[{"op": "set_params", "shot": "s9999", "params": {"camera": []}}])
    shots = [sh for sh in _section(user, "### The shots in scope", "### The shot before") if not sh.get("locked")]
    for sh in shots:
        cam = (sh.get("params") or {}).get("camera")
        if not (isinstance(cam, list) and cam):
            continue
        keys = [dict(k, ease="inout_cubic") for k in cam]
        keys[-1]["zoom"] = round(float(keys[-1]["zoom"]) * 0.9, 4)
        return _json("applied", "Máy quay ở cảnh này đi chậm hơn.", ops=[{"op": "set_params", "shot": sh["id"], "params": {"camera": keys}}])
    for sh in shots:                                       # a shot with one picture and no camera: another treatment
        if sorted((sh.get("slots") or {})) == ["image"] and sh.get("technique") != "CAM-03":
            return _json("applied", "Cảnh này giờ có chuyển động máy quay chậm.", ops=[{"op": "set_technique", "shot": sh["id"], "technique": "CAM-03"}])
    return _json("cannot", reason="Cảnh đã chọn không có chuyển động máy quay nào để làm chậm.")


def pictures_answer(user: str) -> str:
    ask = _request(user)
    if "[mock:broken]" in ask:
        return "Xin lỗi, tôi không làm được việc này {{{"
    if "bản đồ" in ask:
        return _json("escalate", reason="Dự án chưa có hình bản đồ, bạn cần tìm thêm hình ở cột Tìm hình.")
    if "[mock:refuse]" in ask:
        return _json("applied", "Dòng này giờ cho xem cả bức tranh.", ops=[{"op": "set_picks", "beat": "b9999", "items": [{"asset": "A"}]}])
    lines = _section(user, "### The lines in scope", "### The line before")
    i = user.find("### The pictures of the project")
    assets = {}
    for ln in user[i:].splitlines():
        if ln.startswith("{"):
            try:
                assets = json.loads(ln)
            except ValueError:
                pass
            break
    if not lines or not assets:
        return _json("cannot", reason="Chưa có dòng hoặc hình nào để sắp lại.")
    key = next(iter(assets))
    items = [{"asset": key, "role": "main"}]
    region = next(iter(assets[key].get("regions") or {}), None)
    if region:
        items.append({"asset": key, "region": region, "role": "detail"})
    return _json("applied", "Dòng này giờ cho xem cả bức tranh%s." % (", rồi một chi tiết của nó" if region else ""), ops=[{"op": "set_picks", "beat": lines[0]["id"], "items": items}])


def answer(user: str) -> str | None:
    if STORYBOARD_HEADING in user:
        return storyboard_answer(user)
    if PICTURES_HEADING in user:
        return pictures_answer(user)
    return None
