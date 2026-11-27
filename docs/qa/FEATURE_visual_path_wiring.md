# Visual path wiring

New projects select `visual`; existing projects without the setting remain `legacy`. The revision-checked setting is visible in status. The visual path plans a script, waits for picture approval, composes, reviews, scores, adds music, approves and exports. Automatic planning cannot spend on web search. The scorecard's five hard lines block automatic approval; other findings and missing wanted pictures are logged. Composed storyboards do not run the old 27 view checks. A changed script recomposes after picture approval. Validation now prevents an invalid visual script, or an old storyboard from a different path, being approved or exported.

## Real-data acceptance

The walks use separate snapshot copies of `arnolfini-v3`, the supplied golden visual script inserted through the store, fake agent availability and staged checkpoints. They are state-machine observations, not a completed model run or actual export. The review2 modules were copied unchanged into the snapshot and their action specs supplied in memory for this integration exercise; they are not yet present in this worktree. Fake edit and review route starts returned 200. No real project, live server, model or paid API was changed or called.

The golden script has 275 validation findings, including **137 errors**: V3 74, V8 35, V7 22, V5 4, V1 1 and V6 1. The store saves the supplied script, but automatic composition is refused; approval and export remain blocked until it is corrected. The errors include a start word mismatch, required subjects or regions missing, overly long subtitle text, and a missing term marker. Consequently later visual checkpoints below are staged inspections of existing data, not successful progression past the gate.

The tables list path-specific offered actions alongside the common script, title, voice, pipeline-setting and manual picture actions. `next` names the actual action or wait message; automatic decisions were inspected with fake agents. A `blocked` action was present in the answer but not ready. The outline warning is `disputed_no_conflict`; the legacy picture warning comprises three `outside_no_picture` findings.

| Visual checkpoint | Offered path actions | Next / automatic decision |
|---|---|---|
| New | outline generation and approval | `outline.generate` / same |
| Outline | outline approval | `outline.approve` / stops `quality_warning` |
| Narration | `voice.generate`, hand picture actions, `visual.plan`, `picks.approve` | `voice.generate` / same |
| Voice | `visual.plan`, picture gate and hand actions, all waiting for content | waits for picks content / `nothing_to_do` |
| Picks | `visual.plan`, `picks.approve`, `storyboard.compose` | waits for picks content / `nothing_to_do`; gate and compose blocked by `visual_script_valid` |
| Edit (staged) | `visual.edit`, compose, review, scorecard, storyboard gate and music | waits for edit content / `nothing_to_do`; the old board is not a valid composition |
| Export (staged) | compose, scorecard, music and export | waits for export content / `nothing_to_do`; compose, scorecard and export blocked |
| Fake exported (staged) | same as export | waits for export content / `nothing_to_do` |

| Legacy checkpoint | Offered path actions | Next / automatic decision |
|---|---|---|
| New | outline generation and approval | `outline.generate` / same |
| Outline | outline approval | `outline.approve` / stops `quality_warning` |
| Narration | voice, hand pictures, `picks.auto`, picture gate | `voice.generate` / same |
| Voice | hand pictures, `picks.auto`, picture gate | waits for picks content / `nothing_to_do` |
| Picks | `picks.auto`, `picks.edit`, picture gate and hand actions | `picks.approve` / stops `quality_warning` |
| Edit (staged) | `draft.start`, `draft.edit`, review, scorecard, storyboard gate and music | `storyboard.review` / same |
| Export (staged) | `export.start`, scorecard and music | `export.start` / same |
| Fake exported (staged) | export, scorecard and music | `export.start` / same: placeholder is not a valid export |

For `next`, action names above abbreviate the printed `bti do <checkpoint-project> <action> --yes-cost --wait` for long jobs and `bti approve <checkpoint-project> <gate>` for gates. Wait messages were printed instead of commands where stated.

Before adding the validation guard, exploratory composition of that invalid script produced 114 shots and six contact sheets. Its metrics included 5.2% small-painting share, 0.36 marks/minute, maximum mark height 0.246 of frame, no marks on a person, 40 subjects not shown, and a longest borrowed-picture gap of 554.2 seconds. Inspection showed repeated painting crops and very small portraits between black side bars. These are diagnostic outputs from invalid input, not an accepted visual video. The legacy copy had 117 shots and six sheets; 11.39% small-painting share, 4.46 marks/minute, nine marks on people, maximum mark height 2.676, five subjects not shown and the same 554.2-second longest borrowed-picture gap. Inspection showed large rings over people. Neither path was rendered as a final video.

## Verification and remaining integration

Windows snapshot, one folder per run: `state` 371 passed and four initially failed because generated docs and expected action order were stale; after updating those, all affected tests passed in a 19-test targeted run, then 16 related tests passed again after the final stale-composition guard. `auto` 277 passed after the final guard; `editor` 534, `cli` 132, `ops` 565, `picks` 506, `draft` 650, `visual` 105, `compose` 42, `scorecard` 12, `music` 56, `export` 89 passed / 2 skipped, `identity` 108, `output` 81, `settings` 44, `script` 384 passed / 7 skipped, `voice` 108 passed / 1 skipped, `title` 198, `library` 163, `longjob` 69 passed / 1 skipped, `clean_text` 62, and `engine -m 'not slow'` 859 passed / 14 skipped / 168 deselected. All listed reachable folders were run. Generator checks for `bti.cli.docgen`, `bti.ops.doc`, and `bti.editor.hints` passed. `bash -n` passed for the deploy script. The Mac Node suite passed 507 tests and skipped one worktree-dependent check; no JavaScript changed, and the skipped code-list test was read and no new issue code was introduced.

Two existing `media` privacy tests failed (458 passed): `test_the_client_string_is_written_once_in_the_code` and `test_no_module_that_calls_an_outside_service_names_the_project_the_owner_or_the_repository`, both identify `bti/music/fetch.py:25`. One existing `fsio` test failed (8 passed): `test_no_bare_rename_is_left_in_bti` identifies `bti/media/sources/web.py:302`. These files were outside this change; the other worker independently observed the same failures.

The deploy preflight refuses running jobs by name before push and under the deploy lock; job registries reject new starts while that lock is held, unless the operator explicitly forces deployment. No deployment or restart was performed. The already-running old server must load the new guard before it can enforce its side of this protocol.

The real-data gate is blocked by the supplied invalid visual script. The review2 edit/review modules and their marked action-spec block also need integration into this worktree before a real visual run. The review2 edit worker calls post-compose itself while the store now also composes; its integration should avoid duplicate composition and scoring. These constraints cannot be resolved by inventing source content or calling a model in this task.
