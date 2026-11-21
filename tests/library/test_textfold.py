"""U1-001: one folding for the query and the indexed text; "đ" is "d", not nothing."""
import pytest

from bti import textfold
from bti.engine.timing import norm as engine_norm
from bti.library import catalogue
from bti.script import parse as script_parse


@pytest.mark.parametrize("a,b", [("Đ", "d"), ("đà nẵng", "da nang"), ("Dürer", "durer"), ("Ølaf Łukasz", "olaf lukasz"),
                                 ("Straße", "strasse"), ("Hà Nội", "ha noi"), ("D’Arcy", "d arcy")])
def test_fold_maps_special_letters_and_accents(a, b):
    assert catalogue.norm(a) == b == textfold.norm(b)


def test_other_scripts_are_kept_not_erased():
    assert catalogue.norm("Привет, Мир") == "привет мир"
    assert catalogue.norm("Đ") != ""


def test_every_folder_agrees():
    for w in ("Đó", "Dürer", "Ølaf", "Hà-Nội!"):
        assert engine_norm(w) == textfold.squash(w) == catalogue.norm(w).replace(" ", "") == script_parse._norm(w).replace(" ", "")


def test_query_and_text_match_with_or_without_accents():
    hay = catalogue.norm("Đức Phật Dürer 1500")
    for q in ("duc phat", "đức phật", "DURER", "dürer", "đ"):
        assert catalogue.norm(q) in hay


def test_validate_overlap_tokeniser_does_not_break_words_at_d_bar():
    import re
    assert re.findall(r"[a-z0-9']+", textfold.fold("Đó là ở đây")) == ["do", "la", "o", "day"]
