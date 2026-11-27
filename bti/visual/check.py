"""Work-folder check for a visual script; review findings do not block."""
from __future__ import annotations
import json
from pathlib import Path
from bti.visual.validate import validate


def sync_tighten(root: Path) -> None:
    """Copy the session's latest region answers into the tighten helper's workspace."""
    from bti.fsio import atomic_replace
    source = root / 'out/tighten.json'
    destination = root / 'tighten/out/tighten.json'
    if source.is_file() and destination.parent.is_dir():
        part = destination.with_name(destination.name + '.part')
        part.write_bytes(source.read_bytes())
        atomic_replace(part, destination)


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
            extra_file = root / 'out/regions.json'
            if extra_file.exists():
                from bti.picks.doc import MAX_REGIONS
                extra = json.loads(extra_file.read_text(encoding='utf-8'))
                if not isinstance(extra, dict):
                    raise ValueError('out/regions.json must be an object')
                existing = set(context_data.get('existing_regions', []))
                planned = set(context_data.get('planned_regions', []))
                new = len((planned | set(extra)) - existing)
                kept = context_data.get('kept_regions', len(existing))
                if kept + new > MAX_REGIONS:
                    issues.append({'rule': 'region', 'moment': None, 'message': f'{kept} kept regions + {new} new regions exceeds {MAX_REGIONS}; reuse existing regions.'})
                elif extra:
                    issues.append({'rule': 'region', 'moment': None, 'message': 'Add regions during planning, not choosing; reuse the planned regions.'})
            tighten_file = root / 'out/tighten.json'
            if tighten_file.exists() and 'kept_regions' in context_data:
                from bti.picks.doc import MAX_REGIONS
                response = json.loads(tighten_file.read_text(encoding='utf-8'))
                rows = response.get('regions', []) if isinstance(response, dict) else []
                extra_names = {row['name'] for row in rows if isinstance(row, dict) and isinstance(row.get('name'), str) and row.get('action') != 'drop'}
                existing = set(context_data.get('existing_regions', []))
                planned = set(context_data.get('planned_regions', []))
                kept = context_data['kept_regions']
                new = len((planned | extra_names) - existing)
                if kept + new > MAX_REGIONS:
                    issues.append({'rule': 'region', 'moment': None, 'message': f'{kept} kept regions + {new} new regions exceeds {MAX_REGIONS}; reuse existing regions.'})
            if tighten_file.exists() and not (root / 'tighten').is_dir():
                issues.append({'rule': 'region', 'moment': None, 'message': 'No regions were supplied for tightening; add them during planning.'})
            if (root / 'tighten').is_dir():
                from bti.picks.auto import helper
                try:
                    sync_tighten(root)
                    report = helper.run_check(root / 'tighten')
                    issues.extend({'rule': 'region', 'moment': None, 'message': e.replace('look/', 'tighten/look/')} for e in report.errors)
                except SystemExit as e:
                    issues.append({'rule': 'region', 'moment': None, 'message': str(e).replace('look/', 'tighten/look/')})
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
            from bti.picks.doc import MAX_REGIONS
            existing = main.setdefault('regions', {})
            from bti.visual.regions import cleanup_names
            removable = cleanup_names(existing, doc, context_data.get('storyboard'), context_data.get('agent_regions', []))
            from bti.visual.regions import _strings
            removable -= set(_strings(context_data.get('legacy_names', [])))
            moments = doc.get('moments', []) if isinstance(doc, dict) else []
            lines = {m.get('line') for m in moments if isinstance(m, dict)} if isinstance(moments, list) else set()
            for bid, beat in context_data.get('old_beats', {}).items():
                if bid not in lines:
                    removable -= set(_strings(beat))
            kept = len(existing) - len(removable)
            new = len(set(regions) - (set(existing) - removable))
            if kept + new > MAX_REGIONS:
                raise ValueError(f'{kept} kept regions + {new} new regions exceeds {MAX_REGIONS}; reuse existing regions.')
            existing.update(regions)
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
