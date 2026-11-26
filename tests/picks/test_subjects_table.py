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


def test_missing_subject_picture_is_not_mistaken_for_fallback():
    from bti.picks.auto.write import resolve_subjects
    plan = {"subjects": [{"id": "sitter", "kind": "person", "name": "sitter", "strip": True,
                           "where": {"want": "b0001.1"}}],
            "lines": [{"beat": "b0001", "fallback": {"type": "detail", "region": "FIGURE"},
                       "about": [{"id": "sitter", "words": "the sitter"}]}]}
    rows = resolve_subjects(plan, {}, {}, {"FIGURE": "FIGURE_2"}, set())
    assert rows[0]["where"] is None


def test_old_cast_is_read_as_person_subject_without_changing_saved_document():
    cast = {"names": [{"name": "Ada", "also": ["the painter"], "line": "b0001", "where": {"region": "HEAD"},
                       "sure": False, "words": "perhaps"}]}
    subjects, about = doc.subject_view(cast)
    assert subjects == [{"id": "legacy_1", "kind": "person", "name": "Ada", "also": ["the painter"], "sub": "perhaps", "strip": True, "where": {"region": "HEAD"}}]
    assert about == {"b0001": [{"id": "legacy_1", "words": "Ada"}]}
    assert "subjects" not in cast


def test_partial_subject_write_preserves_legacy_presentations():
    from bti.picks.auto.write import subject_operations
    old = {"names": [{"name": "Ada", "also": [], "line": "b0001", "where": {"region": "HEAD"}, "sure": True, "words": ""}]}
    new = [{"id": "river", "kind": "thing", "name": "river", "strip": False, "where": {"region": "RIVER"}}]
    ops = subject_operations(old, new, {"b0002": [{"id": "river", "words": "the river"}]})
    assert [x["id"] for x in ops[0]["subjects"]] == ["legacy_1", "river"]
    assert {o["beat"] for o in ops[1:]} == {"b0001", "b0002"}


def test_existing_asset_subject_survives_a_partial_plan():
    from bti.picks.auto.write import resolve_subjects
    row = {"id": "painter", "kind": "person", "name": "the painter", "strip": True, "where": {"asset": "A3"}}
    assert resolve_subjects({"subjects": [row], "lines": []}, {}, {}, {}, set()) == [row]


def test_later_line_reuses_the_same_subject_picture():
    from types import SimpleNamespace
    from bti.picks.auto.write import build_lines, _ops_for
    inp = SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"})
    want = {"type": "context", "search": "portrait of painter", "kind": "portrait", "what": "Chân dung", "entity": "painter"}
    plan = {"subjects": [{"id": "painter", "kind": "person", "name": "painter", "strip": True, "where": {"want": "b0001.1"}}],
            "lines": [{"beat": "b0001", "reason": "Chân dung.", "show": [want], "about": [{"id": "painter", "words": "painter"}]},
                      {"beat": "b0002", "reason": "Cùng người.", "show": [], "about": [{"id": "painter", "words": "she"}]}]}
    choices = {"b0001.1": {"pick": {"source": "book", "source_id": "one"}, "reason": "Chân dung."}}
    lines = build_lines(inp, plan, choices, {("book", "one"): "A3"}, {}, {}, [], set())
    assert lines[1]["items"][0]["src"] == ("book", "one")
    assert any(op["op"] == "set_picks" and op["beat"] == "b0002" for op in _ops_for(lines, "A"))


def test_concrete_subject_can_record_a_missing_own_picture():
    subject = {"id": "traveller", "kind": "person", "name": "traveller", "strip": False, "where": None}
    assert doc.doc_problem({"subjects": [subject]}) is None


def test_later_missing_subject_picture_is_counted_and_uses_previous_concrete_subject():
    from types import SimpleNamespace
    from bti.picks.auto.write import build_lines
    inp = SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"})
    plan = {"subjects": [{"id": "figure", "kind": "person", "name": "figure", "strip": False, "where": {"region": "FIGURE"}},
                         {"id": "city", "kind": "place", "name": "city", "strip": True, "where": {"want": "b0002.1"}}],
            "lines": [{"beat": "b0001", "reason": "Hình người.", "show": [{"type": "detail", "region": "FIGURE"}], "about": [{"id": "figure", "words": "figure"}]},
                      {"beat": "b0002", "reason": "Nói về thành phố.", "show": [], "about": [{"id": "city", "words": "city"}]}]}
    choices = {"b0002.1": {"id": "b0002.1", "pick": None, "code": "agent_none", "what": "city", "reason": ""}}
    rows = build_lines(inp, plan, choices, {}, {}, {}, [], set())
    assert rows[1]["items"][0]["region"] == "FIGURE"
    assert rows[1]["missing"][0]["code"] == "agent_none"


