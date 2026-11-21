# C2 box: the prompt box works through typed operations, on step 5 and on step 4

Worker `c2box`, 2026-11-19, branch `wt/c2box`. Brief: `.scratch/agy_tasks/c2box/TASK.md`. Design: `docs/design/2026-11-18-agent-first-design.html`
("Ô gõ lệnh hoạt động thế nào", "Bước 5 mới", "An toàn và kiểm chứng"). Operations: `docs/OPS.md`, `docs/AGENT_API.md`.
No model was called by me or by any test: the mock provider with canned answers only.

## What was built

The model of the box no longer writes whole shots. It answers

```
{"status": "applied" | "cannot" | "escalate", "summary": "<one sentence for the owner>", "reason": "<cannot / escalate: what is missing, what to do>", "ops": [ ... ]}
```

and the server (1) checks the shape and the words, (2) dry-runs `ops` through `bti.ops` inside the owner's selection with the actor `agent:<model id>`,
(3) sends a refusal back to the model ONCE as its own error body (`code`, `detail`, `fix`, `retry`, `fields` with the path and the allowed values,
`op_index`), (4) applies the batch for real with the owner's request as its note, (5) records the turn with the batch id and the batch's own sentences.
Step 4 ("Chọn hình") has the same box. Both pages have "Lịch sử thay đổi". The slow path (an agent in a work folder) writes through the same door.

| New file | What |
|---|---|
| `bti/draft/boxops.py` | the whole turn: answer check, owner's language, dry run, repair, stale rule, apply; the refusals as Vietnamese sentences; `Backend` (the adapters of the batch routes over the same locks); the rows of a turn; `apply_deep` (the slow path as `replace_range` batches) |
| `bti/draft/fastedit.py` (rewritten) | the storyboard side: the scope, the briefing, `fast_edit` |
| `bti/draft/picksedit.py` | the pictures side: the scope of lines, the briefing, `picks_edit` |
| `bti/editor/boxroutes.py` | what the two boxes' routes share (enrich a thread with the change log, undo of a batch turn, frames from the log, the step 4 start and thread) |
| `skills/storyboard_edit/FAST.template.md` (rewritten), `skills/picks_edit/FAST.template.md` (new) | the briefings |
| `bti/editor/static/js/changeslist.js`, `changeslogic.js` | "Lịch sử thay đổi" (DOM, pure parts) |

Changed: `bti/draft/run.py` (fast branch, apply part, `make_picks_edit_parts`, `start_picks`, `deep_limits`), `thread.py` (turn fields), `bti/editor/draft_api.py` (thread,
undo, frames, resolve), `picks_api.py` (marked block: four routes), `state_api.py` (`picks.edit`), `hints.py` (three sentences), `promptedit.js` (both boxes),
`editlogic.js`, `labels.js` and `errmsg.js` (blocks marked `c2box`), `views/picks.js` (a column and about 25 lines), CSS (`edit.css`, `picks.css`, marked blocks).
`bti/ops/**` was NOT changed (no behaviour change, nothing to say).

## 1. The answer shape and the size of the briefing

Shape: as above. Extra top-level keys are ignored; `summary` is needed with `applied`, `reason` with `cannot` and `escalate`; at most 40 operations (more: the model is
told to answer `escalate`).

