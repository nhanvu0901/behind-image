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
