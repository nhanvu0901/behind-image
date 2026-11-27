from pathlib import Path
import re


def test_instructions_cover_varied_art_and_fit_the_budget():
    root = Path(__file__).resolve().parents[2] / 'skills/visual_plan'
    plan = (root / 'PLAN.template.md').read_text(encoding='utf-8')
    choose = (root / 'CHOOSE.template.md').read_text(encoding='utf-8')
    assert len((plan + ' ' + choose).split()) <= 2000
    assert all(word in plan.lower() for word in ('portrait', 'landscape', 'religious', 'still life'))
    assert 'arnolfini' not in plan.lower()
    assert not re.search(r'\b(?:MAP|LAY|DOC|KEY|NUM|HI|AN|X-ANN)-\d', plan + choose)
    assert not re.search(r'\b\d+\s*(?:px|pixels?)\b', plan + choose, re.I)
    assert all(phrase in plan.lower() for phrase in ('face or figure', 'even if a similar picture', 'unfamiliar', 'small detail', 'fallback'))


def test_choose_instruction_mentions_the_validation_command():
    root = Path(__file__).resolve().parents[2] / 'skills/visual_plan'
    assert '{{CHECK_CMD}}' in (root / 'CHOOSE.template.md').read_text(encoding='utf-8')
