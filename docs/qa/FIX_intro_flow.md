# FIX intro flow (worker `introflow`): the whole painting first, the longer channel-name beat with the video's title, and "fit the storyboard to the voice again"

Branch `wt/introflow`. The renderer `ID-BRAND-03` is the other worker's (`introengine`); this branch is written against its contract (slot `image`, params `camera`
like `ID-BRAND-01`, texts `text`, `title`, `subtitle`, nominal 9.1 s) and never edits `bti/engine/techniques/identity.py`, `style/gae/techniques.json` or `tests/engine/`.

## What each section became

### 1. The two silences per project
- `bti/voice/config.py`: `intro` in the built-in defaults, `LEAD_RANGE` (0.2 to 15), `TITLE_RANGE` (3 to 30), `silence_settings(saved, cfg)` (the values in force and whether each is
  the project's own), `silenced(cfg, saved)` (the config with the project's own `lead` and `title` in `silence`; the very same object when it has none).
- `bti/voice/plan.py`: `make_plan` builds the chunks (the gaps) from `silenced(cfg, saved)`; `Plan.cfg` is that config. A project without its own values gets the config unchanged, so
  its gaps, its `assemble_sig` and its voice state are exactly what they were (tests/voice/test_intro_silences.py recomputes the old formula independently and compares).
- `bti/voice/timingfile.py`: `title_end` (and `card_length`) read the silences of `plan.cfg`. `bti/voice/status.py`: `describe` has a new key `silence`
  (`{lead, title, own: {lead, title}, default, intro, range}`); `settings` is still `{tempo, pad}` (a test pins it).