def test_map_and_clip_wants_require_a_subject_and_keep_its_id():
    from bti.picks.auto import shapes
    ctx = shapes.PlanCtx(beats=[{"id": "b0001", "chapter": "c01", "words": 10}], targets=["b0001"])
    subject = {"id": "route", "kind": "place", "name": "route", "strip": False, "where": {"want": "b0001.1"}}
    for want in ({"type": "map", "places": ["Paris, France", "Rome, Italy"], "entity": "route"},
                 {"type": "clip", "search": "river water", "what": "Dòng sông", "entity": "route"}):
        errors = []
        line = {"beat": "b0001", "show": [want], "about": []}
        assert shapes._subjects([subject], [line], {}, ctx, errors) and not errors
        cleaned = shapes._item(want, "show", {}, errors, [])
        assert cleaned["entity"] == "route"
        del want["entity"]
        errors = []
        shapes._subjects([subject], [line], {}, ctx, errors)
        assert errors


def test_subject_search_kind_matches_subject_kind():
    from bti.picks.auto import shapes
    ctx = shapes.PlanCtx(beats=[{"id": "b0001", "chapter": "c01", "words": 10}], targets=["b0001"])
    subject = {"id": "author", "kind": "person", "name": "author", "strip": True, "where": {"want": "b0001.1"}}
    line = {"beat": "b0001", "about": [], "show": [{"type": "context", "entity": "author", "kind": "place", "period": "then"}]}
    errors = []
    shapes._subjects([subject], [line], {}, ctx, errors)
    assert errors
    line["show"][0]["kind"] = "portrait"
    errors = []
    shapes._subjects([subject], [line], {}, ctx, errors)
    assert not errors


def test_choice_requires_confirmation_that_picture_shows_the_subject():
    from bti.picks.auto import shapes
    ctx = shapes.ChoiceCtx(wants={"b0001.1": 1}, subject_wants={"b0001.1": "author"})
    choice = {"wants": [{"id": "b0001.1", "pick": 1, "reason": "Chân dung phù hợp."}], "regions": []}
    assert not shapes.check_choice(choice, ctx).ok
    choice["wants"][0]["shows_subject"] = True
    assert shapes.check_choice(choice, ctx).ok
    choice["wants"][0]["pick"] = None
    choice["wants"][0].pop("shows_subject")
    assert shapes.check_choice(choice, ctx).ok


def test_second_picture_requires_a_different_aspect_named_in_line():
    from bti.picks.auto import shapes
    ctx = shapes.PlanCtx(beats=[{"id": "b0001", "chapter": "c01", "words": 10}, {"id": "b0002", "chapter": "c01", "words": 10}],
                         targets=["b0001", "b0002"], line_texts={"b0002": "She appears in an older portrait."})
    subjects = [{"id": "author", "kind": "person", "name": "author", "strip": True, "where": {"want": "b0001.1"}}]
    rows = [{"beat": "b0001", "about": [], "show": [{"type": "context", "entity": "author", "kind": "portrait"}]},
            {"beat": "b0002", "about": [], "show": [{"type": "context", "entity": "author", "kind": "portrait"}]}]
    errors = []
    shapes._subjects(subjects, rows, {}, ctx, errors)
    assert errors
    rows[1]["show"][0]["aspect"] = "older portrait"
    errors = []
    shapes._subjects(subjects, rows, {}, ctx, errors)
    assert not errors
    rows[1]["show"][0]["aspect"] = "unspoken appearance"
    errors = []
    shapes._subjects(subjects, rows, {}, ctx, errors)
    assert errors


