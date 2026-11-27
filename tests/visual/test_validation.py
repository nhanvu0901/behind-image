from bti.visual.validate import validate


def sample():
    return {"schema": "bti.visual/1", "made_from": {"narration": "abc", "timing": "def"},
            "cast": [{"id": "river", "kind": "thing", "name": "river", "also": [], "strip": False, "sub": "", "shown_by": [{"region": "RIVER"}]}],
            "wanted": [], "moments": [{"id": "m1", "line": "b1", "w0": 0, "w1": 2, "about": "river", "show": {"region": "RIVER"}, "move": "hold", "from": "whole", "say": [], "why": "Dòng sông."}]}


def test_reports_multiple_rules_without_mutation():
    doc = sample()
    doc["moments"][0].update(w1=1, show={"region": "SKY"})
    timing = {"words": [{"w": "A", "s": 0, "e": .2}, {"w": "river.", "s": .2, "e": 2}], "beats": [{"id": "b1", "w0": 0, "w1": 2}]}
    before = repr(doc)
    issues = validate(doc, timing)
    assert {issue["rule"] for issue in issues} >= {"V1", "V2", "V3"}
    assert repr(doc) == before
    assert all(issue["message"] for issue in issues)


def timing():
    return {"words": [{"w": w, "s": i * .8, "e": (i + 1) * .8} for i, w in enumerate(["A", "river", "flows", "towards", "Bruges."])],
            "beats": [{"id": "b1", "w0": 0, "w1": 5}]}


def valid():
    doc = sample()
    doc["moments"][0]["w1"] = 5
    return doc


def test_valid_document_and_shape_errors_are_reported_together():
    assert not [i for i in validate(valid(), timing()) if i.get("level") != "review"]
    doc = valid()
    doc["moments"][0]["move"] = "fly"
    doc["cast"][0]["strip"] = "yes"
    issues = validate(doc, timing())
    assert len([i for i in issues if i["rule"] == "shape"]) >= 2


def test_missing_want_and_duplicate_introduction():
    doc = valid()
    doc["moments"][0]["show"] = {"want": "missing", "else": {"whole": True}}
    doc["moments"][0]["say"] = [{"intro": "river", "word": 1}, {"intro": "river", "word": 1}]
    rules = {i["rule"] for i in validate(doc, timing())}
    assert {"V4", "V5"} <= rules


def test_point_person_and_bad_text():
    doc = valid()
    doc["cast"][0]["kind"] = "person"
    doc["moments"][0]["say"] = [{"point": [{"region": "RIVER", "word": 1}]}, {"read": {"region": "RIVER", "text": "invented inscription"}}]
    rules = {i["rule"] for i in validate(doc, timing())}
    assert {"V8", "V12"} <= rules


def test_bad_pair_and_map():
    doc = valid()
    doc["moments"][0]["about"] = None
    doc["moments"][0]["show"] = {"map": {"places": ["Bruges"]}}
    assert "V11" in {i["rule"] for i in validate(doc, timing())}


def test_proper_name_and_repeated_region():
    doc = valid()
    doc["cast"][0].update(kind="person", name="Bruges", strip=False)
    doc["moments"] = [{**doc["moments"][0], "id": f"m{i}", "w0": i, "w1": i + 1} for i in range(5)]
    rules = {i["rule"] for i in validate(doc, timing())}
    assert {"V6", "V10"} <= rules


def test_whole_in_middle_is_reviewed():
    doc = valid()
    first = doc["moments"][0]
    doc["moments"] = [{**first, "id": "m1", "w0": 0, "w1": 1},
                      {**first, "id": "m2", "w0": 1, "w1": 4, "about": None, "show": {"whole": True}},
                      {**first, "id": "m3", "w0": 4, "w1": 5}]
    assert any(i["rule"] == "V9" and i["moment"] == "m2" for i in validate(doc, timing()))


def test_shape_errors_do_not_hide_independent_timing_violation():
    doc = valid()
    doc["moments"][0]["move"] = "fly"
    doc["moments"][0]["w1"] = 1
    rules = {issue["rule"] for issue in validate(doc, timing())}
    assert {"shape", "V1", "V2"} <= rules


def test_filename_is_forbidden_even_when_spoken():
    doc = valid()
    doc["moments"][0]["say"] = [{"read": {"region": "RIVER", "text": "painting.jpg"}}]
    spoken = timing()
    spoken["words"][1]["w"] = "painting.jpg"
    picks = {"assets": {"A": {"file": "media/painting.jpg"}}, "main_asset": "A"}
    assert "V12" in {i["rule"] for i in validate(doc, spoken, picks)}


def test_unverifiable_pair_semantics_are_returned_for_review():
    doc = valid()
    doc["moments"][0]["about"] = None
    doc["moments"][0]["show"] = {"pair": [{"picture": "A"}, {"picture": "B"}]}
    checks = validate(doc, timing())
    assert any(i["rule"] == "V11" and i.get("level") == "review" for i in checks)


def test_thing_strip_needs_familiarity_review():
    assert any(i["rule"] == "V6" and i.get("level") == "review" for i in validate(valid(), timing()))


def test_missing_wanted_picture_checks_the_actual_fallback():
    doc = valid()
    doc["wanted"] = [{"id": "w1", "subject": "river", "kind": "object", "search": "river", "alt": [],
                      "period": None, "status": "none", "picture": None, "tried": ["river"]}]
    doc["moments"][0]["show"] = {"want": "w1", "else": {"region": "SKY"}}
    assert "V3" in {issue["rule"] for issue in validate(doc, timing())}


def test_point_in_borrowed_picture_region_is_not_assumed_missing():
    doc = valid()
    doc["moments"][0].update(about=None, show={"picture": "B"}, say=[{"point": [{"region": "DETAIL", "word": 1}]}])
    picks = {"main_asset": "A", "assets": {"A": {"regions": {"RIVER": {}}}, "B": {"regions": {"DETAIL": {}}}}}
    assert not [i for i in validate(doc, timing(), picks) if i["rule"] == "V8" and i.get("level") != "review"]


def test_point_inside_person_region_is_person_but_partial_overlap_is_not():
    doc = valid()
    doc['cast'][0].update(kind='person', shown_by=[{'region': 'BODY'}])
    doc['moments'][0]['say'] = [{'point': [{'region': 'DETAIL', 'word': 1}]}]
    regions = {'BODY': {'x': 50, 'y': 50, 'rx': 25, 'ry': 25},
               'DETAIL': {'x': 50, 'y': 50, 'rx': 5, 'ry': 5}}
    picks = {'main_asset': 'A', 'assets': {'A': {'regions': regions}}}
    errors = [i for i in validate(doc, timing(), picks) if i['rule'] == 'V8' and i.get('level') != 'review']
    assert any('person region' in i['message'] for i in errors)
    regions['DETAIL']['x'] = 75
    errors = [i for i in validate(doc, timing(), picks) if i['rule'] == 'V8' and i.get('level') != 'review']
    assert not any('person region' in i['message'] for i in errors)