The briefing is the template plus parts generated from the code: the operations (each with its summary, its fields from the registry's JSON Schema, required ones marked,
a field description given once, and the registry's own example verbatim), the shots in scope with the narration said in each, the two neighbours, the narration words over
the range, the pictures with their regions, and a reduced catalogue. Measured by `tests/draft/measure_briefing.py` (characters; the fixture project of `tests/ops`
and the copy of the real `arnolfini`):

| Briefing | Characters |
|---|---|
| step 5, one shot (fixture) | 22,243 |
| step 5, two shots / a chapter of four / all (fixture, nine editable) | 23,782 / 25,812 / 30,495 |
| step 5, one shot (arnolfini copy) | 24,245 |
| step 5, twelve shots (arnolfini copy, 11 editable) | 35,287 |
| step 4, one line / all six lines (fixture) | 10,255 / 12,763 |

Where it goes for one shot (fixture): the fixed text of the template about 6.7 KB, the operations 4.3 KB, the catalogue 8.7 KB (2.9 KB for the techniques on the shot and the usual overlays, 5.4 KB for the one-line entries of the other treatments), the scope data 2.8 KB (5 KB on arnolfini).
The old
briefing carried the full catalogue of 85 techniques (every parameter) on every call. The reduced catalogue: techniques on the scope's shots (full), the core overlays (full),
the occasional overlays and the core base techniques (one line each), the explanatory devices ONLY when the request is about that kind of point (keywords of the request
decide, `fastedit.DEVICE_WORDS`), never the identity techniques, shorts-only or other-series ones. `tests/draft/test_box_briefing.py` pins the sizes
(26,000 / 28,000 / 32,000 / 36,000 characters for one, two, four and all shots of the fixture; 42,000 for twelve arnolfini shots).

What the model has to WRITE (what costs the time of a call): `tests/draft/measure_answer_size.py`: a ring made bigger 160 characters, a slower camera and a ring 417, a refusal 96,
twelve shots with a slower camera 2,409; one shot written whole in the old contract was 495 characters (12 shots: 5,940).
The server's own steps (`tests/draft/measure_fast_path.py`, fixture project, the server): briefing 0.002 s, dry run 0.012 s, batch 0.023 s, undo 0.04 s, about 0.25 s
in all on a cold process. **The time of a real model call was not measured (no model was called): the target "a few tens of seconds" is unproven.**

## 2. How a turn maps to a batch and to the card

| Turn field | Meaning |
|---|---|
| `doc` | `storyboard` (step 5) or `picks` (step 4); one thread file, two boxes, each box reads only its own turns |
| `batch` | the id in the change log (`projects/<pid>/changes/`); null for a turn made before this build, for `cannot`, `escalate`, a failure |
| `batch_changes` | the batch's `changes` verbatim (`target`, `time`, `what`): the Vietnamese sentences the card shows (overlays included) |
| `changes` (step 5) | one row per shot that differs between the log's two copies, with the batch's sentences as its `facts`, `before_id` and `after_id` (the frames use them) |
| `summary`, `summary_source`, `reason`, `repairs`, `limits` | the model's sentence when it is plain Vietnamese (else the batch's first sentence, `code`), the reason of `cannot`/`escalate`, 0 or 1, the slow path's bounds |

Card: the model's summary, then the sentences of the batch (step 5: under the changed shot with its Trước and Sau pictures, taken from the change log's copies; step 4: a list),
"Xem thử" (step 5), "Hoàn tác". "Hoàn tác" posts the same route as before (`POST /draft/edit/{turn}/undo`, and `POST /picks/edit/{turn}/undo` for step 4); for a turn with a batch it undoes
that batch (`bti.ops.runner.run_undo`, actor `human`): `undo_conflict` (something the batch changed was changed since, nothing is undone) and `undo_unavailable` (the copies were pruned) reach
the page as the operations' typed errors with their Vietnamese sentences (`STAGE_CODES.ops`); the thread tells the card whether the undo is possible (copies kept, not undone yet) and shows a batch
undone from the list of changes as `undone`. Turns made before this build (no batch) keep the older undo (stored storyboards of the turn, `force` dialog).
`cannot` writes nothing: status `no_change`, the reason as the card's sentence. `escalate`: status `escalate`, nothing written, the reason, and on step 5 the button "Làm kỹ hơn"
(it says "mất vài phút"); on step 4 the card says "Agent chọn hình chưa có" and has "Tìm hình bằng tay" (opens the search tab). A failure: the code of the last refusal and one plain sentence.

## 3. What the slow path writes now

