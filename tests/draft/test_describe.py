"""What the owner reads: plain Vietnamese by code (`facts`), the check of the model's sentences, the summary built by code, and the
normalisation that keeps registry defaults out of the stored shots."""
import copy

import pytest

from bti.draft import describe as DS
from bti.draft.normalize import keep_saved
from bti.engine import registry as R
from bti.engine.timing import Timing

BUNDLE = R.load_bundle("gae")
TM = Timing({"duration": 100.0, "words": [{"w": "w%d" % i, "s": 0.5 * i, "e": 0.5 * i + 0.4} for i in range(200)]})
ASSETS = {"A": {"regions": {"MIRROR": {"label": "chiếc gương"}, "DOG": {"label": "Con chó"}}}}


def cam(z0, z1, ease="linear", cx1=800, cy1=500):
    return [{"at": {"rel": 0}, "cx": 500, "cy": 500, "zoom": z0, "ease": ease}, {"at": {"rel": 1}, "cx": cx1, "cy": cy1, "zoom": z1, "ease": ease}]


def shot(**kw):
    s = {"id": "s0004", "start": {"w": 10, "off": 0.0}, "technique": "CAM-01", "slots": {"image": {"asset": "A"}}, "params": {"camera": cam(0.5, 1.0)},
         "overlays": [], "note": ""}
    s.update(kw)
    return s


def facts(before, after):
    return DS.shot_facts(before, after, assets=ASSETS, bundle=BUNDLE, tm=TM)


# ---------------------------------------------------------------------------------------------------- the owner's words, by code
def test_a_slower_camera_is_said_in_owner_words():
    f = facts(shot(), shot(params={"camera": cam(0.5, 0.65)}))
    assert f[0] == "Máy quay đi chậm hơn", f
    assert facts(shot(), shot(params={"camera": cam(0.5, 1.6, cx1=1200)}))[0] == "Máy quay đi nhanh hơn"


def test_a_smoother_camera():
    assert facts(shot(), shot(params={"camera": cam(0.5, 1.0, ease="inout_cubic")})) == ["Máy quay chuyển động mượt hơn"]


def test_an_added_ring_names_the_detail_by_its_label():
    after = shot(overlays=[{"technique": "AN-01", "start": {"w": 12, "off": 0.0}, "params": {"at": "MIRROR"}, "slots": {}}])
    assert facts(shot(), after) == ["Thêm: vẽ vòng khoanh quanh chiếc gương"]


def test_a_removed_text_and_a_moved_start_and_another_treatment():
    before = shot(overlays=[{"technique": "TXT-02", "start": {"w": 12, "off": 0.0}, "params": {}, "slots": {}}])
    assert facts(before, shot()) == ["Bỏ dòng chữ"]
    assert facts(shot(), shot(start={"w": 10, "off": -1.24})) == ["Cảnh bắt đầu sớm hơn 1,2 giây"]
    assert facts(shot(), shot(start={"w": 14, "off": 0.0})) == ["Cảnh bắt đầu muộn hơn 2 giây"]
    assert facts(shot(), shot(technique="CAM-03")) == ["Đổi cách dựng: Đẩy vào thành kéo ra"]


def test_the_region_a_shot_looks_at():
    after = shot(slots={"image": {"asset": "A", "region": "DOG"}})
    assert facts(shot(), after) == ["Nhìn vào Con chó"]


def test_added_and_removed_shots():
    assert DS.added_facts(shot(), bundle=BUNDLE) == ["Thêm cảnh: Đẩy vào"]
    assert DS.removed_facts(shot(), bundle=BUNDLE) == ["Xóa cảnh"]


def test_no_fact_ever_carries_an_id_or_a_setting_name():
    cases = [facts(shot(), shot(params={"camera": cam(0.5, 0.65)})), facts(shot(), shot(technique="CAM-03")),
             facts(shot(), shot(overlays=[{"technique": "AN-01", "start": {"w": 12}, "params": {"at": "MIRROR", "size_px": 3}}])),
             facts(shot(), shot(params={"camera": cam(0.5, 1.0), "foo_bar": 3})), facts(shot(), shot(note="x"))]
    for fs in cases:
        for f in fs:
            assert DS.sentence_ok(f), f