def test_failed_initial_search_uses_previous_subject_not_plan_detail():
    from types import SimpleNamespace
    from bti.picks.auto.write import build_lines
    inp = SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"})
    want = {"type": "context", "entity": "city", "search": "old city", "kind": "place", "what": "Thành phố"}
    plan = {"subjects": [{"id": "figure", "kind": "person", "name": "figure", "strip": False, "where": {"region": "FIGURE"}},
                         {"id": "city", "kind": "place", "name": "city", "strip": True, "where": {"want": "b0002.1"}}],
            "lines": [{"beat": "b0001", "reason": "Hình người.", "show": [{"type": "detail", "region": "FIGURE"}], "about": [{"id": "figure", "words": "figure"}]},
                      {"beat": "b0002", "reason": "Thành phố.", "show": [want], "about": [{"id": "city", "words": "city"}],
                       "fallback": {"type": "detail", "region": "HANDS"}}]}
    choices = {"b0002.1": {"id": "b0002.1", "pick": None, "code": "agent_none", "what": "city", "reason": ""}}
    rows = build_lines(inp, plan, choices, {}, {}, {}, [], set())
    assert rows[1]["items"][0]["region"] == "FIGURE"
    assert rows[1]["missing"][0]["code"] == "agent_none"


def test_text_subjects_and_optional_proper_name_aliases_are_valid():
    subject = {"id": "law", "kind": "text", "name": "The Charter", "also": ["The Great Charter"], "strip": False, "where": None}
    assert doc.doc_problem({"subjects": [subject]}) is None
    assert doc.normalize({"subjects": [subject]})["subjects"][0]["also"] == ["The Great Charter"]
    assert doc.doc_problem({"subjects": [{**subject, "also": [42]}]}) is not None
    assert doc.doc_problem({"subjects": [{**subject, "strip": True}]}) is not None


def test_subject_choice_must_confirm_period_or_missing_period_pictures():
    from bti.picks.auto import shapes
    ctx = shapes.ChoiceCtx(wants={"b0001.1": 1}, subject_wants={"b0001.1": "author"}, period_wants=["b0001.1"])
    row = {"id": "b0001.1", "pick": 1, "shows_subject": True, "reason": "Chân dung phù hợp."}
    choice = {"wants": [row], "regions": []}
    assert not shapes.check_choice(choice, ctx).ok
    row["period_picture"] = False
    assert not shapes.check_choice(choice, ctx).ok
    row["no_period_picture"] = True
    assert shapes.check_choice(choice, ctx).ok
    row["period_picture"] = True
    row.pop("no_period_picture")
    assert shapes.check_choice(choice, ctx).ok


def test_map_subject_must_be_a_place_or_route():
    from bti.picks.auto import shapes
    context = shapes.PlanCtx(beats=[{"id": "b0001", "chapter": "c01", "words": 5}], targets=["b0001"])
    row = {"beat": "b0001", "about": [], "show": [{"type": "map", "entity": "route", "places": ["Paris, France", "Rome, Italy"]}]}
    subject = {"id": "route", "kind": "person", "name": "traveller", "strip": False, "where": {"want": "b0001.1"}}
    errors = []
    shapes._subjects([subject], [row], {}, context, errors)
    assert errors
    subject['kind'] = 'place'
    errors = []
    shapes._subjects([subject], [row], {}, context, errors)
    assert not errors