The agent in a folder still produces specs that the compiler turns into a storyboard; `apply_deep` then reads the saved storyboard, runs `merge.merge_storyboard` (the three-way
merge that keeps what the owner saved meanwhile; a shot both sides changed is still `needs_choice`) and turns the difference between the saved storyboard and the merge into ONE batch:
one `replace_range` per maximal run of consecutive shots that differ (the shot itself or the time it covers), the shots of the merge over that time as the new shots (technique, anchor,
intent, note, slots, params, overlays). Same actor (`agent:<model id>`), same note (the request), same log, same undo; the first replaced shot's `transition_in` is kept, locked shots are
refused by the operation. `resolve` (overwrite) goes through the same function. A stale revision between the read and the write is retried once (read and merge again). The turn's card
rows come from the same facts as before ("Máy quay đi chậm hơn") with `before_id` and `after_id` (a replaced shot has a NEW id: `replace_range` makes new shots).
Limits found and stated on the card when the slow path starts (`turn.limits`, `deep_limits()`): the agent is stopped after 30 minutes of working (`AGENT_TIMEOUT_S`, the watchdog of
`providers/agy.py` and `claudecode.py`), sent back at most 2 times after its first answer (`max_repairs`), and a job part may not last over 35 minutes (`PART_LIMIT_SECONDS`); the owner can
press "Dừng" at any time. The card says all of it plus "mất vài phút".

## 4. Step 4's box

Scope: the selected narration lines (`{"beats": [...]}`), a chapter or all; default the line being looked at; "Chọn nhiều dòng" adds clicked lines. The model gets those lines' text, the neighbours,
the pictures with title, artist, regions and where each is used (`used_in`), and the picks operations without `import`; the whole-video operations (`set_main`, `set_region`, `remove_region`) are offered only
when the selection is the whole video (they are outside any scope for the server, so a scoped box would only be refused). It can rearrange, add and remove pictures and regions the project
already has. It cannot import, search or look: a request that needs a picture the project does not have, or someone to look at a picture, is `escalate` with the reason; until the pictures agent exists the
card says "Agent chọn hình chưa có" and offers the manual search. Routes beside the picks routes: `POST /api/projects/{pid}/picks/edit` (`instruction`, `scope`, `base_rev?`, `model?`), `GET .../picks/edit/thread`,
`DELETE .../picks/edit/thread`, `POST .../picks/edit/{turn}/undo`. The agent is the one of the step `picks` (role `picks`). The state answer lists `picks.edit` (fill `instruction`, `scope`; template with the picks revision).

## 5. Each earlier defect and the test that covers it

The defects are those of the real probes of 2026-11-18 (`docs/qa/FIX_A_core.md` 13.4).

| # | Defect | Gone because | Test |
|---|---|---|---|
| 1 | existing overlays of a returned shot were reported as changed (probes 2 and 3) | the card shows what the batch changed; an operation touches only what it names | `test_box_storyboard.py::test_the_card_shows_the_batch_sentences_for_the_changed_shot_only` (one shot, one sentence, the other overlay byte-identical) |
| 2 | a `cannot` whose reason was English lost its content (probe 6b) | the reason is checked in the owner's language, sent back once, and an English one that stays is kept under "chi tiết" | `test_a_cannot_with_an_english_reason_is_sent_back_once_and_never_shown_in_english`, `test_a_reason_that_stays_english_is_replaced_by_a_fixed_sentence_and_kept_under_details`; Node `a reason in English is never the headline` |
| 3 | the model's own sentences never passed the check (English), so every sentence was code-made | the briefing asks for the owner's language; a `summary` that fails is replaced by the batch's own sentence and says `summary_source: code` (no second call for a sentence) | `test_an_english_summary_for_a_vietnamese_owner_is_replaced_by_the_batch_sentence`, `test_a_normal_answer_is_one_batch...` (`summary_source` model), `test_an_owner_who_writes_english_gets_english_sentences` |
| 4 | region labels were English in the facts | **only in part**: the briefing tells the model to speak of a region in the owner's language and the card leads with the model's Vietnamese summary; the batch's sentences for a region still use the project's own label (project data, not translated) | `test_the_pictures_with_their_regions_and_the_other_pictures_are_listed`, `test_the_rules_are_in_the_briefing`; the English label under a Vietnamese sentence is NOT fixed |
| 5 | the slow path ran 8 minutes and 750,000 input tokens for one small edit, then 21 minutes without an end | the owner now chooses it by a button that says "mất vài phút", the card states 30 minutes, 2 repairs, "Dừng"; the 30-minute watchdog exists and is stated | `test_f_deep_one_chapter_with_the_fake_agy` (`limits`), Node `the slower way states its limits`, `test_the_button_of_an_escalated_turn_starts_the_slow_path...` (**the cost in tokens and the stall itself were not reproduced or changed**) |

