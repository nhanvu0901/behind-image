# FIX fixes4: what the first real run of the new picture rules showed (worker `fixes4`)

Brief: `.scratch/agy_tasks/fixes4/TASK.md`. Branch `wt/fixes4`, snapshot `fixes4`, 2026-11-20. No model, no paid request and no request to any outside service ran: every test uses the fakes, and the proofs read copies of the saved files of the
real run (project `eligius`) that were put into the snapshot's own folders (`proof_in`, `proof_in3`); nothing outside `D:\code\behind-the-image\run\snap-fixes4\` was written on the server. The four files of the worker `panelbox`
(`bti/media/assets.py`, `bti/draft/compile.py`, `bti/draft/zones.py`, `bti/identity/apply.py`) are untouched.

## 0. The five in one table

| # | what was found | what changed | the test that proves it |
|---|---|---|---|
| 1 | The write step sent the Commons API call, the rendition call and the file call of each picture back to back (no pacing on the import path; the only pacing, `pace_wikimedia`, was for the thumbnails of the search); `http` raised the first 429 at once (a wait over 5 s was never waited); and `download_all` then took that first refusal as "the whole source is closed for 60 s" and listed every later picture of the source as `import_limited` without asking | every download (`bti.media.api.import_candidate`: the write step, the operation `import`, `POST .../picks/import`) is polite (one request a second per host, Wikimedia counted as one) and patient (429 or 503 with Retry-After waited out: what it asks, else 10, 30, 90 s, three times); the write step closes a source only after a picture is still refused after those tries | `tests/media/test_polite_downloads.py` (20), `tests/picks/test_auto_job.py` (4 new), `tests/picks/test_size_repair.py` (1 changed) |
| 2 | six chosen pictures lost, finished by hand | new action `picks.retry_missing` (`bti/picks/auto/retry.py`, route, state answer, run loop) | `tests/picks/test_auto_retry.py` (16), `test_auto_retry_api.py` (7), `tests/auto/test_run_retry.py` (4); the proof on the real saved files (section 3) |
| 3 | `outside_on_painting` flagged b0011 (42%), b0058 (28%), b0035 (48%) | 45% for one kind, 25% for two kinds, at least 3.5 s | `tests/engine/test_viewchecks_kinds.py`; the proof on the real storyboard (section 4) |
| 4 | the model read the kind, looked at AN-03 (`defaults.cmd AN-03 ... --region SHELVES`) and chose a camera move; its reason repeats two sentences of ours | the parenthetical "(the finished video used only a camera move here)" is gone from the AN-03 example | `tests/engine/test_catalogue_registry.py` (1 new) |
| 5 | the draft workspace had no `picks.json`; the typed operations let an agent name any technique | `picks.json` in the workspace; `technique_not_offered` in the operations, by the actor | `tests/draft/test_workspace.py` (2 new), `tests/ops/test_sb_ops.py` (10 new, 2 adapted) |

## 1. Polite and patient downloads

### Why the present limiter did not prevent it (from the code, and from the saved files)

1. **There was no pacing on the import path.** `bti.picks.auto.search.pace_wikimedia` (one request a second) was called only for the thumbnails of the search part, and only for `upload.wikimedia.org`. A Commons import
   (`bti.media.api.import_candidate`) sends `fetch_meta` (API, `commons.wikimedia.org`), for a picture of 1920 px or more `_rendition_url` (API again) and the file (`upload.wikimedia.org`): two or three requests to the same service
   in the same instant, picture after picture. In the real run the five Commons pictures before b0025 went through; the sixth (b0025.1) is the first that was refused (the transcript of the write part is not kept, so which of its requests got the 429 is not known).
2. **`bti.media.http` raised the first refusal at once.** A 429 with a `Retry-After` of at most 5 s was waited and tried once; any other 429 (no time, or longer) raised `MediaHTTPError(rate_limited)` without a second try. `_COOLDOWN` is per host name and is
   set only when the host gave a time, so the API host and the file host never held each other back.