def test_no_picture_concrete_subject_is_a_warning_and_missing_line():
    from types import SimpleNamespace
    from bti.picks.auto import shapes, write
    context = shapes.PlanCtx(beats=[{"id": "b0001", "chapter": "c01", "words": 4}], targets=["b0001"],
                             line_texts={"b0001": "A traveller arrived."})
    plan = {"subjects": [{"id": "traveller", "kind": "person", "name": "traveller", "strip": False, "where": None}],
            "regions": [], "lines": [{"beat": "b0001", "reason": "Người đi đường.", "kinds": ["outside"],
            "about": [{"id": "traveller", "words": "traveller"}], "show": []}]}
    result = shapes.check_plan(plan, context)
    assert result.ok, result.text()
    assert any('no picture' in warning for warning in result.warnings)
    rows = write.build_lines(SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"}), result.value, {}, {}, {}, {}, [], set())
    assert rows[0]['missing'] and rows[0]['missing'][0]['code'] == 'agent_none'
    assert rows[0]['items'][0]['asset'] == 'main'


def test_reused_clip_keeps_video_role():
    from types import SimpleNamespace
    from bti.picks.auto.write import build_lines
    inp = SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"})
    plan = {"subjects": [{"id": "river", "kind": "place", "name": "river", "strip": False, "where": {"want": "b0001.1"}}],
            "lines": [{"beat": "b0001", "reason": "Dòng sông.", "show": [{"type": "clip", "seconds": 6}], "about": []},
                      {"beat": "b0002", "reason": "Vẫn là dòng sông.", "show": [], "about": [{"id": "river", "words": "river"}]}]}
    choices = {"b0001.1": {"pick": {"source": "commons", "source_id": "v"}, "reason": "Dòng sông."}}
    rows = build_lines(inp, plan, choices, {("commons", "v"): "V1"}, {}, {}, [], set())
    assert rows[1]["items"][0]["role"] == "video"


def test_existing_video_subject_reuses_video_role():
    from types import SimpleNamespace
    from bti.picks.auto.write import build_lines
    inp = SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"}, picks={"assets": {"V1": {"kind": "video"}}})
    plan = {"subjects": [{"id": "river", "kind": "place", "name": "river", "strip": False, "where": {"asset": "V1"}}],
            "lines": [{"beat": "b0002", "reason": "Dòng sông.", "show": [], "about": [{"id": "river", "words": "river"}]}]}
    rows = build_lines(inp, plan, {}, {}, {}, {}, [], set())
    assert rows[0]["items"][0]["role"] == "video"


def test_distinct_aspect_reaches_search_and_choosing_input():
    from bti.picks.auto import shapes, search
    plan = {"subjects": [{"id": "author", "name": "Ada"}],
            "lines": [{"beat": "b0002", "kinds": ["outside"], "show": [
                {"type": "context", "entity": "author", "aspect": "older portrait", "kind": "portrait",
                 "search": "older portrait Ada", "what": "Chân dung về sau", "period": "then"}]}]}
    want = shapes.wants_of(plan)[0]
    assert want["aspect"] == "older portrait"
    assert search._new_want(want)["aspect"] == "older portrait"


def test_modern_fallback_cannot_be_claimed_as_period_picture():
    from bti.picks.auto import shapes
    context = shapes.ChoiceCtx(wants={'b0001.1': 1}, subject_wants={'b0001.1': 'city'},
                               period_wants=['b0001.1'], modern_wants=['b0001.1'])
    row = {'id': 'b0001.1', 'pick': 1, 'shows_subject': True, 'period_picture': True, 'reason': 'Hình thành phố.'}
    choice = {'wants': [row], 'regions': []}
    assert not shapes.check_choice(choice, context).ok
    row.update(period_picture=False, no_period_picture=True)
    assert shapes.check_choice(choice, context).ok


def test_incomplete_period_search_cannot_approve_a_modern_photo():
    from bti.picks.auto import shapes
    context = shapes.ChoiceCtx(wants={'b0001.1': 1}, subject_wants={'b0001.1': 'city'},
                               period_wants=['b0001.1'], incomplete_wants=['b0001.1'])
    row = {'id': 'b0001.1', 'pick': 1, 'shows_subject': True, 'period_picture': False,
           'no_period_picture': True, 'reason': 'Hình thành phố.'}
    assert not shapes.check_choice({'wants': [row], 'regions': []}, context).ok
    row['period_picture'] = True
    assert shapes.check_choice({'wants': [row], 'regions': []}, context).ok



def test_multi_genre_subject_plans_and_person_fallback_rules():
    from bti.picks.auto import shapes
    # 1. Landscape with village & river (place region enforces its own region fallback)
    l_ctx = shapes.PlanCtx(
        beats=[{"id": "b0001", "chapter": "c01", "words": 12}],
        targets=["b0001"],
        existing_regions={"VILLAGE": [0.1, 0.2, 0.4, 0.5], "RIVER": [0.4, 0.5, 0.9, 0.8]},
        line_texts={"b0001": "The mountain village overlooks the winding river."},
    )
    l_plan = {
        "subjects": [{"id": "village", "kind": "place", "name": "village", "strip": False, "where": {"region": "VILLAGE"}}],
        "regions": [],
        "lines": [{"beat": "b0001", "reason": "Nói về ngôi làng.", "kinds": ["detail"],
                   "about": [{"id": "village", "words": "village"}],
                   "show": [{"type": "detail", "region": "VILLAGE"}],
                   "fallback": {"type": "detail", "region": "RIVER"}}],
    }
    assert not shapes.check_plan(l_plan, l_ctx).ok
    l_plan["lines"][0]["fallback"] = {"type": "detail", "region": "VILLAGE"}
    assert shapes.check_plan(l_plan, l_ctx).ok

    # 2. Crowded religious scene with saint, scripture (kind text, strip False), and illustrating work
    r_ctx = shapes.PlanCtx(
        beats=[{"id": "b0001", "chapter": "c01", "words": 15}],
        targets=["b0001"],
        existing_regions={"SAINT_A": [0.2, 0.2, 0.4, 0.7]},
        line_texts={"b0001": "Saint Lucy holds the Gospel shown in an earlier illuminated miniature."},
    )
    r_plan = {
        "subjects": [
            {"id": "lucy", "kind": "person", "name": "Saint Lucy", "strip": True, "where": {"region": "SAINT_A"}},
            {"id": "gospel", "kind": "text", "name": "Gospel", "strip": False, "where": None},
            {"id": "miniature", "kind": "work", "name": "illuminated miniature", "strip": False, "where": {"want": "b0001.1"}},
        ],
        "regions": [],
        "lines": [{"beat": "b0001", "reason": "Thánh nữ và bản tiểu họa.", "kinds": ["outside"],
                   "about": [{"id": "lucy", "words": "Saint Lucy"}, {"id": "gospel", "words": "the Gospel"},
                             {"id": "miniature", "words": "illuminated miniature"}],
                   "show": [{"type": "context", "entity": "miniature", "kind": "work", "search": "Saint Lucy illuminated miniature",
                             "what": "Bản tiểu họa thời trung cổ", "period": "then"}],
                   "fallback": {"type": "detail", "region": "SAINT_A"}}],
    }
    assert shapes.check_plan(r_plan, r_ctx).ok

    # 3. Arnolfini-like couple line: wife's region required as fallback, not hands
    c_ctx = shapes.PlanCtx(
        beats=[{"id": "b0001", "chapter": "c01", "words": 20}],
        targets=["b0001"],
        existing_regions={"WOMAN": [0.5, 0.15, 0.8, 0.9], "HANDS": [0.42, 0.48, 0.55, 0.58]},
        line_texts={"b0001": "Beside him, a woman in green rests her hand in his. She is usually named as his wife, Costanza Trenta."},
    )
    c_plan = {
        "subjects": [{"id": "wife", "kind": "person", "name": "Costanza Trenta", "strip": True, "where": {"region": "WOMAN"}}],
        "regions": [],
        "lines": [{"beat": "b0001", "reason": "Giới thiệu người phụ nữ.", "kinds": ["detail"],
                   "about": [{"id": "wife", "words": "Costanza Trenta"}],
                   "show": [{"type": "detail", "region": "WOMAN"}],
                   "fallback": {"type": "detail", "region": "HANDS"}}],
    }
    assert not shapes.check_plan(c_plan, c_ctx).ok
    c_plan["lines"][0]["fallback"] = {"type": "detail", "region": "WOMAN"}
    assert shapes.check_plan(c_plan, c_ctx).ok


def test_where_want_must_belong_to_that_subject_and_region_cannot_satisfy_empty_outside():
    from bti.picks.auto import shapes
    ctx = shapes.PlanCtx(
        beats=[{"id": "b0001", "chapter": "c01", "words": 10}, {"id": "b0002", "chapter": "c01", "words": 10}],
        targets=["b0001", "b0002"],
        existing_regions={"HEAD": [0.1, 0.1, 0.3, 0.3]},
        line_texts={"b0001": "Ada painted Rome.", "b0002": "The portrait shows the sitter."},
    )
    # Subject A points where.want to b0001.1, whose entity is B
    mismatch = {
        "subjects": [
            {"id": "a", "kind": "person", "name": "Ada", "strip": True, "where": {"want": "b0001.1"}},
            {"id": "b", "kind": "place", "name": "Rome", "strip": True, "where": {"want": "b0001.1"}},
        ],
        "regions": [],
        "lines": [
            {"beat": "b0001", "reason": "Thành phố Rome.", "kinds": ["outside"], "about": [{"id": "b", "words": "Rome"}],
             "fallback": {"type": "whole"},
             "show": [{"type": "context", "entity": "b", "kind": "place", "search": "Rome view", "what": "Cảnh thành Rome"}]},
            {"beat": "b0002", "reason": "Chân dung.", "kinds": ["detail"], "about": [], "show": [{"type": "detail", "region": "HEAD"}]},
        ],
    }
    assert not shapes.check_plan(mismatch, ctx).ok

    # An outside line with show: [] cannot reuse a painting-only region
    region_outside = {
        "subjects": [{"id": "sitter", "kind": "person", "name": "sitter", "strip": False, "where": {"region": "HEAD"}}],
        "regions": [],
        "lines": [
            {"beat": "b0001", "reason": "Chân dung.", "kinds": ["detail"], "about": [{"id": "sitter", "words": "Ada"}],
             "show": [{"type": "detail", "region": "HEAD"}]},
            {"beat": "b0002", "reason": "Ngoài tranh.", "kinds": ["outside"], "about": [{"id": "sitter", "words": "sitter"}],
             "show": []},
        ],
    }
    assert not shapes.check_plan(region_outside, ctx).ok


def test_duplicate_about_mentions_on_reuse_line_do_not_duplicate_items_or_missing():
    from types import SimpleNamespace
    from bti.picks.auto.write import build_lines
    inp = SimpleNamespace(beat=lambda bid: {"no": 1, "chapter": "c01"})
    want = {"type": "context", "search": "Ada portrait", "kind": "portrait", "what": "Chân dung", "entity": "ada"}
    plan = {
        "subjects": [{"id": "ada", "kind": "person", "name": "Ada", "strip": True, "where": {"want": "b0001.1"}}],
        "lines": [
            {"beat": "b0001", "reason": "Chân dung.", "show": [want], "about": [{"id": "ada", "words": "Ada"}]},
            {"beat": "b0002", "reason": "Vẫn nói về Ada.", "show": [],
             "about": [{"id": "ada", "words": "Ada"}, {"id": "ada", "words": "she"}]},
        ],
    }
    rows_found = build_lines(inp, plan, {"b0001.1": {"pick": {"source": "book", "source_id": "one"}, "reason": "Rõ."}},
                             {("book", "one"): "A3"}, {}, {}, [], set())
    assert len(rows_found[1]["items"]) == 1
    rows_miss = build_lines(inp, plan, {"b0001.1": {"id": "b0001.1", "pick": None, "code": "agent_none", "what": "Ada", "reason": ""}},
                            {}, {}, {}, [], set())
    assert len(rows_miss[1]["missing"]) == 1 and len(rows_miss[1]["items"]) == 1


def test_resumed_write_reuses_already_written_subject_asset(tmp_path, monkeypatch):
    from auto_helpers import install_sources, make_auto_project
    from bti.picks.auto import inputs as ainputs, write as awrite
    install_sources(monkeypatch)
    pdir = make_auto_project(tmp_path)
    inp = ainputs.load(pdir)
    want = {"type": "context", "search": "portrait", "alt": [], "kind": "portrait", "entity": "painter", "period": "then", "what": "Chân dung"}
    plan = {
        "subjects": [{"id": "painter", "kind": "person", "name": "painter", "strip": True, "where": {"want": "b0001.1"}}],
        "regions": {},
        "lines": [
            {"beat": "b0001", "reason": "Chân dung.", "kinds": ["outside"], "about": [{"id": "painter", "words": "painter"}],
             "show": [want], "fallback": {"type": "whole"}},
            {"beat": "b0003", "reason": "Vẫn là họa sĩ.", "kinds": ["outside"], "about": [{"id": "painter", "words": "painter"}],
             "show": []},
        ],
    }
    search = {"wants": {"b0001.1": {"candidates": [{"n": 1, "source": "commons", "source_id": "File:Portrait A.jpg", "media": "image"}]}}, "books": []}
    choice = {"wants": {"b0001.1": {"pick": ("c", 1), "reason": "Đúng chân dung."}}, "regions": {}}
    run_state = {"lines": {"b0001": {"reason": "Chân dung.", "kind": "pictures", "clips": 0, "missing": [], "no": 1, "outside_without": False}},
                 "imported": 1, "regions_made": 0, "regions_tight": 0, "batches": ["batch_0001"], "stale_cleaned": True}
    res = awrite.run(pdir, inp, plan, search, choice, run_state, actor="agent:test", cancelled=lambda: False, progress=lambda *a: None)
    assert res["stopped"] is None and res["lines_done"] == 2
    saved = doc.load_or_new(pdir)
    asset_key = saved["subjects"][0]["where"]["asset"]
    assert asset_key in saved["assets"]
    assert saved["beats"]["b0003"]["items"][0]["asset"] == asset_key


def test_outside_fallback_to_other_subject_asset_is_counted_as_outside_without_picture():
    d = doc.normalize({
        "main_asset": "A",
        "assets": {"A": {"file": "media/a.png", "kind": "image"}, "B": {"file": "media/b.png", "kind": "image"}},
        "subjects": [
            {"id": "painter", "kind": "person", "name": "Ada", "strip": True, "where": {"asset": "B"}},
            {"id": "city", "kind": "place", "name": "Rome", "strip": True, "where": None},
        ],
        "beats": {
            "b0001": {"items": [{"asset": "B", "region": None, "role": "context", "note": ""}], "status": "picked",
                      "kinds": ["outside"], "about": [{"id": "painter", "words": "Ada"}]},
            "b0002": {"items": [{"asset": "B", "region": None, "role": "context", "note": ""}], "status": "picked",
                      "kinds": ["outside"], "about": [{"id": "city", "words": "Rome"}],
                      "missing": [{"what": "Rome", "code": "agent_none"}]},
        },
    })
    assert doc.outside_without_picture(d, "b0001") is False
    assert doc.outside_without_picture(d, "b0002") is True
    assert doc.outside_summary(d, ["b0001", "b0002"]) == {"lines": 2, "with_picture": 1, "without": ["b0002"]}
    assert [i["beat"] for i in doc.issues(d, None, ["b0001", "b0002"]) if i["code"] == "outside_no_picture"] == ["b0002"]


def test_picks_auto_templates_have_no_arnolfini_specifics():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "skills" / "picks_auto"
    texts = {p.name: p.read_text(encoding="utf-8") for p in (root / "PLAN.template.md", root / "CHOOSE.template.md", root / "TIGHTEN.template.md")}
    banned = ("Arnolfini", "Jan van Eyck", "convex mirror", "carved woman standing on a dragon", "brass chandelier", "pattens", "bàn chải")
    for name, body in texts.items():
        low = body.casefold()
        for phrase in banned:
            assert phrase.casefold() not in low, f"{name} still mentions {phrase!r}"


def test_subject_where_accepts_multiple_places_and_rejects_bad_lists():
    from bti.picks.doc import doc_problem
    subject = {"id": "s", "kind": "person", "name": "A", "strip": True, "where": {"region": "HEAD"}}
    assert doc_problem({"subjects": [subject]}) is None
    subject["where"] = [{"region": "HEAD"}, {"asset": "B"}]
    assert doc_problem({"subjects": [subject]}) is None
    for invalid in ([], [{"region": ""}], [{"region": "HEAD", "asset": "B"}], [None]):
        subject["where"] = invalid
        assert doc_problem({"subjects": [subject]}) is not None


def test_resolve_subject_retains_all_available_places():
    from bti.picks.auto.write import resolve_subjects
    plan = {'subjects': [{'id': 's', 'kind': 'person', 'name': 'A', 'strip': True,
                          'where': [{'region': 'HEAD'}, {'want': 'b0001.1'}]}]}
    chosen = {'b0001.1': {'pick': {'source': 'museum', 'source_id': '123'}}}
    assert resolve_subjects(plan, chosen, {('museum', '123'): 'B'}, {'HEAD': 'HEAD_2'}, set())[0]['where'] == [
        {'region': 'HEAD_2'}, {'asset': 'B'}]
    assert resolve_subjects(plan, chosen, {}, {}, set())[0]['where'] == [{'region': 'HEAD'}]