Also kept from the earlier rounds and re-tested here: the owner's own save is not the turn's change (`test_an_owner_save_of_another_shot_while_the_agent_worked_stays_and_undo_leaves_it`,
the stale tests), undo restores only the batch's things, nothing outside the selection or locked is ever written (`test_refused_twice...`, `test_a_locked_shot...`).

## 6. Decisions where the brief was silent

1. **What the box offers.** Storyboard: every operation except `lock`, `unlock` (a lock is the owner's own decision) and `replace_range` (the slow path's tool; big schema). Picks: every operation except `import`; a scoped box also not `set_main`, `set_region`, `remove_region`. An operation the box does not offer is refused as `unknown_op` before the dry run (the same sentence a repair gets).
2. **The scope sent to the server** is the owner's selection with the locked shots IN it (so the server answers `locked`, naming the shot, instead of `out_of_scope`); cards (title, chapter marks, text cards) are left out so the box cannot touch them. Chapter and whole video become the list of those shots; whole video on step 4 is no scope at all.
3. **What costs a repair call and what does not.** A wrong shape, an operation the server refuses, a `reason` not in the owner's language: one repair call. A `summary` that is not fit: no call, the batch's sentence is used. Second failure: the turn fails with the code of the last refusal.
4. **The owner's language**: Vietnamese unless the request is plain English (no diacritics, English function words and no Vietnamese ones). An owner who types Vietnamese without marks still gets Vietnamese. An English request gets English sentences from the model (the sentences of the batch stay Vietnamese).
5. **Stale revision.** The model answered for the document it was shown. If the scope's shots are not what it saw when the dry run starts, the turn fails ("Storyboard đã đổi trong lúc agent làm việc"). A stale revision between the dry run and the write is retried once on the new revision when the scope's shots did not change, else the same failure.
6. **`escalate` never starts the slow path by itself**, not even with `mode: "auto"` (the old behaviour); it is a turn status with a button. `mode: "auto"` still chooses the slow path directly for more than 12 shots. The 12-shot limit is kept.
7. **One thread, two boxes**: turns have `doc`; `GET /draft/thread` and `DELETE /draft/thread` act on storyboard turns only, the picks routes on picks turns only. A job of the box is of kind `draft` (one agent call at a time); its record has `meta.doc`.
8. **The slow path's regions.** The operations have no storyboard region operation, so a region the agent added to a picture is written first, under the storyboard lock, outside the batch (an undo leaves it, a region nobody uses). **Needs another worker** (see below).
9. **A replaced shot gets a new id** (`replace_range`), so the slow path's card maps before and after by `before_id` / `after_id`; the first replaced shot's `transition_in` is kept, the others get none (the operation has no such field).
10. **State answer**: only the action `picks.edit` was added; `changes.undo` still names the ONE newest batch that can be undone, so the list shows "Hoàn tác" on that row only (the brief said "when the state answer says it can be undone"). A per-document target would need a new key in the state answer, which the hand-written example of `docs/AGENT_API.md` would have to follow.
11. **The page**: step 4 has a fourth column (`pk-box`), `min-width` of the page 980 → 1280 px; the list of changes is a closed `details` under the thread of each box (30 newest of its document). Another worker restyles both later.
12. **`prompt_edit.mjs`**, the previous browser check of the box, describes the earlier contract (conflict dialogs, `force`, needs_choice on the fast path): marked superseded in its header, not ported, not re-run. Its launcher's canned answer (`launch.py`) and `launch_agent.py`'s now come from `tests/e2e/stages/box_mock.py`.
13. **Tests removed or rewritten** (all of the old fast contract): the old `test_fastedit.py` (now the pure parts), the fast-path tests of `test_edit_routes_e2e.py` (now `test_box_storyboard.py`, `test_box_slow.py`; the file keeps the plumbing, the quota, the tampering guard and the deep path), the part of `test_explainers_briefing.py` and `test_identity_catalogue.py` that read the old template's wording, `measure_fast_path.py` and `measure_answer_size.py`.

