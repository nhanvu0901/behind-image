"""Viewer-review findings are exposed by the storyboard and thread GET routes."""
from bti.draft.review import save_report
from editor_helpers import PID


def test_reviewed_revision_is_visible_to_gate_and_thread(client):
    path = f"/api/projects/{PID}"
    rev = client.get(path).json()["rev"]
    save_report(client.root / PID, {"revision": rev, "rounds": 2, "history": [], "warnings": [
        {"level": "warn", "code": "review_picture_mismatch", "shot": "s0001", "message": "Person is not visible."}]})
    issues = client.get(path).json()["issues"]
    issue = next(i for i in issues if i.get("code") == "review_picture_mismatch")
    assert issue["args"]["shot"] == "s0001"
    thread = client.get(path + "/draft/thread").json()
    assert thread["review"]["revision"] == rev
    assert thread["review"]["warnings"][0]["code"] == issue["code"]