3. **`bti.picks.auto.write.download_all` turned that one refusal into "this source is closed for `retry_after` or 60 s"** (`wait_until[src]`), and every later picture of the source inside that time was written as `import_limited` *without a request*. The
   saved files show exactly that: of the 26 pictures the agent chose, the Commons ones in plan order are b0011.2, b0012.1, b0013.1, b0014.1, b0020.1 (downloaded), then **b0025.1, b0029.1, b0035.1, b0042.1, b0051.1, b0055.1** (all lost: the first
   was refused, the others were never asked); every picture of another source after b0025 (Pexels, the Met, the web, OpenStreetMap) was downloaded. All six say "Thử lại sau khoảng 1 phút" (the default wait of 60 s, no time given). The write step never
   sleeps, so nothing was ever tried again: the coordinator's by-hand batches, 25 seconds apart, worked at once.

### What changed

- `bti/media/http.py`: `polite()` (a context: every `open_url` request inside it is paced and patient), `pace(url)` (at least `PACE_INTERVAL` = 1 s after the last request to the same host, the lock held while waiting; **all Wikimedia hosts**
  (`*.wikimedia.org`, `*.wikipedia.org`) **are one key**, because they are one service with one rule), `hasty()` (inside `polite()`: do not wait for this request, it has a way round), the patience in `open_url`: a 429, or a 503 that carries `Retry-After`, is
  waited out (the time it asks, else `PATIENT_WAITS` = 10, 30, 90 s) and the same request sent again, **three times**; a time over `PATIENT_MAX_WAIT` = 120 s is not waited for (the error carries it at once, as before); a patient wait is not one of the
  `tries` of the 5xx backoff; a host cooldown of at most 120 s is waited out instead of refused. Outside `polite()` nothing changes: a search still fails at once and says when to come back (the 19 old tests of `test_http.py` pass untouched).
- `bti/media/api.py`: `import_candidate` runs inside `polite()`. That one function is what the write step (`psvc.fetch_asset`), the typed operation `import` (`PicksAdapter.prefetch`), the route `POST .../picks/import` (`import_asset`), the older import of the storyboard
  page (`bti/editor/app.py`, `media_adapter`) and `python -m bti.media` all call, so every place the app downloads a picture is covered, not only the three named.
- `bti/media/sources/commons.py`: an original that is refused when a rendition can be had instead (`_fallback_width`, new, the same rule as before) is asked under `hasty()`: the rendition takes its place at once, without waiting 130 s for the original first.
- `bti/picks/auto/search.py`: `pace_wikimedia` now uses `http.pace` (one clock for the thumbnails and the downloads).
- `bti/picks/auto/write.py` `download_all`: a source is **closed for the rest of the write part** once one of its pictures is still refused after those tries (the others are listed `import_limited`, with the wait the host asked, without a request). Nothing sleeps here: the
  waiting is inside the download.