## 7. Tests

New test files: `tests/draft/test_box_storyboard.py` (23: a normal answer as one batch with the request as its note, a wrong operation repaired on the second try, a dry-run refusal with `code`/`fix`/`fields` sent back, refused twice, out of scope, a locked shot, `lock`/`unlock`/`replace_range` not accepted, `cannot` with its reason, an English reason sent back once, an English reason that stays, an English owner, an English summary replaced, `escalate`, a save of another shot while the model thinks, a change of the selected shot while it thinks, a stale revision between the dry run and the write with BOTH outcomes, undo through the card's route, undo conflict, undo unavailable, a batch undone from the list, the frames from the log, a chapter scope), `test_box_slow.py` (14: `replace_ops` on small documents, the owner's save kept, needs_choice, overwrite as one batch, discard, the button of an escalated turn, a refusal of the operations), `test_box_briefing.py` (18: the generated schemas, a change of the registry reaches the briefing, only the scope's shots and the two neighbours, locked shot shown, pictures and regions, the reduced catalogue, a device only when asked, the rules, the language, the thread, the sizes, the real arnolfini copy), `tests/picks/test_box_picks.py` (14: rearranging, add and remove, a new picture escalates, `import` not offered, whole-video operations only for the whole video, a region, out of scope, repair, no change, undo and its conflict, separate threads, refusals of the routes with `code`/`fix`/`retry`, busy, the briefing), `tests/editor/test_box_routes.py` (7: the page's files served, the body the page sends today, a stale `base_rev`, an older turn keeps its undo, a turn without copies, the threads do not mix, a batch undone from the list), `tests/state/test_ops_state.py` (4 added: both boxes in the state answer with a template the route takes, not ready while a job runs, the refusals of the step 4 routes, the log and `changes.undo`), `tests/editor_frontend/editlogic.test.mjs` (10 added: every outcome of the card for both boxes, escalate, limits, no empty card, no English, the errors, the scope of the pictures box) and `changeslist.test.mjs` (5). Rewritten: `test_fastedit.py` (the pure parts, 25). Adapted: `test_edit_routes_e2e.py`, `test_agent_choice.py`, `test_claude_runner.py`, `test_explainers_briefing.py`, `test_identity_catalogue.py`, `tests/state/test_state.py` (`picks.edit` in the list of ids).

Python, on the Windows server (`BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh c2box [--no-sync] -- tests/<folder> -q`, snapshot `c2box`, one folder per run, no `-m slow`), the summary lines as printed:

| Folder | Last line |
|---|---|
| `tests/draft` | `400 passed, 1 warning in 152.33s (0:02:32)` |
| `tests/picks` | `106 passed, 1 warning in 17.38s` |
| `tests/ops` | `468 passed, 1 warning in 107.81s (0:01:47)` |
| `tests/state` | `237 passed, 1 warning in 139.84s (0:02:19)` |
| `tests/editor` | `488 passed, 1 warning in 240.92s (0:04:00)` |
| `tests/script` | `262 passed, 7 skipped in 36.66s` |

