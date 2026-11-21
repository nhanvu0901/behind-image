"""A full draft compile writes `identity.video_title` from the project's title document; without a document the field is left as it was (the beat falls back to the painting's title);
an edit-mode compile and the old look are not touched. The fixtures are those of tests/draft (a synthetic project, the real engine's registry)."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "tests" / "draft") not in sys.path:
    sys.path.insert(0, str(REPO / "tests" / "draft"))

pytest.importorskip("cv2")

from intro_helpers import brand03, compiled, intro_timing, make_project  # noqa: E402,F401  (brand03 is a fixture)

from bti.draft.compile import compile_specs  # noqa: E402
from bti.draft.inputs import load_inputs  # noqa: E402
from bti.title import store as T  # noqa: E402
from intro_helpers import specs  # noqa: E402

TITLE = "The Saint Who Was Also an Advertisement"


def beat(sb):
    return next(s for s in sb["shots"] if s["technique"].startswith("ID-BRAND"))


def test_a_compile_without_a_title_document_is_as_before(tmp_path, brand03):
    proj = make_project(tmp_path, intro_timing())
    sb = compiled(proj).storyboard
    assert sb["identity"] == {"style": "raking"} and beat(sb)["params"]["title"] == "Intro" and beat(sb)["params"]["subtitle"] == "Some Painter, 1434"


def test_the_document_gives_the_video_title_and_the_beat_shows_it(tmp_path, brand03):
    proj = make_project(tmp_path, intro_timing())
    T.set_title(proj, base_rev=T.EMPTY_REV, actor="human", text=TITLE)
    sb = compiled(proj).storyboard
    assert sb["identity"] == {"style": "raking", "video_title": TITLE}
    assert beat(sb)["params"]["title"] == TITLE and beat(sb)["params"]["subtitle"] == "Intro · Some Painter, 1434" and beat(sb)["params"]["text"] == "RAKING LIGHT"
    assert list(sb).index("identity") == list(sb).index("style") + 1                              # the field sits where the engine's documents keep it


def test_the_document_wins_over_a_title_carried_over_from_the_saved_storyboard(tmp_path, brand03):
    proj = make_project(tmp_path, intro_timing())
    first = compiled(proj).storyboard
    first["identity"]["video_title"] = "An Older Title"
    (proj / "storyboard.json").write_text(json.dumps(first), encoding="utf-8")
    assert compiled(proj).storyboard["identity"]["video_title"] == "An Older Title"              # no document: the carried title stays
    T.set_title(proj, base_rev=T.EMPTY_REV, actor="human", text=TITLE)
    again = compiled(proj).storyboard
    assert again["identity"] == {"style": "raking", "video_title": TITLE} and beat(again)["params"]["title"] == TITLE


def test_a_damaged_document_is_no_document(tmp_path, brand03):
    proj = make_project(tmp_path, intro_timing())
    (proj / "title.json").write_text("{ nope", encoding="utf-8")
    assert compiled(proj).storyboard["identity"] == {"style": "raking"}


def test_the_old_look_has_no_identity_and_so_no_title(tmp_path, brand03):
    proj = make_project(tmp_path, intro_timing())
    T.set_title(proj, base_rev=T.EMPTY_REV, actor="human", text=TITLE)
    res = compile_specs(load_inputs(proj), specs(), draw=False, identity=False)
    assert "identity" not in res.storyboard