- **How long the write step may now take.** A Commons picture is 3 requests, so 3 s at the least apart plus its transfer: 60 pictures (the plan's cap) is about 6 minutes. The patience of the one picture that happens to be refused is 130 s (no time given) to 6
  minutes (a host that says 120 s three times), and after it the source is closed, so it happens once per source. With the batches that is about 15 minutes in the worst honest case. **The limit stays at 25 minutes** (`WRITE_SECONDS`, comment in `write.py`):
  the deadline is looked at before each download, the long-job manager stops a part at 35 minutes, and 25 + 6 (the download under way) + the batches fits where 30 would not. **The estimate** (`EST_SECONDS["write"]`) goes from 120 to 300 seconds (about 25 pictures
  at 3 requests each and their transfer, then the batches). The `GET .../picks/auto` answer still says `write_seconds` 1500.
- A command that sends an `import` can now wait up to about six minutes: `docs/AGENT_API.md`, `skills/picks/SKILL.md` and the summary of the operation `import` (so `docs/OPS.md`) say `--timeout 300` (the default of `bti` is 60 s).

### Tests

- `tests/media/test_polite_downloads.py` (20): the pacing (a second apart, other hosts free, all Wikimedia hosts one clock), 429 without a time waited 10, 30, 90 s, with a time exactly that time, a 503 with Retry-After the same and a 503 without a time not, the refusal after the
  three tries (with the host's last time, or none), more than two minutes not waited for, a patient wait that does not use the 5xx tries, a polite request that waits out a short cooldown and refuses a long one, `hasty`, nothing left behind by a refused download; and through the
  real import: **a fake Wikimedia that answers 429 when two requests come less than a second apart** (as the real one did) gives six Commons imports in a row with no refusal (gaps of at least a second), while the unpaced client is refused; a refused file is waited for and imported; a refused
  original with a rendition to fall back on is not waited for.
- `tests/picks/test_auto_job.py` (4 new): a picture refused after the tries closes its source (the second Commons picture is not asked, another source is), the wait said for both lines (75 s: "khoảng 2 phút"; none: "khoảng 1 phút"), nothing missing when nothing is refused, and the limit and the estimate against the manager's 35 minutes.
- `tests/picks/test_size_repair.py`: `test_import_answers_429_without_a_time_with_a_null_wait` now sees 4 requests (1 + 3 tries) instead of 1; `tests/picks/test_auto_search.py` resets the shared pacing clock.

## 2. `picks.retry_missing`

`bti/picks/auto/retry.py` (new), route `POST /api/projects/{pid}/picks/retry-missing` (`bti/editor/picks_api.py`), `Spec` + `b_picks_retry_missing` + need `picks_saved_files` (`bti/editor/state_api.py`), codes `retry_nothing_to_do` and `retry_no_files` (`texts.py`, `hints.py`, `errmsg.js`),
the Vietnamese sentence of the result (`texts.retry_sentence`), `store.FILES` has `retry.json`.

- **A long job** (kind `picks`, `meta.action` `retry`, one part), no model, no cost (`cost` null: a download, like `picks.import`), no search. Body `{"beats": [..] | null, "actor": ..}`; `bti do <project> picks.retry_missing --wait`.
- **Listed** only while a line of `picks.json` has `missing` with the code `import_limited` (`web_budget` is not retried: it was a search that was not made). **Ready** when `cache/picks_auto/{plan,search,choice}.json` are there (else the need `picks_saved_files`), the narration is approved,
  there is a main painting and no agent job runs. **Advances** for the lines it has not looked at since the last run of `picks.auto` (`cache/picks_auto/retry.json`, which a new run forgets), so the automatic run takes it **once**, between `picks.auto` and the gate
  (it is placed before `picks.approve` in the catalogue; `tests/auto/test_run_retry.py` shows `picks.auto`, `picks.retry_missing`, `picks.approve` and, when the source keeps refusing, one try and then the gate's own rule).
- **What it does for each line:** the candidate comes from `merge_choice(choice.json, choice2.json, search.json)`, the very merge the write part used (`pick` `["c", n]`: candidate n of the want; for a pick of the second choice n counts inside `round2.map[want]`; `["b", n]`: a picture of the books);
  the picture is imported (polite and patient); the line is written again with the write part's own functions (`build_lines`, `_ops_for`, `line_note`): **the plan's pictures in the plan's order** (the picture with the agent's reason as its note; where the plan put it, which in the six lines is first), `kinds`, `missing` without what it fixed (another
  picture of the line that is still missing keeps its own code), the line's note without "Chưa tìm được ...", **one batch of the change log per line** (note "Tải lại hình đã chọn: đoạn b0025", the actor the caller names, undoable).
- **A line that is not as the write part left it is left alone** (`line_changed`): the items of the line must equal what `build_lines` gives for the state the saved files and the line's `missing` describe; a line the owner (or an operation) changed meanwhile, which keeps its `missing` (an edit keeps it unless it sends new ones), would otherwise be overwritten.
  A line still refused stays as it was and is listed (`lines_still_limited`, with the wait). The result: `lines_total`, `lines_fixed`, `lines_still_limited`, `lines_left`, `pictures_imported`, `batches`, `sentence` ("Đã tải lại hình cho 5/6 đoạn. 1 chỗ vẫn bị giới hạn lượt tải, thử lại sau.").
- Refusals: `retry_nothing_to_do` (409), `retry_no_files` (409), `invalid_field` (422), `agent_job_running` / `busy` (409). While it runs `picks.auto` is not ready (`no_running_job`) and is refused (`busy`).

### Tests

`tests/picks/test_auto_retry.py` (16): the result equals what an unrefused run writes (the same notes, kinds, items in the same order, no `missing`, against a second project run without refusals), the picture's place, one undoable batch per line, `retry.json` and the reset, a line still refused (nothing written),
the second source not asked after a refusal, only the line that could be had written, a changed line left alone and its picture not even downloaded, `web_budget` not retried, every refusal, `beats`, the job holding the project, and the second choice read as the write part reads it (a
hand-made plan: pick 2 of the second session is candidate 5 through `round2.map`). `tests/picks/test_auto_retry_api.py` (7): the state answer (listed only with a line that says it, ready, advances, before the gate, the need), the route and its refusals, a still-refused line not offered to the run a second time, the job holding `picks.auto`.
`tests/auto/test_run_retry.py` (4): the run takes it once before the gate; a source that keeps refusing is tried once, then the gate's rule stops it; never listed when nothing was refused; no spend needed.

## 3. Proof of point 2 on the real saved files (read-only)

`tests/e2e/picks_auto/retry_proof.py`, run in the snapshot (`tools/deploy/snapshot_py.sh fixes4 tests/e2e/picks_auto/retry_proof.py proof_in`). Inputs: copies of `choice.json`, `choice2.json`, `plan.json`, `search.json`, `last.json`, the narration and the outline of `eligius` and its present `picks.json` (used
only to compare a result, never as the start). The start is a project of the proof's own with the real narration and a picks document of the main painting only (with the regions it had before that run). Full output: `.scratch/fixes4/proof_retry_output.txt` in the worktree.

1. **The write part from the saved files reproduces the real run:** 61 lines written, 20 pictures imported, and the `missing` list equal to `last.json`'s (15 entries) when the six pictures the real run lost (read from `last.json`: `b0025.1 b0029.1 b0035.1 b0042.1 b0051.1 b0055.1`) are refused with "too many requests".
2. `picks.retry_missing` then runs with the source giving its pictures (fake files, no network). The state answer says: lines `b0025 b0029 b0035 b0042 b0051 b0055`, saved files there, none looked at yet. Result: `Đã tải lại hình cho 6/6 đoạn.`, 6 pictures, 6 batches. **The candidate it downloads for each line** (the answer is not given to the code: it is read from the files):

```text
OK   b0029  File:Philipp the Good - Van der Weyden.jpg   [choice2.json pick ['c', 5] -> round2.map[b0029.1][4] = candidate 10]
OK   b0035  File:Charles the Bold 1460.jpg                [choice.json pick ['c', 1]]
OK   b0051  File:Portrait of a Man by Jan van Eyck.jpg    [choice2.json pick ['c', 3] -> round2.map[b0051.1][2] = candidate 8]
OK   b0042  File:The Arnolfini Portrait, détail (2).jpg   [choice2.json pick ['c', 7] -> round2.map[b0042.1][6] = candidate 12]
OK   b0025  File:Jacques de Guise, Chroniques de Hainaut, frontispiece, KBR 9242 (cropped).jpg   [choice2.json pick ['c', 1] -> round2.map[b0025.1][0] = candidate 6]
OK   b0055  File:Pluenderung Grandson.jpg                 [choice2.json pick ['c', 4] -> round2.map[b0055.1][3] = candidate 10]
```

   These are the six of the brief, and five of the six come through the second choice (`choice2.json`), the case the mapping through `round2.map` is for; reading `choice2.json`'s numbers as the want's own numbers would have taken candidate 5 of b0029 (a Met picture) instead of 10.
3. **The lines as written against the real `picks.json` after the coordinator's hand-made batches:** the same pictures in the same order for all six (b0025: the Chroniques de Hainaut page, then the detail COUPLE; b0051: the portrait, then the manuscript page), nothing missing, the plan's reason as the line's note
   (without "Chưa tìm được"), the agent's own reason as the note of the new picture. The 55 other lines are unchanged. `lines with missing after the retry`: b0007, b0008, b0016, b0021, b0026, b0028, b0030, b0031, b0046 (`agent_none`: the agent chose nothing for them; not this action's).

## 4. `outside_on_painting`

`bti/engine/viewchecks.py` (`OUTSIDE_ON_PAINTING_SHARE` 0.45, `OUTSIDE_ON_PAINTING_SHARE_TWO` 0.25, `OUTSIDE_ON_PAINTING_MIN_SECONDS` 3.5, `outside_needed(kinds, dur)`): a line of kind `outside` needs its outside picture for **45% of its length with one kind, 25% with two, and in both cases 3.5 seconds at
the least; a line shorter than 3.5 s needs it for all of the line** (decision: a line of 3 s can never hold 3.5 s, so the floor is capped at the line). The issue's `args` now carry `limit` (the share this line needs), `min_seconds` and `needed_seconds`, and its message says what the line needs.
The sentence of the storyboard draft template (rule 19 of `skills/storyboard_draft/TASK.template.md`), the row of `skills/storyboard/SKILL.md`, the reason of the automatic run (`bti/auto_run/checks.py`, so `docs/AGENT_API.md`), the hint of the check and the page's sentence (`errmsg.js`, a block at the end: it says what the line needs) say the same. Tests: `tests/engine/test_viewchecks_kinds.py`
(the one-kind edge at 8.9 / 9.0 s of 20, the two-kinds edge at 4.9 / 5.0, the order of the two kinds, the table of `outside_needed`, the 3.5 s floor on a beat of 8 s).

**Proof on the real storyboard** (`tests/engine/outside_real_proof.py`, copies of `storyboard.json`, `timing.json`, `picks.json` of `eligius`; output `.scratch/fixes4/proof_outside_output.txt`):

```text
OLD rule (half of the line): 3 line(s) flagged
   b0011 kinds detail,outside     line 11.7 s, picture on 4.9 s = 42%   (needs 50% and 0.0 s = 5.8 s)
   b0035 kinds outside            line 13.1 s, picture on 6.3 s = 48%   (needs 50% and 0.0 s = 6.5 s)
   b0058 kinds whole,outside      line 14.1 s, picture on 3.9 s = 28%   (needs 50% and 0.0 s = 7.1 s)
NEW rule (45% / 25% / 3.5 s): 0 line(s) flagged
```

## 5. Why the storyboard model did not use the perspective lines on b0043

Read from the saved files of the draft (`cache/draft/20261120-070804/`: `events.jsonl` (the transcript, 562 events), `out/c07.json`, `out/notes.md`; the proposal `draft_20261120-070804`). The model's thinking blocks are empty in the transcript; its words are in its notes and its last message.

- **Did it read the kind?** Yes: its notes say "b0043 (perspective, kind construction)". It read `inputs/techniques.md` (the new catalogue: the transcript's header line is the new generator's, and the file is 55 KB, the new size; the old one was 81 KB) and `inputs/beats.json`, and its notes cite rules 20 and 21, which exist only in the new template.
- **Did it consider AN-03?** Yes: event 393, after writing c06 and before c07, it ran `./defaults.cmd AN-03 --asset goldsmith_his_shop_3bc1 --region SHELVES` ("Show defaults for perspective rays and ring"). The answer gave the registry line (`vanishing_point:point*`, `origins:points`, `intents: explain_mechanism, point_at`) and defaults
  that are placeholders, not measurements: `vanishing_point [1734.5, 1560.0]` (the middle of the picture) and nine `origins` at the frame's edges.
- **Did something refuse it?** No. It never wrote AN-03, so no check ran on it (the check ended with 0 errors), `technique_not_offered` never appeared (the transcript has no such word), and the coordinates were not missing (the defaults printed values).
- **What it wrote for the line:** `s0080` in `c07.json`: `CAM-01`, intent `explain_mechanism`, on the region `SHELVES`, a slow push-in (zoom 0.85 to 0.92), no overlay, note "the shelves whose angles do not obey the new perspective".
- **The model's own words** (`out/notes.md`, and its final message):
  - "b0043 (perspective, kind construction): there is no AN-03. I could not trace shelf edges in the picture that clearly meet or clearly fail to meet, and invented rays would be decoration. A camera move on the shelves serves this line, **as it did in the finished reference video**."
  - "s0080 (shelves, c07) is a plain push-in: a candidate for a hand-drawn AN-03 if the owner wants one."
  - final message: "**No perspective lines (b0043):** I couldn't trace shelf edges that clearly meet or fail to meet, so the line about perspective gets a camera move instead."
- **The cause is two sentences of ours it repeated.** (a) The `example` of AN-03 in the catalogue ended "(the finished video used only a camera move here)": the model's "as it did in the finished reference video" is that sentence, and it names the answer the technique is there to replace.
  (b) The `needs` of AN-03: "The edges the lines follow, taken from the picture itself ... The picture must show those edges", with the techniques.md paragraph "use one only where its text fits the sentence, never as decoration ... none is fine; a camera move serves most sentences": the model's "invented rays would be decoration" is that rule applied.
  The `needs` sentence is a true requirement and the paragraph is the generator's (`bti/draft/techniques_md.py`, not mine), so **only (a) was changed**: the parenthetical is removed from the `example` of AN-03 in `style/gae/techniques.json` (the example is now the sentence of b0043 alone), and `test_an_example_never_tells_the_model_what_an_earlier_video_did_not_use` keeps
  it out (and every other offered example free of "used only" / "did not use"). Nothing in the template was changed for this point.
- **What I did not change and the coordinator may want to** (not in my files, or not plainly a sentence that told it not to): the draft's helpers give the model no way to measure edges (`defaults.cmd` fills `vanishing_point` and `origins` with the middle of the picture and the frame's edges: it cannot trace shelf edges, so a model that wants true rays must place them by eye and
  check with `still`; the five regions it measured by eye in the same run it checked with frames, so it could have done the same here); and the "none is fine" paragraph in `bti/draft/techniques_md.py` leans the model towards leaving a device out. A `crop --grid` helper for the draft workspace, and `needs` text that says "the origins are
  the edges as they lie, and rays that miss each other are the claim" would be the two steps.

