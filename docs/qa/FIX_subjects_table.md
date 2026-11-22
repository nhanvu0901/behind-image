# Subjects table and subject-first picks

## Table shape and operations
- `picks.json` stores `subjects` (`id`, `kind`, `name`, optional `also`, optional `sub`, `strip`, `where`) and ordered `beats[beat].about` (`id`, `words`).
- Subject `kind` values are `person`, `thing`, `place`, `work`, `idea`, and `text`. `idea` and `text` cannot request strips (`strip: true` is rejected).
- `where` holds `{"region": R}` on the main painting, `{"asset": key}` for an imported asset, or `null` when a subject has no picture of its own (without mistaking a fallback for the subject itself).
- `bti.picks.doc.subject_view(picks)` adapts legacy `names` documents to person subjects without rewriting older files; `doc.outside_without_picture`, `doc.outside_summary`, and `doc.issues` (`outside_no_picture`) also count subject-table outside lines that fell back to another subject's non-main asset when `missing` is recorded.
- Typed operations `set_subjects` and `set_about` validate non-blank names/aliases/words, `strip` rules, unique ids, and region/asset targets, with change-log and undo support.

## Picks agent, search, choice, and write
- `bti.picks.auto.shapes` validates `subjects`, ordered `about` mentions, subject-bound `context`/`map`/`clip` wants (`entity` matching a subject id, `where.want` belonging to that subject), search `kind` matching subject `kind`, `map` restricted to `place` subjects, `period: "then"` first, distinct spoken `aspect` for secondary searches, and subject-own region fallbacks for painting concrete subjects. `outside` lines with `show: []` may reuse an outside/existing subject picture, not a painting-only region.
- `bti.picks.auto.search` and `job` run period sources first, search modern stock (`pexels`/`pixabay`) only when a clean period search returns no candidates or when the chooser rejects complete period candidates (never opening modern fallback when a source was rate-limited, failed, or thumbnails were missing).
- `shapes.check_choice` requires `shows_subject: true` on selected subject-bound wants and explicit `period_picture` / `no_period_picture` classification on subject-bound context wants (chooser judgments, not independent factual proof).
- `bti.picks.auto.write` deduplicates repeated mentions in `about` when reusing a subject's picture, preserves subject-want downloads across resumed runs even when the defining beat was already written, and falls back to the nearest concrete subject (excluding `idea`) from the current or preceding line (reading `existing_picks` via `subject_view` on partial runs) or the whole painting, while leaving `subjects[].where` as `null` for missing pictures.
- `skills/picks_auto/` templates (`PLAN.template.md`, `CHOOSE.template.md`, `TIGHTEN.template.md`) and `shapes.py` error examples were cleaned of Arnolfini-specific details (`convex mirror`, `carved woman standing on a dragon`, `brass chandelier`, `Jan van Eyck`, etc.).

## Scope boundary (draft & viewer checks)
- Goals 3 and 4 (`bti/draft/`, `bti/engine/viewchecks.py`, `skills/storyboard_draft/`) belong to worker `subjdraft`; no viewer checks were folded or modified in this worktree.

## Verification
- Focused tests (`tests/picks/test_subjects_table.py tests/picks/test_auto_shapes.py tests/picks/test_auto_kinds.py tests/picks/test_auto_search.py tests/picks/test_auto_job.py tests/ops/test_picks_ops.py -q`): `321 passed, 1 warning in 42.66s`
- Full `tests/picks -q`: `485 passed, 1 warning in 123.42s (0:02:03)`
- Full `tests/ops -q`: `556 passed, 1 warning in 142.29s (0:02:22)`
- Full `tests/auto -q`: `255 passed, 1 warning in 97.89s (0:01:37)`
- Generators (`bti.cli.docgen --check`, `bti.ops.doc --check`, `bti.editor.hints --check`): exited 0 with no output
- Node (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`): `tests 499`, `pass 497`, `fail 1`, `skipped 1` (pre-existing unrelated failure in `tests/editor_frontend/idfix.test.mjs` expecting `/Settle/` in `strip_without_light` Vietnamese message)

## Not verified
- Live model sessions and real external picture source searches (all runs used fake agents and fake sources; no real model calls were made).
