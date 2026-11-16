import hashlib
import json

import pytest

from bti.engine import storyboard as SB
from bti.engine.api import ValidationError
from conftest import base_storyboard


def test_revision_is_sha256_of_canonical_json(tiny_project):
    sb = tiny_project.storyboard()
    canon = json.dumps(sb, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert tiny_project.revision() == hashlib.sha256(canon.encode()).hexdigest()


def test_revision_ignores_key_order_and_derived_keys(tiny_project):
    sb = tiny_project.storyboard()
    rs = tiny_project.resolve()
    assert SB.revision_of(rs) == SB.revision_of(sb)
    shuffled = json.loads(json.dumps(sb))
    shuffled["shots"][0] = dict(reversed(list(shuffled["shots"][0].items())))
    assert SB.revision_of(shuffled) == SB.revision_of(sb)


def test_save_returns_new_revision_strips_derived_and_backs_up(tiny, tiny_project):
    before = tiny_project.revision()
    sb = tiny_project.resolve()                      # carries _t keys
    sb["shots"][1]["params"]["title"] = "CHAPTER TWO"
    rev = tiny_project.save(sb)
    assert rev != before and rev == tiny_project.revision()
    on_disk = json.loads((tiny / "storyboard.json").read_text())
    assert "_t0" not in json.dumps(on_disk) and on_disk["shots"][1]["params"]["title"] == "CHAPTER TWO"
    assert SB.revision_of(on_disk) == rev
    hist = sorted((tiny / "history").glob("*.json"))
    assert len(hist) == 1
    assert SB.revision_of(json.loads(hist[0].read_text())) == before        # the backup is the previous document
    assert not list(tiny.glob("*.tmp"))


def test_second_save_adds_second_backup_and_noop_adds_none(tiny, tiny_project):
    sb = tiny_project.storyboard()
    sb["title"] = "One"
    r1 = tiny_project.save(sb)
    assert tiny_project.save(sb) == r1               # unchanged: no new history entry
    assert len(list((tiny / "history").glob("*.json"))) == 1
    sb["title"] = "Two"
    r2 = tiny_project.save(sb)
    assert r2 != r1 and len(list((tiny / "history").glob("*.json"))) == 2


def test_save_refuses_documents_with_errors(tiny, tiny_project):
    before = (tiny / "storyboard.json").read_text()
    sb = tiny_project.storyboard()
    sb["shots"][0]["technique"] = "NOPE-01"
    with pytest.raises(ValidationError) as ei:
        tiny_project.save(sb)
    assert any(i["level"] == "error" for i in ei.value.issues)
    assert (tiny / "storyboard.json").read_text() == before
    assert not (tiny / "history").exists() or not list((tiny / "history").glob("*.json"))


def test_saved_change_is_rendered_and_draft_is_not_saved(tiny, tiny_project):
    import numpy as np
    f0 = tiny_project.frame_at(6.5, 320)
    sb = tiny_project.storyboard()
    sb["shots"][1]["params"]["title"] = "A VERY DIFFERENT CARD"
    tiny_project.use_draft(sb)
    f1 = tiny_project.frame_at(6.5, 320)
    assert not np.array_equal(f0, f1)
    assert json.loads((tiny / "storyboard.json").read_text())["shots"][1]["params"]["title"] == "CHAPTER ONE"
    tiny_project.use_draft(None)
    assert np.array_equal(tiny_project.frame_at(6.5, 320), f0)