## 6. The two things the catalogue worker left

- **`picks.json` in the draft workspace** (`bti/draft/workspace.py`): `<workspace>/picks.json` is the very picks document `inputs/compile_input.json` holds (its assets pointing at the copies in `images/`, no path of the project), written in `build()` for every mode. The viewer checks look for `picks.json` beside the storyboard's project folder
  (`viewchecks._picks_doc`), and the workspace is that folder for the model's `./check`; without the file the checks that read the kinds were silent there and only ran on the server. `tests/draft/test_workspace.py` (2 new): with `kinds` on the line the agent's own `check` prints `warning device_wrong_kind: chapter c02, shot 2 (LAY-01)` and the project's compile says the same; without `kinds` they stay silent.
- **`technique_not_offered` in the typed operations** (`bti/ops/sb_ops.py` `_tech`, `bti/ops/errors.py`, `errmsg.js`, `hints.py`): the route tells a person from an agent by the **actor** (`Ctx.source` is `human` for the actor `human`, the page; every other actor, `agent:<model id>`, `cli:<name>`, `agent:auto`, is an agent).
  A batch of an agent that **names** a technique the registry hides (`offered` false: `set_technique`, `add_overlay`, `set_overlay` with a new technique, `replace_range` shots, except for the techniques of the run it replaces: see section 8) is refused 422 `technique_not_offered` before anything is written, with the text of the draft's own error (`not_offered_text`: why, and "Use X instead."), `technique`, `use` (the offered
  techniques that replace it), and `fields[].allowed` (the offered ones of the right kind). A batch of a person may use any technique. **A technique the shot or the overlay already has is never refused** (`set_params`, `set_slot`, `set_technique` / `set_overlay` to the same technique): the stored storyboards use hidden ones. The prompt box's own
  pre-check (`bti/draft/boxops.py`, the catalogue worker's) keeps its code `unknown_technique`; it is not mine to change. Two old tests that took the first available technique with a parameter (`test_set_technique_lists_what_is_allowed`, `test_set_overlay_technique_takes_new_defaults`) now take the first *offered* one; the rest of `tests/ops` passed untouched.

## 7. Decisions where the brief was silent

1. The polite client is in `bti.media.api.import_candidate`, not only in the three named places: the older storyboard import and the media CLI use it too. Wikimedia's hosts are one pacing key. A wait over 120 s is not waited for (the coordinator's "wait what it asks" has to stop somewhere); a host cooldown of at most 120 s is waited out in a download.
2. After the three tries the write step closes the source for the rest of its part (it used to close it for the wait the host gave, or 60 s). The limit stays 25 minutes; the estimate is 300 s (section 1).
3. `picks.retry_missing` has no cost (a download is like `picks.import`), so the run needs no spend for it; it is not an agent job (it is of kind `picks` with `meta.action` `retry`, and it refuses to start while the pictures agent, a prompt-box turn, a draft, the title writer or another run works).
4. It writes the lines in the plan's order of pictures, not "the retried picture first" (the same for the six lines, which is what the brief's description fits); it leaves a line the owner changed; it writes even when the picks are approved (the write drops the approval, as every edit does).
5. `outside_on_painting`: the floor of 3.5 s is capped at the length of the line; "two kinds" is `len(kinds) >= 2` (a line has at most two).
6. Point 4: only the AN-03 example was changed (section 5).
7. `technique_not_offered` is decided by the actor (`human` or not), and not by the route; a technique already on the shot or overlay is never refused, and a `replace_range` may name again every technique of the run it replaces (the deep edit of the prompt box needs it).
8. The snapshot `D:\code\behind-the-image\run\snap-fixes4\` keeps `proof_in`, `proof_in3` (read-only copies of the real project's files) and `proof_out`; I did not remove it (the coordinator may want to look: `tools/deploy/snapshot_rm.sh fixes4`).

## 8. Tests (snapshot `fixes4`, server; summary lines exactly as printed)

One folder per run, `-m "not slow"` for `tests/engine`, snapshot `fixes4`, `BTI_NO_REAL_MODELS=1`. **Where a folder is given as slices**, the link to the server dropped a run that lasted about two minutes ("Read from remote host ... Operation timed out", three times, and
a sync stalled for half an hour twice), so the folder was run as several runs of its files, which together are the whole folder (the file lists are in `.scratch/agy_tasks/fixes4/STATUS.md` order: alphabetical); the sum is given. Summary lines exactly as printed:

```text
tests/picks   387 passed, 1 warning in 104.61s (0:01:44)
tests/media   425 passed in 3.88s
tests/ops     slice 1 (test_sb_ops.py)                     225 passed, 1 warning in 53.35s
              slice 2 (the other five files)               279 passed, 1 warning in 58.02s         = 504 passed
