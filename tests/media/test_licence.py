import pytest

from bti.media.licence import check_licence, check_text


@pytest.mark.parametrize("text,name", [
    ("Public domain", "PD"), ("PD-old-100", "PD"), ("pd", "PD"), ("PD-US-expired", "PD"),
    ("<a href='x'>Public Domain Mark 1.0</a>", "PD"),
    ("CC0", "CC0"), ("CC0 1.0 Universal", "CC0"), ("cc-zero", "CC0"),
    ("CC BY 4.0", "CC BY 4.0"), ("cc-by-2.0", "CC BY 2.0"), ("CC BY", "CC BY"),
    ("Creative Commons Attribution license (reuse allowed)", "CC BY"),
    ("CC BY-SA 3.0", "CC BY-SA 3.0"), ("cc-by-sa-4.0", "CC BY-SA 4.0"),
    ("Creative Commons Attribution-ShareAlike 2.5", "CC BY-SA 2.5"),
])
def test_accepted(text, name):
    ok, got, reason = check_text(text)
    assert ok and got == name and reason == ""


@pytest.mark.parametrize("text", [
    "CC BY-NC-SA 4.0", "CC BY-NC 2.0", "cc-by-nc-nd-3.0", "CC BY-ND 4.0", "CC BY-NC-SA",
    "Creative Commons Attribution-NonCommercial", "Fair use", "All rights reserved",
    "Standard YouTube License", "unknown", "GFDL", "Attribution", "", None, "   ",
    "Not public domain",
])
def test_rejected(text):
    ok, _, reason = check_text(text)
    assert not ok and reason


def test_reject_reason_names_the_licence():
    _, name, reason = check_text("CC BY-NC-SA 4.0")
    assert "CC BY-NC-SA 4.0" in reason and name == "CC BY-NC-SA 4.0"


def test_missing_reason():
    assert check_text(None) == (False, "", "licence is missing")


def test_british_museum_style_rejected():
    ok, _, reason = check_licence({"licence": "CC BY-NC-SA 4.0",
                                   "credit_line": "Donated to the British Museum"})
    assert not ok and "NC" in reason


def test_extmetadata_any_spelling_and_nc_wins():
    assert check_licence({"extmetadata": {"License": {"value": "cc-by-sa-4.0"}}})[0]
    ok, name, _ = check_licence({"LicenseShortName": "CC BY 4.0", "UsageTerms": "CC BY-NC 4.0"})
    assert not ok and "NC" in name          # conservative: any rejecting spelling rejects


def test_met_records():
    assert check_licence({"isPublicDomain": True})[:2] == (True, "CC0")
    ok, _, reason = check_licence({"isPublicDomain": False})
    assert not ok and "public domain" in reason


def test_ytdlp_metadata():
    assert check_licence({"license": "Creative Commons Attribution license (reuse allowed)"})[0]
    assert not check_licence({"license": "Standard YouTube License"})[0]
    assert not check_licence({"license": None})[0]
    assert not check_licence({})[0]


from bti.media.licence import flag_for_meta, flag_for_text, with_size_flag  # noqa: E402


@pytest.mark.parametrize("text,flag", [
    ("CC0", None), ("CC BY-SA 4.0", None), ("Public domain", None),
    ("CC BY-NC 2.0", "rejected"), ("CC BY-ND 4.0", "rejected"), ("Fair use", "rejected"), ("All rights reserved", "rejected"),
    ("", "unknown"), (None, "unknown"), ("unknown", "unknown"), ("GFDL", "unknown"),
])
def test_flag_for_text(text, flag):
    assert flag_for_text(text) == flag


def test_flag_for_meta_and_size():
    assert flag_for_meta({"isPublicDomain": False}) == "rejected" and flag_for_meta({"isPublicDomain": True}) is None
    assert flag_for_meta({"licence": "CC BY 4.0"}) is None and flag_for_meta({}) == "unknown"
    assert with_size_flag(None, 800, 600, 1200) == "small" and with_size_flag(None, 0, 0, 1200) is None
    assert with_size_flag("unknown", 800, 600, 1200) == "unknown" and with_size_flag(None, 1300, 1250, 1200) is None


# ---------------------------------------------------------------- the free picture services (advisory gate: they are recorded, not refused)
@pytest.mark.parametrize("text,name", [
    ("Pexels License", "Pexels License"), ("pexels licence", "Pexels License"), ("PEXELS LICENSE", "Pexels License"),
    ("Pixabay Content License", "Pixabay Content License"), ("Pixabay License", "Pixabay Content License"),
    ("Content License", "Pixabay Content License"),
    ("ODbL", "ODbL"), ("ODbL 1.0", "ODbL 1.0"), ("Open Database License", "ODbL"),
    ("Open Data Commons Open Database License (ODbL)", "ODbL"), ("<a href='x'>ODbL</a>", "ODbL"),
])
def test_free_service_licences_are_recognised(text, name):
    ok, got, reason = check_text(text)
    assert ok and got == name and reason == ""


def test_free_service_licences_have_links():
    from bti.media.licence import licence_url
    assert licence_url("Pexels License") == "https://www.pexels.com/license/"
    assert licence_url("Pixabay Content License") == "https://pixabay.com/service/license-summary/"
    assert licence_url("ODbL") == "https://www.openstreetmap.org/copyright"
    assert licence_url("ODbL 1.0") == "https://www.openstreetmap.org/copyright"
    assert licence_url("CC BY 4.0") == "" and licence_url(None) == ""        # only the names this table knows


def test_a_look_alike_is_still_not_allowed():
    for text in ("Pexels", "Pixabay", "Stock license", "Content License NC", "Pexels License non-commercial", "Open Database", "Database License"):
        assert not check_text(text)[0], text


def test_the_sources_candidates_carry_no_flag():
    from bti.media import api
    from bti.media.sources.osm import OSM_LICENCE
    from bti.media.sources.pexels import parse_photo, parse_video
    from bti.media.sources.pixabay import PIXABAY_LICENCE
    cands = [parse_photo({"id": 1, "width": 4000, "height": 3000, "photographer": "A", "src": {"original": "https://x/a.jpg", "medium": "https://x/m.jpg"}}),
             parse_video({"id": 2, "duration": 9, "user": {"name": "B"}, "video_files": [{"link": "https://x/v.mp4", "file_type": "video/mp4", "width": 1920, "height": 1080}]}),
             {"source": "pixabay", "source_id": "3", "kind": "image", "width": 4000, "height": 3000, "licence": PIXABAY_LICENCE},
             {"source": "osm", "source_id": "4:12", "kind": "image", "width": 2000, "height": 1500, "licence": OSM_LICENCE}]
    for m in cands:
        c = api._candidate(m)
        assert c["flag"] is None and c["licence_ok"] is True and c["licence_reason"] == "", m["source"]
    assert api._candidate(cands[0])["licence"] == "Pexels License"
    assert api._candidate(cands[3])["licence"] == "ODbL"
