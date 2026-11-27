from bti.visual.from_project import convert


def test_convert_preserves_shots_cast_and_picture_pool():
    timing = {"duration": 4, "words": [{"w": w, "s": i, "e": i + .8} for i, w in enumerate(["The", "river", "is", "blue."])],
              "beats": [{"id": "b1", "w0": 0, "w1": 4}]}
    picks = {"main_asset": "A", "assets": {"A": {}, "B": {}},
             "subjects": [{"id": "river", "kind": "thing", "name": "river", "strip": False, "where": [{"region": "RIVER"}, {"asset": "B"}]}],
             "beats": {"b1": {"about": [{"id": "river", "words": "river"}]}}}
    storyboard = {"shots": [{"id": "s0000", "start": {"t": 0}, "technique": "CAM-01"},
                            {"id": "s1", "start": {"w": 0}, "technique": "CAM-01", "slots": {"image": {"asset": "A", "region": "RIVER"}}, "overlays": []},
                            {"id": "s2", "start": {"w": 2}, "technique": "CAM-01", "slots": {"image": {"asset": "B"}}, "overlays": []}]}
    doc, augmented = convert(storyboard, timing, picks, "narhash", "timhash")
    assert [m["w0"] for m in doc["moments"]] == [0, 2]
    assert [m["w1"] for m in doc["moments"]] == [2, 4]
    assert doc["moments"][0]["show"] == {"region": "RIVER"}
    assert doc["moments"][0]["about"] == "river"
    assert doc["moments"][1]["show"] == {"picture": "B"}
    assert augmented["assets"]["B"]["shows"] == ["river"]
    assert "shows" not in picks["assets"]["B"]


def test_issue_counts_distinguish_findings_and_affected_moments():
    from bti.visual.from_project import issue_counts
    document = {"moments": [{"id": "m1", "about": "river", "say": []},
                            {"id": "m2", "about": "river", "say": []},
                            {"id": "m3", "about": None, "say": []}]}
    issues = [{"rule": "V7", "moment": None, "subject": "river", "message": "x"},
              {"rule": "V7", "moment": "m1", "message": "y"}]
    assert issue_counts(document, issues, "V7") == (2, 2)


def test_convert_map_from_named_legacy_places():
    timing = {"duration": 3, "words": [{"w": "Lucca", "s": 0, "e": 1}, {"w": "Bruges", "s": 1, "e": 3}],
              "beats": [{"id": "b1", "w0": 0, "w1": 2}]}
    picks = {"main_asset": "A", "assets": {"A": {}}, "beats": {}}
    storyboard = {"shots": [{"id": "s1", "start": {"w": 0}, "technique": "MAP-01",
                              "params": {"places": [{"name": "Lucca, Italy"}, {"name": "Bruges, Belgium"}]}}]}
    doc, _ = convert(storyboard, timing, picks, "n", "t")
    assert doc["moments"][0]["show"] == {"map": {"places": ["Lucca, Italy", "Bruges, Belgium"]}, "else": {"whole": True}}


def test_uncertain_main_picture_frame_is_marked_in_the_moment():
    timing = {"duration": 3, "words": [{"w": "The", "s": 0, "e": 1}, {"w": "face", "s": 1, "e": 2}],
              "beats": [{"id": "b1", "w0": 0, "w1": 2}]}
    picks = {"main_asset": "A", "assets": {"A": {}}, "beats": {}}
    storyboard = {"shots": [{"id": "s1", "start": {"w": 0}, "technique": "CAM-01", "slots": {"image": {"asset": "A"}}}]}
    notes = []
    doc, _ = convert(storyboard, timing, picks, "n", "t", notes)
    assert "kiểm tra" in doc["moments"][0]["why"]
    assert notes


def test_unconvertible_number_overlay_is_reported():
    timing = {"duration": 3, "words": [{"w": "Two", "s": 0, "e": 1}, {"w": "rings", "s": 1, "e": 2}],
              "beats": [{"id": "b1", "w0": 0, "w1": 2}]}
    picks = {"main_asset": "A", "assets": {"A": {}}, "beats": {}}
    storyboard = {"shots": [{"id": "s1", "start": {"w": 0}, "technique": "CAM-01",
                              "slots": {"image": {"asset": "A", "region": "R"}},
                              "overlays": [{"technique": "NUM-01", "params": {}}]}]}
    notes = []
    doc, _ = convert(storyboard, timing, picks, "n", "t", notes)
    assert any("number" in note for note in notes)
    assert "kiểm tra" in doc["moments"][0]["why"]