# ---------------------------------------------------------------------------------------------------- the check of the model's sentence
@pytest.mark.parametrize("text", ["Máy quay ở cảnh này đi chậm hơn và dừng lại ở chiếc gương.", "Cảnh bắt đầu sớm hơn 1,2 giây.",
                                  "Thêm một vòng khoanh quanh con chó và bỏ dòng chữ ở cảnh sau.", "Đổi hai cảnh theo yêu cầu."])
def test_plain_vietnamese_passes(text):
    assert DS.sentence_ok(text)


@pytest.mark.parametrize("text", [
    "Làm chậm chuyển động zoom vào gương trong s0004 và thêm vòng sáng AN-01 quanh gương.",      # a shot id and a technique id
    "Camera easing changed from linear to inout_cubic and the zoom end value reduced from 0.4075 to 0.3850.",     # English, parameters
    "Máy quay đổi ease sang inout_cubic.", "Giảm zoom cuối từ 0.4075 xuống 0.3850.", "Đổi size_px thành 12.", "Slower camera move.", "", None, 42,
    "Máy quay đi tới 1920 điểm ảnh."])
def test_editing_words_ids_and_parameter_numbers_are_refused(text):
    assert not DS.sentence_ok(text)


def test_the_model_sentence_is_used_only_when_it_passes():
    f = ["Máy quay đi chậm hơn"]
    assert DS.what_for("Máy quay chậm lại và dừng ở chiếc gương.", f) == ("Máy quay chậm lại và dừng ở chiếc gương.", "model")
    assert DS.what_for("Camera easing changed", f) == ("Máy quay đi chậm hơn.", "code")
    assert DS.what_for(None, f + ["Thêm: vẽ vòng khoanh"]) == ("Máy quay đi chậm hơn; Thêm: vẽ vòng khoanh.", "code")


def test_the_summary_by_code():
    ch = [{"op": "changed", "facts": ["Máy quay đi chậm hơn"]}, {"op": "changed", "facts": ["Máy quay đi chậm hơn", "Bỏ dòng chữ"]},
          {"op": "added", "facts": ["Thêm cảnh: Đẩy vào"]}, {"op": "removed", "facts": ["Xóa cảnh"]}]
    s = DS.code_summary(ch)
    assert s == "Đã sửa 2 cảnh, thêm 1 cảnh, xóa 1 cảnh: Máy quay đi chậm hơn; Bỏ dòng chữ; Thêm cảnh: Đẩy vào."
    assert DS.summary_for("Fixed 4 shots (s0004)", ch) == (s, "code")
    assert DS.summary_for("Đã sửa bốn cảnh.", ch) == ("Đã sửa bốn cảnh.", "model")


# ---------------------------------------------------------------------------------------------------- registry defaults stay out
def test_a_registry_default_the_saved_shot_did_not_carry_is_not_written_and_an_equal_shot_is_not_a_change():
    saved = {"shots": [shot(id="s1", params={"camera": cam(0.5, 1.0)}, source="import", locked=False)]}
    returned = copy.deepcopy(saved["shots"][0])
    returned["params"]["shadow"] = True                       # the compiler's default (the registry's default of CAM-01)
    returned["source"] = "agent"
    out = keep_saved(saved, {"shots": [returned]}, BUNDLE)
    assert out["shots"][0] == saved["shots"][0]               # equal after the normalisation: the saved shot, verbatim

    changed = copy.deepcopy(returned)
    changed["params"]["camera"] = cam(0.5, 0.7)
    out = keep_saved(saved, {"shots": [changed]}, BUNDLE)
    assert "shadow" not in out["shots"][0]["params"]          # a real change does not drag the default in
    assert out["shots"][0]["params"]["camera"] == cam(0.5, 0.7)

    carried = {"shots": [shot(id="s1", params={"camera": cam(0.5, 1.0), "shadow": True})]}
    keep = copy.deepcopy(carried["shots"][0])
    keep["params"]["camera"] = cam(0.5, 0.7)
    assert keep_saved(carried, {"shots": [keep]}, BUNDLE)["shots"][0]["params"]["shadow"] is True     # carried before: stays
    assert "shadow" not in (shot(id="s1")["params"])