- `bti/editor/voice_api.py`: `PUT .../voice/settings` takes `lead` and `title` (null removes the project's own value; out of range is `422 bad_lead` / `bad_title`, nothing written).
- `config/voice.json`: `"intro": {"lead": 5.0, "title": 10.2}`. `bti/library/projects.py`: `create_project` (the only place the app makes a project) writes the two values into
  `voice/settings.json`.
- A change of either value makes the voice `stale` with the existing reason `mix_settings_changed` (the gaps are in `assemble_signature`); `voice.generate` with scope `changed` then
  assembles and aligns again, no part `synth-*` exists, the chunk files keep their modification times, and every word is later by the difference of the leads (cold open) and of the
  leads plus the difference of the title silences (every later word) (test with the fake provider).
- The estimate of the voice's length (`planner.estimate_*`) counts characters only, not silences: nothing to change.

### 2. The style
- `style/gae/style.json` (`identity` block only): `raking.brand` is `ID-BRAND-03`, `raking.nominal` is `{"open": {0.0, 3.6}, "label": {1.2, 3.8}, "brand": {9.1}, "mark": {3.2}}`; `dim` untouched.
- How an old `ID-BRAND-01` slot under `raking` is kept from being reported: the block says it. `raking.earlier = {"brand": ["ID-BRAND-01"]}`; `bti/identity/config.py` reads it
  (`StyleDef.earlier`, `StyleDef.own(role)`) and `is_mismatch` accepts the style's current technique **and** its earlier forms. Nothing else reads the key. The old slot is still
  a title slot to `apply_identity` (family prefix), so it becomes `ID-BRAND-03` when the identity is applied again (the retime does it); until then it renders as before.
  `ID-BRAND-01` is not an earlier form of `dim`.
- The fallback table `NOMINAL` of `bti/identity/apply.py` (used only for a block with no numbers, the fake blocks of the tests) keeps the old numbers.

### 3. The opening shot, written by the program
- `bti/draft/zones.py` (new, pure): `opening_span`, `whole_camera`, `opening_shot`, `OPENING_ID`, `is_opening`, and the placement of the cards (see 4).
- `bti/draft/compile.py`: `_Compiler.zones()` calls `zones.place`; `opening_camera`, `opening_rec` (a rec of kind `opening`, id `s0000`, `t0` 0, anchor `{"t": 0.0}`), `assign_ids`
  (the reserved id belongs to the opening alone: no other shot takes it over and it takes nobody's), `map_issue` ("opening shot"). The model's first shot starts at
  `{"w": 0, "off": -0.35}` because the first zone's start is the end of the opening shot.
- `apply_identity` puts `ID-OPEN-01` (0 to 3.6 s) and `ID-LABEL-01` (1.2 s, up to 3.8 s, shortened to the end of the shot) on it by the existing rule, with the new nominal numbers.
- **The mark of the opening shot is its id, `s0000`.** `bti/ops` hands out the next number after the largest in use, the compiler `s0001`, `s0002`, ...: `s0000` is nobody's else.
  An id survives every typed operation, an edit-mode compile (the shot is read back with its id and copied through verbatim), the fast edit and the identity application; the
  other candidates do not: `source` is overwritten by every operation (and by the merge), `note` is cleared when a shot's technique or picture changes and the owner may rewrite it, and
  the technique is an ordinary one (`CAM-01`). The validator needed no change for it.

### 4. The channel-name beat
- `zones.title_length(B, gap, cd) = min(B, gap - cd - 1.2)`, else `min(B, gap - cd)` when that is under `MIN_CARD_S`; `B = zones.brand_length(cfg, style)` is `nominal.brand.dur_s` of the
  style (9.1) and 2.9 when the style has none (or no identity is applied). With 10.2 + 3.2 the beat is 9.1 s and starts 1.5 s after the last word; with 6.2 + 3.2 it is 5.4 s.
- `bti/identity/apply.py`: on a title slot whose technique has the params `title` and `subtitle` (the registry defaults say so) it writes `text` = channel name, `title` = `identity.video_title`
  (else the painting's title), `subtitle` = "<painting's title> · <Artist, year>" (else "<Artist, year>"), from the same `texts()` the label uses (computed once, before the old overlays
  go). `identity.video_title` is kept when the style is applied again; `with_video_title(storyboard, title)` and `video_title_of` are the helpers. Applying twice gives the same document.
- `bti/editor/identity_api.py`: `PUT .../identity` takes an optional `video_title` (whitespace and newlines become single spaces, at most 90 characters: `422 video_title_too_long`,
  not a string: `422 video_title_invalid`, `""` removes it) and `style` is optional when a title is given (the present style stays; the default one when there is none). The answer has `video_title`
  only when the request had one (an existing test pins the other answers' keys). `GET` has `video_title`.
- `bti/engine/storyboard.py`: `identity.video_title` must be a string when it is there (`not_a_string`, the existing code: a new issue code would need a Vietnamese template in
  `sbissues.js`, which is not mine). A full compile and an edit keep the field (tests).

### 5. Fit the storyboard to the voice again
- `bti/draft/retime.py` (new): `off_voice(storyboard, timing, style, meta=None) -> [problems]` (tolerance 0.05 s; codes `first_shot_late`, `opening_missing`, `opening_extra`, `title_off`, `card_off`,
  `card_count`, `end_off`; each problem has `repair` and `locked`) and `retime(storyboard, timing, style, meta=None, defaults=None) -> (storyboard, report)`; `project_off_voice(project_dir)` for
  a project on disk (never raises). The placement is `zones.place`, the same pure code the compiler calls.
- Route `POST /api/projects/{pid}/storyboard/retime` `{base_rev, actor?}` in `bti/editor/retime_api.py` (new; included in `app.py` in a marked block). It commits through the app's `commit` (the same
  path as the identity route: the storyboard lock, validation, the page's save with its `history/` copy) and adds one batch to the change log (`ops: [{"op": "retime"}]`, one sentence per
  changed shot): `bti changes` lists it and `bti undo` takes the shots back. Answer `{rev, changed: [shot ids], batch, report}`; nothing changed means no write, the same `rev`, `changed: []`.
- Action `storyboard.retime` ("Khớp lại với giọng đọc", `bti/editor/state_api.py`), listed only while `off_voice` is not empty, before `storyboard.approve` in the catalogue; ready when the voice is done (`voice_done`
  otherwise), `advances` when some problem is repairable; body `{"base_rev", "actor": "cli:retime"}`; `bti status` names it (`next: bti do <p> storyboard.retime   (Khớp lại với giọng đọc)`) and the
  automatic run takes it by its own rule (the first ready advancing action). New need `storyboard_fits_voice` on `storyboard.approve` and `export.start`.
- Guard: `POST .../approve` (`bti/editor/app.py`, marked block) and `export.start` (`bti/export/run.py:start`, before any part is planned) refuse with `409 storyboard_off_voice`
  (`problems`, the fix names the action). Vietnamese in `errmsg.js` (my block at its end), the action's name is the Spec label (and `labels.js`, `RETIME_LABELS`), one line with a button on the
  storyboard page (`retimeline.js`, mounted by 3 lines in `views/storyboard.js`; shown only while the state answer lists the action).
- Documents: `python -m bti.editor.hints` and `python -m bti.cli.docgen` run (`docs/AGENT_API.md`, `skills/*/SKILL.md`), a paragraph in `skills/storyboard/SKILL.md`, `skills/voice/SKILL.md`,
  `docs/AGENT_API.md` section 11.

### 6. What the model is told, and what a person reads
- `skills/storyboard_draft/TASK.template.md` and `skills/storyboard_edit/FAST.template.md` (and the identity section of `bti/draft/techniques_md.py`): the program writes the opening shot `s0000`; the
  model's first shot starts on the first word and is never a still view of the whole painting. The two size bounds of the briefings (tests/draft/test_explainers_briefing.py, test_fixdraft.py) were
  raised by what this costs (27,000 to 27,500 bytes, 9,300 to 9,500).
- `bti/output/shotwords.py`: the opening shot reads "Mở đầu: cả bức tranh", the new beat "Tên kênh và tựa video: <title>" (`ID-BRAND-03` in the `CARD` table); `labels.js` has the same card name and `OPENING_WORDS`.
- `docs/APP_GUIDE.md` (Vietnamese section in step 5), `docs/design/2026-11-18-identity-raking-light.md` section 10.

## Decisions where the brief was silent
1. **The mark of the opening shot is its id, `s0000`** (reasons in section 3). `bti.draft.zones.OPENING_ID`, `is_opening(shot)`.
2. **When there is an opening shot.** The first word of the video starts at 3.3 s or later **and** the video starts with a cold open (the first chapter's `lead.kind` is `plain`). A video with no cold
   open starts with the beat or a card (the first picture is already the title slot, `zones.place` moves its start to 0), so it has no opening shot. Also only when the main painting's pixel
   size is known (else no camera can be made: the compiler writes no opening, `off_voice` reports `opening_missing` with `repair: false`).
3. The opening shot is written whether or not an identity style is applied (`compile_specs(identity=False)` keeps the old cards but still gets the opening). `fit_pct` is read from the style's
   `matte.painting_height_pct` either way. Its fields: technique `CAM-01`, slot `image` = the main painting, intent `establish`, `source` `agent` (the compiler's word), note
   "opening shot: the whole painting before the first word", `transition_in` null.
4. A first word between 3.30 and 3.35 s gives an opening shot of 2.95 to 3.0 s: shorter than the 3.0 s floor of an opening overlay, so `apply_identity` skips `ID-OPEN-01` there (reason
   `no_room`); the label is skipped too. It cannot happen with the silences in use (5.0 s); I kept the threshold the brief gave.
5. `off_voice` / `retime` ignore a timing that the voice code did not write (no chapter has a `lead`): the reference and lab projects of `projects/` (their cards and ends are older or
   hand-made) report nothing, so they approve and export as before. Every stored storyboard of a real project is clean (proof below).
6. A first shot that starts at 0 without the reserved id is taken as the owner's or the model's own opening: not a problem even when the first word starts late (`opening_missing` is
   reported only when the first shot does not start at 0 either). If the next shot after an inserted opening starts on word 0 its start becomes `{"w": 0, "off": -0.35}`; any other start
   (another word, an absolute time) is left alone. After a removal the next shot starts at 0 (`{"w", "off": -word start}` or `{"t": 0.0}`).
7. `retime` moves only what is off (a clean card or beat is not touched, so a clean old-layout storyboard keeps its 2.9 s beat) and an off beat takes the new length rule. The cards are moved
   before the beat; **a beat whose card cannot be moved (locked, its end not where the silence ends, a wrong number of cards) is left too**, and a locked shot is never changed (`left` says so).
   A card whose end is not where its silence ends is reported, not repaired (its end is the next shot's start, which is the model's or the owner's). If the moves would put two shots out
   of order nothing is moved (`retime_blocked`).
8. `retime` always applies the identity style again when the storyboard has one (the opening overlays on the opening shot, `ID-BRAND-01` becomes `ID-BRAND-03` with its texts, the marks);
   a storyboard with no `identity` (the old look) is judged by `X-CARD-02` / `X-CARD-01` and keeps them (no identity applied). `meta.main_asset` is the project's `picks.json` main painting.
9. The route's answer is `{rev, changed: [shot ids], batch, report}` (`batch` is the change-log id; null when nothing was written). `actor` is optional (default `human`); the action's body
   carries `cli:retime`, which `bti do` replaces with the caller. Undo puts the shots back; the document's `end` and `identity` stay as the retime left them (`bti.ops.undo` restores shots
   only; that module is not mine).
10. `storyboard.retime` is `ready` when the voice is done and `advances` only when some problem is repairable; a problem `retime` cannot repair (`card_count`) is listed and still blocks the
    gate, but the automatic run then stops at the gate (`gate_refused`) instead of looping on a call that changes nothing. `storyboard.approve` and `export.start` carry the need
    `storyboard_fits_voice` while the storyboard is off; the guard code is `storyboard_off_voice`, HTTP 409, `retry: after_fix`.
11. `identity.video_title`: whitespace and newlines inside are collapsed to single spaces, 90 characters after trimming; the validator only checks that it is a string (a new issue code
    would need a Vietnamese sentence in `sbissues.js`, not mine). `GET .../identity` always has `video_title`; the PUT answer has it only when the request had it. The page has no input
    box for the title (not in the brief): an agent or the command sets it (`--set style=raking --set video_title=...` on `identity.set`).
12. `GET .../voice` has a new key `silence`; `settings` keeps `{tempo, pad}` (a test pins it). A value in `settings.json` out of its range is ignored (the project is taken as having none).
13. The fallback table `NOMINAL` in `bti/identity/apply.py` keeps the old numbers (a style block with no numbers, the fake blocks of the tests); the real block has the new ones.
14. The tests use a fixture `brand03` (tests/draft/intro_helpers.py) that adds an `ID-BRAND-03` entry to the registry when it is missing; with the real entry it does nothing.
15. Shared tests I edited because the change makes them say something else: `tests/draft/test_explainers_briefing.py` and `tests/draft/test_fixdraft.py` (size bounds of the two briefings, +425 and
    +178 bytes), `tests/draft/test_identity_catalogue.py` (the family is the seven techniques of the block **plus the earlier form** `ID-BRAND-01`), `tests/draft/test_box_briefing.py`
    (`ID-BRAND-03` joins the ids that must not be in the small-edit catalogue) and, as the coordinator allowed, `tests/engine/test_identity.py::test_style_block_names_the_techniques_of_each_style`
    (now states the new block: `raking.brand` `ID-BRAND-03` with nominal 9.1, `earlier.brand` `["ID-BRAND-01"]` and `ID-BRAND-01` still a registered technique, the opening 0 to 3.6 s, the
    label 1.2 s for 3.8 s, the mark 3.2 s, `dim` as it was).

## Proof on real data (read only: `eligius` and `arnolfini-opus`)
Read-only: `storyboard.json`, `timing.json`, `project.json` and `picks.json` of the two projects were copied from `D:\code\behind-the-image\projects\<id>\` into
`D:\code\behind-the-image\run\snap-introflow\_scratch\real\<id>\` (nothing was written in the projects); the script `_scratch/proof.py` (kept at `.scratch/introflow/proof.py`)
ran on the snapshot with the real registry (`ID-BRAND-03` present) by `tools/deploy/snapshot_py.sh introflow _scratch/proof.py _scratch/real`.

**How the shifted timing of `eligius` was built** (`shift_timing`, the way the voice code would): the same sentences, so every chunk keeps its length; the lead goes from 0.35 to
5.0 s (d1 = +4.65 s) and the silence before the first chapter after the cold open from 6.2 to 10.2 s (+4.0 s more, d2 = +8.65 s). Every word, beat `start`/`end` of the cold open moves by d1, of
every later chapter by d2; a chapter's `start` (where the silence before it starts = where the chapter before it ends) moves by the shift of the words before it, its `end` and `lead.end` and
`card_start`/`card_end` by the shift of its own words (`c02`: `lead` 59.92 to 73.32 = 10.2 + 3.2, `title_end` = `lead.start` + 10.2); `duration` + d2 (762.49 s). (a) is `off_voice` on the documents
as they are; (b) is the rest.

```
ID-BRAND-03 in the registry: True

======== (a) off_voice as it is: eligius ->  []

======== (a) off_voice as it is: arnolfini-opus ->  []

======== (b) eligius, lead 0.35 -> 5.0 and title silence 6.2 -> 10.2
new timing: duration 762.49 (was 753.84); first word 5.00; chapters:
    {'id': 'c01', 'start': 0.0, 'end': 59.92, 'lead': {'kind': 'plain', 'start': 0.0, 'end': 5.0}}
    {'id': 'c02', 'start': 59.92, 'end': 145.24, 'lead': {'kind': 'title', 'start': 59.92, 'end': 73.32}, 'card_start': 70.52, 'card_end': 73.32, 'title_start': 59.92, 'title_end': 70.12}
    {'id': 'c03', 'start': 145.24, 'end': 234.71, 'lead': {'kind': 'card', 'start': 145.24, 'end': 148.44}, 'card_start': 145.64, 'card_end': 148.44}
off_voice before retime (12):
   first_shot_late  x1   first: the first shot starts at 4.65 s, not at 0
   opening_missing  x1   first: the first word starts at 5.00 s: the video needs the opening shot (the whole painting) before it
   title_off        x1   first: the channel-name beat ends at 61.87 s, the voice puts its end at 70.52 s
   card_off         x8   first: the chapter card starts at 61.87 s, the voice puts it at 70.52 s
   end_off          x1   first: the video ends at 753.84 s, the voice lasts 762.49 s
main painting: goldsmith_his_shop_3bc1 size (3469, 4000)

off_voice after retime: []
stale anchors after retime: []
second retime changes nothing: True | moved: [] inserted: [] removed: []
validator errors after retime: [] (0)
first three shots after retime:
  s0000     0.00 -> 4.65    CAM-01      start={"t": 0.0}   overlays: ID-OPEN-01@0.0+3.60, ID-LABEL-01@1.2+3.45
  s0001     4.65 -> 12.76   CAM-01      start={"w": 0, "off": -0.35, "text": "Look"}
  s0002    12.76 -> 17.73   CAM-05      start={"w": 21, "off": 0.0, "text": "A"}
the beat:
  s0011    61.42 -> 70.52   ID-BRAND-03 start={"t": 61.42}
   params: {"text": "RAKING LIGHT", "title": "St. Eligius", "subtitle": "Petrus Christus, 1449"} camera: [[{"rel": 0.0}, 1850, 2400, 0.64], [{"rel": 1.0}, 1850, 2400, 0.6592]]
the first chapter mark:
  s0012    70.52 -> 73.32   ID-MARK-01  start={"t": 70.52}
   params: {"title": "1. The Open Window"}
opening shot params camera: [[{"rel": 0.0}, 1734.5, 2000.0, 0.25785], [{"rel": 1.0}, 1734.5, 2000.0, 0.26559]] id s0000 note: opening shot: the whole painting before the first word
shots from the first chapter mark on: 104 | changed: 8 | all of them only in `start`: True | their techniques: ['ID-MARK-01']
end: {'t': 753.84} -> {'t': 762.49}
report: inserted ['s0000'] removed [] end {'from': {'t': 753.84}, 'to': {'t': 762.49}} left []
report moved: 9 (first 4): [{"shot": "s0012", "what": "start", "from": {"t": 61.87}, "to": {"t": 70.52}}, {"shot": "s0022", "what": "start", "from": {"t": 136.99}, "to": {"t": 145.64}}, {"shot": "s0036", "what": "start", "from": {"t": 226.46}, "to": {"t": 235.11}}, {"shot": "s0050", "what": "start", "from": {"t": 315.84}, "to": {"t": 324.49}}]
report identity: style raking, changed 3 shots, skipped []

(c) arnolfini-opus retime on its own timing: moved [] inserted [] removed [] end None left []
```

Read: in (b) `off_voice` lists 12 things (the first shot at 4.65 s, the opening shot missing, the beat, the eight cards and the end); `retime` inserts `s0000` (0 to 4.65 s, the whole
3469x4000 painting at zoom 0.25785 = 95.5 % of the height, a 3 % push), puts `ID-OPEN-01` and `ID-LABEL-01` on it, moves the beat to 61.42 to 70.52 s (9.1 s, starting 1.5 s after the last
word of the cold open at 59.92 s) as `ID-BRAND-03` with `text`, `title` (the painting's title: no video title was set) and `subtitle`, moves the eight cards, sets `end`; the 104 shots from the
first chapter mark on are unchanged except the start of the 8 cards; a second `retime` changes nothing; the engine's validator finds no error.

## The calls the coordinator makes on a real project to get the new opening
On a project made before this change (for example `eligius`), with `$P` its id and `rev` the current storyboard revision (`GET /api/projects/$P` or `bti status`):

1. The two silences: `PUT /api/projects/$P/voice/settings` `{"lead": 5.0, "title": 10.2}`. The voice becomes `stale` (`mix_settings_changed`, "cần ghép lại").
2. The voice again, no sentence spoken again: `bti do $P voice.generate --yes-cost --wait` (the state's body is `{"scope": "changed"}`; the aligner runs again, a heavy part of a few minutes; the
   chunks are cached). `GET /api/projects/$P/voice` then shows `state: done` and `silence.own` true for both.
3. The video's title: `PUT /api/projects/$P/identity` `{"video_title": "<title>", "base_rev": rev}` (or `bti do $P identity.set --set style=raking --set video_title="<title>"`). The
   answer has `video_title`. Applying the identity at this point only rewrites what the identity owns; step 4 applies it again on the right positions.
4. Fit the storyboard: `bti do $P storyboard.retime` (`POST /api/projects/$P/storyboard/retime` `{"base_rev": rev, "actor": "cli:<name>"}`); `bti status $P` names it as `next:` as soon as
   step 2 is done. The answer has `changed` (the opening shot `s0000`, the beat, the cards), `batch` (undo with `bti undo $P <batch>`) and `report` (`left` must be empty; if not, read it).
5. `bti approve $P storyboard` (only if the owner allowed that gate; else the owner approves on the page), then `bti do $P export.start --yes-cost --wait`.
   Before step 4 both are refused with `storyboard_off_voice`; after any later edit the approval must be made again (the retime changed the revision).

Order note: steps 3 and 4 may be swapped (the retime applies the identity again and writes the title from `identity.video_title`).

## Tests
Snapshot `introflow` (`D:\code\behind-the-image\run\snap-introflow\`), one folder per run, never `-m slow`, with the real registry (`ID-BRAND-03` present). Summary lines exactly as printed:

- `tests/voice`: `95 passed, 1 skipped, 1 warning in 74.77s (0:01:14)`
- `tests/identity`: `88 passed in 1.85s`
- `tests/draft`: `461 passed, 1 warning in 163.73s (0:02:43)`
- `tests/state`: `302 passed, 1 warning in 180.35s (0:03:00)`
- `tests/export`: `81 passed, 2 skipped, 1 warning in 16.09s`
- `tests/editor`: `508 passed, 1 warning in 234.36s (0:03:54)`
- `tests/cli`: `130 passed, 1 warning in 50.26s` (an earlier run of this folder failed one test, `test_every_action_id_a_document_names_exists`: `skills/storyboard/SKILL.md` wrote `identity.video_title`, which the test reads as an action id; reworded, rerun green)
- `tests/auto`: `207 passed, 1 warning in 73.68s (0:01:13)`; after the last wording change of `docs/APP_GUIDE.md` the one file that reads it, `tests/auto/test_run_joined.py`: `30 passed, 1 warning in 13.28s`
- `tests/output`: `77 passed, 1 warning in 17.06s`
- `tests/engine -m "not slow"`: `646 passed, 14 skipped, 166 deselected in 405.23s (0:06:45)` (the first attempt ran the folder without `-m "not slow"`; I stopped it at 43 % and ran it again with the marker: no slow test was run)
- Node (Mac): `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`:
  `ℹ tests 460`, `ℹ suites 0`, `ℹ pass 459`, `ℹ fail 0`, `ℹ cancelled 0`, `ℹ skipped 1`, `ℹ todo 0`, `ℹ duration_ms 935.23425` (the skipped one needs a `.venv` on the Mac).
- `tests/output` passes with the golden `tests/output/fixtures/shot_cases.json` the engine worker regenerated: my `shotwords.py` words `ID-BRAND-03` the same ("Tên kênh và tựa video"), so no regeneration was needed.

New test files (all green above): `tests/voice/test_intro_silences.py` (the config, the route, the gaps, the old signature, a run with the fake voice: a silence change is `mix_settings_changed`, no part
`synth-*`, the chunk files untouched, every word later by the difference, `title_end`), `tests/draft/test_intro_flow.py` (zones, the whole painting in the frame for upright, very wide and other paintings, the
full compile with the opening shot, the 9.1 s beat with three texts, the cards, `off_voice` empty; the voice made again: `off_voice` lists, `retime` fixes, word-anchored shots byte-identical, validator clean, twice = same;
an old-layout storyboard (2.9 s beat, `ID-BRAND-01`, lead 0.35) is clean and `retime` after a lead of 5.0 inserts the opening and moves the overlays; removal when the first word starts early; locked card; wrong number
of cards; old-look storyboard; edit-mode compile; a full recompile; the engine draws it), `tests/draft/intro_helpers.py`, `tests/identity/test_intro_beat.py` (the block, `earlier`, texts, video title, nominal numbers,
validator), `tests/editor/test_retime_route.py` (the route, undo, one logged batch, stale revision, guard on approve and export, the title through the route: set, changed, removed, 90 characters, kept by a style choice and by
a recompile), `tests/state/test_retime_state.py`, `tests/export/test_retime_guard.py`, `tests/cli/test_retime_cli.py`. Changed existing tests: see decision 15.

## What I could not verify
- **No page was opened.** The line and button "Khớp lại với giọng đọc" (`retimeline.js`, three lines in `views/storyboard.js`, words in `labels.js`) are checked with `node --check` and
  by the state/route tests that decide when the action is listed; no browser, no screenshot. (`tests/editor_frontend` is not one of my test folders, so there is no unit test of `retimeAction`.)
- **No real voice, aligner, render or export** (the rules): the voice runs only with the fake provider and the even aligner; the draw check of the engine draws frames of the opening shot and
  the new beat without error, but nobody looked at the frames of an opening shot of a real painting (the engine worker's stills show `ID-BRAND-03` itself).
- The real run on `eligius` (the coordinator's): the numbers in the proof come from a shifted copy of its timing made as the voice code would make it, not from a real second assembly. The
  real aligner may put a first word a few hundredths of a second away from the chunk start; the tolerance of 0.05 s and `lead.end = max(first word, chunk start)` were made for that, but only
  a real run shows it.
- The slow tests of `tests/engine` (`-m slow`) were not run (rule). The page's behaviour with a storyboard that has `s0000` (the list of shots, the camera editor on the opening shot) is untested.
- A first word between 3.30 and 3.35 s (see decision 4) and a main painting with no known size are handled and tested only at the level of `off_voice` / `zones`.

## Needs another worker
1. `bti/editor/static/js/shotsentence.js` (the JavaScript twin of `bti/output/shotwords.py`): the Python twin now words the opening shot (the shot with the id `s0000`) "Mở đầu: cả bức tranh";
   the page's list of shots still says what its technique says ("Zoom vào cả bức tranh"). The words are already in `labels.js` (`OPENING_WORDS.opening`); the twin needs
   `if (shot.id === 's0000') base = OPENING_WORDS.opening` before the technique's own sentence and one case in `tests/output/fixtures/shot_cases.json` (`UPDATE_GOLDEN=1 node --test
   tests/output/shotsentence_parity.test.mjs`) so that both sides stay in step. The card name of `ID-BRAND-03` ("Tên kênh và tựa video: <title>") is data in both and needs nothing.
2. A text box for the video's title on the storyboard page (the page has none; an agent sets `identity.video_title`). Not in the brief.
3. `bti/ops/undo.py` restores shots only: the undo of a retime leaves the document's `end` and `identity` as the retime wrote them. Harmless here (the voice is the new one), but an owner who
   undoes a retime and then edits by hand sees the new end.
4. `docs/design/2026-11-18-identity-raking-light.md` has my section 10 and the engine worker's section 4b; `skills/storyboard/SKILL.md` has my paragraphs and their regenerated table: the coordinator
   merges both (run `python -m bti.cli.docgen` and `python -m bti.editor.hints` after the merge; both print "up to date" on this tree).
