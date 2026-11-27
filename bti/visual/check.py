"""Work-folder check for a visual script; review findings do not block."""
from __future__ import annotations
import json
from pathlib import Path
from bti.visual.validate import validate


def run_check(root: Path) -> dict:
    root = Path(root)
    try:
        context = root / 'inputs/context.json'
        context_data = json.loads(context.read_text(encoding='utf-8')) if context.exists() else {}
        mode = context_data.get('mode', 'plan')
        if mode == 'choose':
            from bti.visual.job import choice_errors
            choice = json.loads((root / 'out/choice.json').read_text(encoding='utf-8'))
            visual = json.loads((root / 'inputs/visual.json').read_text(encoding='utf-8'))
            search = json.loads((root / 'inputs/search.json').read_text(encoding='utf-8'))
            issues = [{'rule': 'choice', 'moment': None, 'message': e} for e in choice_errors(choice, visual, search)]
            if (root / 'tighten').is_dir():
                from bti.picks.auto import helper
                try:
                    report = helper.run_check(root / 'tighten')
                    issues.extend({'rule': 'region', 'moment': None, 'message': e} for e in report.errors)
                except SystemExit as e:
                    issues.append({'rule': 'region', 'moment': None, 'message': str(e)})
            return {'ok': not issues, 'issues': issues}
        doc = json.loads((root / 'out/visual.json').read_text(encoding='utf-8'))
        timing = json.loads((root / 'inputs/timing.json').read_text(encoding='utf-8'))
        picks = json.loads((root / 'inputs/picks.json').read_text(encoding='utf-8'))
        regions_file = root / 'out/regions.json'
        if regions_file.exists():
            regions = json.loads(regions_file.read_text(encoding='utf-8'))
            if not isinstance(regions, dict):
                raise ValueError('out/regions.json must be an object')
            from bti.picks.auto.shapes import clean_box, NAME_RE
            for name, row in regions.items():
                if not isinstance(name, str) or not NAME_RE.fullmatch(name) or not isinstance(row, dict) or not isinstance(row.get('what'), str) or not row['what'].strip():
                    raise ValueError(f'{name}: supply a region name, box and description')
                _, problem = clean_box(row.get('box'), name)
                if problem:
                    raise ValueError(problem)
            main = picks['assets'][picks['main_asset']]
            main.setdefault('regions', {}).update(regions)
        issues = validate(doc, timing, picks)
        if context_data.get('made_from') and doc.get('made_from') != context_data['made_from']:
            issues.append({'rule': 'shape', 'moment': None, 'message': 'Copy made_from from inputs/context.json.'})
    except (OSError, ValueError, TypeError, KeyError) as e:
        issues = [{'rule': 'shape', 'message': str(e), 'moment': None}]
    return {'ok': not any(i.get('level') != 'review' for i in issues), 'issues': issues}


def main():
    report = run_check(Path.cwd())
    for issue in report['issues']:
        print(f"{'REPORT' if issue.get('level') == 'review' else 'ERROR'} {issue['rule']}: {issue['message']}")
    print('OK' if report['ok'] else 'Please repair the errors and check again.')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