tests/draft   slice 1 (test_agent_choice ... test_box_storyboard)           113 passed, 1 warning in 54.16s
              slice 2 (test_catalogue_compile ... test_edit)              160 passed, 1 warning in 66.75s (0:01:06)
              slice 3 (test_edit_routes_e2e ... test_identity_compile)    130 passed, 1 warning in 25.53s
              slice 4 (test_intro_flow ... test_workspace)                 83 passed in 19.41s                = 486 passed
tests/engine  737 passed, 14 skipped, 166 deselected in 359.15s (0:05:59)        (-m "not slow"; run before the last change of bti/ops/sb_ops.py, which the engine does not use)
tests/auto    234 passed, 1 warning in 103.25s (0:01:43)
tests/state   slice 1 (test_auto, test_docs, test_errors, test_ops_state)  93 passed, 1 warning in 30.27s
              slice 2 (test_retime_state, test_state)                      227 passed, 1 warning in 154.96s (0:02:34)     = 320 passed
tests/editor  slice 1 (test_agent_routes ... test_identity_route)          272 passed, 1 warning in 141.05s (0:02:21)
              slice 2 (test_integration_real ... test_proposals)           82 passed, 1 warning in 22.60s
              slice 3 (test_retime_route ... test_shell_static)           175 passed, 1 warning in 94.36s (0:01:34)     = 529 passed