Node, on the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs`: `ℹ tests 357`, `ℹ pass 356`, `ℹ fail 0`, `ℹ skipped 1` (the one skipped is not mine: "every code in bti.engine.storyboard.ISSUE_CODES has a Vietnamese template", `# no .venv/bin/python`).
The one warning of each Python run is the existing `StarletteDeprecationWarning` of the test client. Nothing else was run on the Mac in Python except `python -m bti.editor.hints` (writes `docs/AGENT_API.md`), `python -m bti.ops.doc --check`, `py_compile` and `tests/draft/measure_answer_size.py` (no server, no model).

Browser probe, `BTI_SSH_HOST=winbox-cmd node tests/e2e/box/box.mjs` (a second instance of the app on the server with the mock agent, port 8571, folder suffix `c2box`, stopped afterwards; headless Chrome on the Mac; a real project copy `arnolfini-live` for step 5 and `arnolfini-from-books` with a pasted narration and an imported main picture for step 4; `tests/e2e/stages/launch.py` with the canned answers of `tests/e2e/stages/box_mock.py`), last line as printed:

```
53 pass, 0 fail
```

It covers, on step 5: the box and the empty list, a request applied (one batch, the card's sentences, the Trước and Sau pictures loaded, "Xem thử" and "Hoàn tác", the saved storyboard changed and taken in, the log's note and actor), "Xem thử" opening a clip, the list with its row and its "Hoàn tác", the card's "Hoàn tác" putting the storyboard back exactly, a `cannot`, an `escalate` with the "Làm kỹ hơn" button, a refusal with one plain sentence and "Thử lại"; on step 4: the box, a request applied and taken in by the page, the list, the card's undo, an `escalate` with "Tìm hình bằng tay" opening the search, a refusal; and "no leftovers, no raw words" after each. Four earlier runs failed on the probe's own mistakes (a card read before it was drawn, a form sent while the box was still busy with the previous turn, a narration too short to approve, a text compared without its uppercase form, a selector) and one was stopped by me while it waited for a narration generation by the mock model that never answered (the probe now pastes the narration); no failure was a defect of the page or the server.


## 8. What could not be verified

- **No real model was called.** Only a real model shows: whether it answers in the shape (and how often the repair is needed), whether its operations pass the dry run, whether its Vietnamese passes `describe.sentence_ok` (`summary_source` model or code), how long a call takes with a 22 KB briefing (the target is a few tens of seconds; unproven), whether it asks for `escalate` and `cannot` at the right moments (the examples in the briefings are the only guide), whether it respects "never guess a fact" and the explanatory-device rule, whether the keyword gate on the devices misses a way the owner says it (then the model answers `escalate` and the owner presses "Làm kỹ hơn").
- The slow path was run with the fake `agy` and the fake Claude Code programs only: the 30-minute watchdog, the repair loop and the cost in tokens are as the earlier probes left them.
- The operations' sentences contain the ids of technique parameters ("đổi thiết lập camera") because the registry has no Vietnamese names for parameters (a decision of `docs/qa/FIX_c1_ops.md`); the card shows them as the server wrote them.
- A browser run at 1280x720 of the new fourth column on step 4 was not made (the probe's screenshots are 1700x1000).

## Needs another worker

- `bti/ops`: an operation that adds or changes a region in the STORYBOARD document (today the slow path writes new regions outside the batch, so they are not in the change log and not undone); Vietnamese names for technique parameters (the sentences of `set_params` and `set_technique` say `rx, ry`, `camera`).
- `bti/editor/state_api.py` / `docs/AGENT_API.md`: a per-document target of the undo (`undoable: {picks, storyboard}`) so that each list shows "Hoàn tác" on its newest undoable batch even when the newest batch overall belongs to the other document.
- The pictures agent (another worker): when it exists, `escalate` on step 4 can start it; the card has the place (`actions.escalate === 'manual'`).
- `.gitignore`: `projects/*/changes/` (still from `FIX_c1_ops.md`).
