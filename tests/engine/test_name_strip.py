import bti.engine.api  # noqa: F401
from bti.engine import registry


def test_name_strip_accepts_optional_second_line_and_preserves_old_default():
    bundle = registry.load_bundle('gae')
    spec = bundle.spec('X-ANN-01')
    params = {p['name']: p for p in spec['params']}
    assert params['sub']['default'] == ''
    assert registry.merged_params(spec, {'text': 'COSTANZA', 'sub': 'most often named'})['sub'] == 'most often named'
    assert registry.merged_params(spec, {'text': 'SETTLE'})['sub'] == ''


def test_name_strip_guidance_reaches_draft_catalogue():
    from bti.draft.techniques_md import generate
    text = generate(registry.load_bundle('gae'))
    assert 'JEAN DE DINTEVILLE' in text
    assert 'TAVERN SIGN' in text
    assert 'sub:string' in text


def test_second_line_is_checked_for_readability(tmp_path):
    from test_pointfix_checks import context, ov
    from bti.engine import viewchecks
    c = context(tmp_path, overlay=ov('X-ANN-01', text='Costanza', sub='most often named as the wife'))
    c.shots[0]['overlays'][0]['dur'] = 2.0
    issues = viewchecks._text_too_brief(c)
    assert [x['args']['text'] for x in issues] == ['most often named as the wife']
