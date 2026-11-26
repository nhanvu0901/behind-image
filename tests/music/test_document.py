import pytest

from bti.engine.timing import Timing
from bti.music.document import MusicError, validate


def cue(**changes):
    result = {"recording": "one", "start": {"w": 0, "text": "Hello"}, "end": {"t": 5},
              "offset": 0, "role": "bed", "level_db": -24, "fade_in": 1, "fade_out": 1, "why": "Quiet opening."}
    result.update(changes)
    return result


def test_valid_cue_resolves_word_anchor():
    result = validate({"cues": [cue()]}, {"one": {"duration": 20}}, Timing({"words": [{"w": "Hello", "s": 1}]}), 10)
    assert result[0]["start"] == 1
    assert result[0]["end"] == 5


@pytest.mark.parametrize("change", [
    {"recording": "unknown"}, {"end": {"t": 12}}, {"offset": 18},
    {"level_db": 1}, {"fade_in": -1}, {"role": "bad"},
    {"start": {"w": 0, "text": "Changed"}},
])
def test_refuses_invalid_cues(change):
    with pytest.raises(MusicError):
        validate({"cues": [cue(**change)]}, {"one": {"duration": 20}}, Timing({"words": [{"w": "Hello", "s": 1}]}), 10)


def test_refuses_overlap_outside_fades():
    with pytest.raises(MusicError):
        validate({"cues": [cue(start={"t": 0}, end={"t": 5}), cue(start={"t": 3}, end={"t": 8})]},
                 {"one": {"duration": 20}}, Timing({}), 10)


def test_store_round_trip_and_stale_revision(tmp_path):
    from bti.music import store
    tm = Timing({"words": [{"w": "Hello", "s": 1}]})
    library = {"one": {"duration": 20}}
    assert store.read(tmp_path) is None
    saved = store.set_document(tmp_path, {"cues": [cue()]}, library, tm, 10, base_rev=store.revision(None))
    assert store.read(tmp_path) == saved
    with pytest.raises(MusicError) as exc:
        store.set_document(tmp_path, {"cues": []}, library, tm, 10, base_rev=store.revision(None))
    assert exc.value.code == "stale_revision"
    assert store.read(tmp_path) == saved