tests/cli     131 passed, 1 warning in 76.92s (0:01:16)
python -m bti.cli.docgen --check        exit 0
python -m bti.ops.doc --check           exit 0
python -m bti.editor.hints --check      exit 0
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs     (Mac)
    tests 491, pass 490, fail 0, skipped 1
node --check bti/editor/static/js/labels.js and errmsg.js    ok
```

**One regression of mine, found by the whole-folder run of `tests/draft` (15 failures) and fixed.** The deep edit of the prompt box (`bti.draft.boxops.apply_deep`) puts the merged storyboard back as ONE `replace_range` whose actor is the agent and which names every technique again,
the stored hidden ones included; the new `technique_not_offered` refused it (the box showed "Agent trả lời chưa đúng cách ..."). `replace_range` now treats the techniques of the run it replaces (the shots' own and their overlays') as existing, like `set_params` and `set_technique` to
the same technique; only a new hidden technique is refused (`test_a_replace_range_keeps_the_hidden_techniques_the_run_already_has_and_refuses_a_new_hidden_one`). After the fix `tests/draft` is 486 passed, 0 failed (it was 471 passed, 15 failed). The first whole-folder runs of `tests/state` and `tests/editor` were cut by the dropped link;
the figures above are the reruns, on the final code.


## 9. What I could not verify

- **The link to the server was unstable for the last part of the work** (ssh dropped runs of about two minutes, an upload of the snapshot stalled for half an hour twice, a reboot of the server ended one run): the folders of `tests/draft`, `tests/ops`, `tests/state` and `tests/editor` are therefore given as runs of their files (section 8), not as one summary line each. I did not start any process on the server by other means (an attempt to start the runs detached was refused, and I did not go round it).

- Nothing reached Wikimedia: the real answers of the service (whether its 429 carried a `Retry-After`; the six messages say "khoảng 1 phút", which is the default of 60 s or a time of at most 60 s) are not known. The claim that the unpaced client was refused is proved with a fake that does what the real one did (a refusal when two requests come less than a second apart), not with the real one;
  whether one request a second is enough for Wikimedia in practice (its own rule says about that) is for the first real run.
- The proof of point 2 used fake files for the six pictures (no network): that the real Commons files download is the coordinator's batches' proof (they worked).
- The model's thinking is empty in the transcript, so point 4 is its notes and its last message, read against the two sentences of ours that they repeat, not its reasoning; whether the same model with the example changed draws the rays is for the next real draft.
- Pages: no browser was opened. The new sentences (`errmsg.js`) are syntax-checked and the existing page tests pass; the new action has no button on the pictures page (the brief asked for the route, the state answer and the command).

## 10. Needs another worker

- `bti/draft/techniques_md.py` (the "none is fine; a camera move serves most sentences" paragraph, point 4) and a measuring helper for the draft workspace.
- `bti/draft/boxops.py`: the prompt box's refusal of a hidden technique has the code `unknown_technique`; it could use `technique_not_offered` like the typed operations now do.
- The pictures page (`views/picks_auto.js`) shows only a job whose `meta.action` is `auto`; a job `retry` is not shown there (it is followed by `bti job`, and by the state answer's `jobs`).
- `bti` (`bti/cli`): the default request timeout is 60 s; an `import` that waits for a host can take longer (the documents say `--timeout 300`).
