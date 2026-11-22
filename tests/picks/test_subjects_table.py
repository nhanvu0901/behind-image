from bti.picks import doc


def test_subject_table_survives_normalization():
    source = {"subjects": [{"id": "village", "kind": "place", "name": "village", "strip": False,
                             "where": {"region": "VILLAGE"}}],
              "beats": {"b0001": {"about": [{"id": "village", "words": "the village"}]}}}
    result = doc.normalize(source)
    assert result["subjects"] == source["subjects"]
    assert result["beats"]["b0001"]["about"] == source["beats"]["b0001"]["about"]


def test_subject_validation_requires_unique_ids_and_known_references():
    subject = {"id": "river", "kind": "thing", "name": "river", "strip": False, "where": {"region": "RIVER"}}
    assert doc.doc_problem({"subjects": [subject, subject]}) is not None
    assert doc.doc_problem({"subjects": [subject], "beats": {"b0001": {"about": [{"id": "missing", "words": "river"}]}}}) is not None
    assert doc.doc_problem({"subjects": [{**subject, "where": None}]}) is not None
