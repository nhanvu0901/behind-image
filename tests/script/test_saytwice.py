from bti.script.store import Beat
from bti.script.validate import validate_outline, validate_narration
from script_helpers import make_outline, make_narration


def test_fact_in_three_chapters_is_error():
    o = make_outline()
    for c in o.chapters:
        c.facts = ['f01']
    issues = [i for i in validate_outline(o) if i['code'] == 'fact_in_too_many_chapters']
    assert len(issues) == 1 and issues[0]['level'] == 'error' and issues[0]['chapters'] == ['c01', 'c02', 'c03']


def test_repeated_fact_and_words_are_reported():
    o = make_outline(True)
    n = make_narration(per_chapter=1)
    texts = ['The little dog lies beside her feet.', 'THE LITTLE DOG lies beside her feet!', 'The little dog lies beside her feet.']
    for c, text in zip(n.chapters, texts):
        c.beats[0].text = text
    issues = validate_narration(n, o)
    for code in ('fact_said_too_often', 'return_same_words', 'sentence_repeated'):
        assert any(i['code'] == code for i in issues)


def test_repair_plan_targets_later_chapters_with_specific_evidence():
    from bti.script.generate import repetition_repairs
    n = make_narration(per_chapter=1)
    for c in n.chapters:
        c.beats[0].text = 'The little dog lies beside her feet.'
    plan = repetition_repairs(n, None)
    assert set(plan) == {'c02', 'c03'}
    assert 'f01' in plan['c03'] and 'b0001' in plan['c03'] and 'little dog' in plan['c03']


def test_cast_and_painting_names_alone_are_not_same_word_returns():
    n = make_narration(per_chapter=1)
    n.chapters = n.chapters[:2]
    for c in n.chapters:
        c.beats[0].text = 'Giovanni di Arnolfini The Arnolfini Portrait.'
    brief = {'painting': {'title': 'The Arnolfini Portrait'}, 'cast': [{'name': 'Giovanni di Arnolfini'}]}
    from bti.script.validate import repetition_issues
    assert not [i for i in repetition_issues(n, brief) if i['code'] == 'return_same_words']
    assert [i for i in repetition_issues(n, brief) if i['code'] == 'sentence_repeated']


def test_job_repairs_repetition_with_evidence(tproj):
    import time
    from bti.script import generate, store
    from bti.script.providers import mock
    from bti.script.runner import ScriptJobs
    spec = {'id': 'mock', 'provider': 'mock', 'model': 'mock', 'key_env': None}
    jobs = ScriptJobs()
    def wait(job):
        deadline = time.time() + 30
        while job.state not in ('done', 'error', 'cancelled') and time.time() < deadline:
            time.sleep(.02)
        assert job.state == 'done', job.error
        return job
    wait(jobs.start('outline', tproj.name, 'mock', lambda j: generate.run_outline(j, tproj, spec)))
    o = store.load_outline(tproj)
    store.approve(tproj, 'outline', o.rev())
    mock.CALLS.clear()
    job = wait(jobs.start('narration', tproj.name, 'mock', lambda j: generate.run_narration(j, tproj, spec)))
    retries = [c['user'] for c in mock.CALLS if c['retry']]
    assert job.result['repetition_repaired'] and retries
    assert any('Each point may be said at most twice' in text and 'Fact f' in text and 'b0' in text for text in retries)


def test_brief_uses_known_visual_cast_for_name_exemption(tproj):
    import json
    from bti.script.brief import build_brief
    (tproj / 'visual.json').write_text(json.dumps({'cast': [{'name': 'Giovanni di Arnolfini', 'also': []}]}), encoding='utf-8')
    assert build_brief(tproj)['cast'][0]['name'] == 'Giovanni di Arnolfini'
