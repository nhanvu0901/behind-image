# FIX fixes3: the eleven small things left open by the workers of 2026-11-20

Worker `fixes3`, branch `wt/fixes3`, snapshot `fixes3` on the server. No model, no outside service, no `.env`, no git command that writes. Files of the worker `catalogue`
(`style/gae/techniques.json`, `bti/draft/techniques_md.py`, `bti/draft/compile.py`, `bti/engine/viewchecks.py`, `bti/engine/registry.py`, the storyboard templates) were not touched.

## 1. Privacy: no request of the app names the project, a repository, a person, an address or an account

**Found.** `bti.media.http.USER_AGENT` was `behind-the-image-media/0.1 (art documentary research tool)`: it named the project in every request of Commons, the Met, Pexels, Pixabay,
OpenStreetMap (Nominatim and tiles) and the thumbnails. The three sources of the web search worker (`wikipedia.py`, `web.py`, `youcom.py`) each carried their own copy of a generic string.
One more place: `bti/script/providers/openrouter.py` sent `X-Title: behind-the-image` (OpenRouter shows that header as the name of the calling app).

**Changed.**
- `bti/media/http.py`: `USER_AGENT = "ImageResearch/1.0 (art documentary research; generic client)"` (the string the web-search worker chose: a descriptive client name, no person, no
  project, no address, no URL). It is the ONE place of the string; `open_url` sends it by default, so every source that goes through `open_url` (Commons, Met, Pexels, Pixabay, `get_json`,
  `download_file`, thumbnails) says it without writing it.
- `bti/media/sources/wikipedia.py` and `bti/media/sources/web.py`: their own constants (`USER_AGENT`, `GENERIC_UA`) and the explicit header are gone (the default of `open_url` is the same string).
- `bti/media/youcom.py`: `"User-Agent": http.USER_AGENT` (it builds its own `urllib` request, outside `open_url`). `bti/media/sources/osm.py` already used `http.USER_AGENT`.
- `bti/script/providers/openrouter.py`: `X-Title` removed (nothing else: the key goes in `Authorization`).
- Tests: `tests/media/test_http.py` (the pinned string: now `ImageResearch/...`, and it contains no `behind`, `bti`, `github`, `@`, `http`, `mailto`, `nhanvu`) and the new `tests/media/test_privacy.py`
  (10 tests): the string is written once in `bti/` (`ImageResearch` only in `bti/media/http.py`; no `"User-Agent": "<literal>"` anywhere); no module that can open a connection holds a string constant that names the
  project, its repository, the owner or a noreply address (an `ast` scan, docstrings excluded); no `X-Title`/`HTTP-Referer`/`Referer` header is written anywhere; every source as sent (Commons, Met, Pexels, Pixabay, OSM
  with its geocoding query, Wikipedia, the download of a file, the download of a web picture, You.com search and research) carries `http.USER_AGENT` and nothing in its address, headers or body matches the project's
  names, `github`, `@`, `noreply`; the two HTTP model providers (OpenRouter, Gemini) send no app-naming header and no such word.
- `tests/e2e/picks_auto/websearch_proof.py` (real-network proof script, not run): it used to patch `http.USER_AGENT`; it now only asserts the string is the generic one.

**Places looked at** (all of `bti/**` and `tools/**`; searched for `urllib`, `urlopen`, `httpx`, `requests`, `http.client`, `aiohttp`, `socket`, `curl`, `wget`, `pip`, `huggingface`, `snapshot_download`, `User-Agent`, `Referer`, `X-Title`, the names `behind-the-image`, `Behind the Image`, `bti`, `nhanvu`, `github`, `@`):

| place | what it sends to an outside service | result |
|---|---|---|
| `bti/media/http.py` | the one User-Agent, `Accept`; `get_json`/`download_file` add only the caller's query | CHANGED (was the project's name) |
| `bti/media/sources/commons.py`, `met.py`, `pixabay.py` | `http.get_json` / `download_file`: default headers; queries are the wanted words; Pixabay's key in the query (never in a message: `_short`) | clean |
| `bti/media/sources/pexels.py` | `Authorization: <key>` + `Accept`; the User-Agent is the default of `open_url` | clean |
| `bti/media/sources/osm.py` | Nominatim `q, format, limit, addressdetails` (no `email=` parameter), `http.USER_AGENT`; tiles through `open_url` | clean |
| `bti/media/sources/wikipedia.py`, `web.py` | own copies of the generic string | CHANGED (one place now) |
| `bti/media/sources/bookpage.py` | local files only | clean |
| `bti/media/youcom.py` | `X-API-Key`, `Accept`, the User-Agent; body = the question (`research`) or the query (`search`) | CHANGED (shared string) |
| `bti/media/research.py`, `bti/picks/suggest.py`, `bti/picks/context.py` | what the You.com prompts hold: the narration line, the painting's title, artist, year, motifs; never the project id | clean |
| `bti/media/clips.py` | `yt-dlp` command lines: no `--user-agent`, no cookies, no account | clean |
| `bti/script/providers/openrouter.py` | `Authorization`, `content-type`, ~~`X-Title`~~ | CHANGED |
| `bti/script/providers/gemini.py` | `x-goog-api-key`, `content-type`; httpx's own User-Agent (`python-httpx/<version>`) | clean |
| `bti/script/providers/antigravity.py`, `claudecode.py`, `bti/draft/providers/agy.py`, `claudecode.py`, `auto.py` | the `agy` / `claude` programs, with an allow-listed environment and a work folder in the system temp folder; the network is those programs' own | see "Seen, not changed" (1) |
| `bti/cli/transport.py`, `bti/evals/*` | `urllib` to `BTI_URL`, the app itself (default `127.0.0.1:8560`, no proxy); `Accept`, `Content-Type` | clean (not an outside service) |
| `bti/longjob/heavy.py` | `APP_MARK = "behind-the-image"` is written into the local lock file `D:\bench\_heavy.lock`, never sent | clean |
| `bti/voice/align_worker.py`, `bti/voice/providers/chatterbox.py` | `faster-whisper` may fetch its model from Hugging Face with the library's own client (`HF_HUB_DISABLE_TELEMETRY=1` is set by the deploy scripts) | clean (library default) |
| `bti/editor/static/**` (pages, scripts, styles) | the only outside address is the YouTube embed of a clip preview (`picks.js`, `referrerpolicy="strict-origin-when-cross-origin"`) | see "Seen, not changed" (2) |
| `bti/script/brief.py`, `bti/draft/inputs.py` | data handed to a model: `project` = the project id (the painting's slug), which is the content of the work, not an identity of the owner | see "Seen, not changed" (3) |
| `tools/deploy/*.sh`, `*.ps1`, `*.bat`, `*.py` | `ssh`/`scp` to the owner's own server; `git push` / `git fetch` to the project's own remote (the deploy route); `pip install -r requirements.txt` with pip's own client; `download_model.py` through `faster_whisper` | clean, see (4) |
| `tools/geo/build_bundle.py` | Natural Earth downloads with `naturalearth-bundle-builder/1.0` (names neither the project nor a person); it is a stand-alone build script that does not import `bti`, so it does not use the shared string | clean, left |
| `tools/run_editor.sh`, `run_editor.bat`, `tools/bti`, `tools/server/wait.sh` | pip, the local app, ssh to the owner's server | clean |
| `tools/clean_text/**`, `tools/explain*`, `tools/text_audit`, `tools/export_arnolfini.py`, `tools/paintings_table.py`, `tools/registry_merge.py`, `tools/vmetrics.py` | no network at all (they hold the owner's home folder in absolute paths; they send nothing) | clean |
| `config/*.json`, `prompts/`, `skills/` | no address is sent from them; `config/server.json` holds a server path | clean |

**Seen, not changed** (decisions for the owner or the coordinator):
1. The temporary work folders the model programs run in are named `bti-claude-*`, `bti-agy-*`, `bti-draft-*`, `bti-picks-*`, `bti-title-*`. `bti` is the project's abbreviation, and a model program may show its working
   folder to its model. It is a folder name, not a header, a query or a body, and the names are pinned by tests and by the cleaning of old folders (a new prefix would orphan the old folders), so I left them.
2. The YouTube embed sends the page's ORIGIN (the app's own address, no path, no project id) as Referer. `no-referrer` would remove it but some videos refuse to play without an origin.
3. The data files handed to a model carry the project id (`brief.py`: `"project": ...`). I read "the project's name" as this software's name, which is what the brief's example (`USER_AGENT`) is; the id of a video project is the slug of the painting.
4. The deploy route pushes to the project's GitHub repository by design; the repository address lives in git's own configuration, not in any code.

## 2. A title on a storyboard that no longer fits the voice

**Found.** `PUT /api/projects/{pid}/identity` applied the identity (with the new title) to a storyboard whose cards and beat still sat where the old voice put them; the engine refused the result and the
answer was the validator's raw "shots must be in time order" errors. `title.set` (`PUT .../title`) already stored the title first and swallowed the engine's refusal into a generic "Chưa cập nhật được tựa video..." sentence; `storyboard.retime`
did NOT read the title document: it applied the identity with the `identity.video_title` the storyboard already had, so a title stored while off the voice could never reach the beat by it.

**Changed.**
- `bti/editor/identity_api.py:put_identity`: after the revision check and before anything is applied, `RT.project_off_voice(d, saved)` (the guard of the approval and the export); a non-empty answer is `409 storyboard_off_voice`
  with `problems` (the code's own `fix` and `retry: after_fix` come from `hints.py`, "call storyboard.retime"). Decision: the guard covers every `PUT .../identity` (a style change as well as a title), because the same `apply_identity` fails the same way for both.
- `bti/editor/title_api.py:apply_title` (the function `title.set` and `title.generate` call through `bti.title.apply`): when the storyboard is off the voice it writes nothing and answers
  `{rev, changed: [], approval_was_fresh: false, off_voice: true, code: "storyboard_off_voice", problems: n, sentence}`. `bti/title/texts.py:storyboard_off_voice_sentence()` is the sentence ("Storyboard đang lệch với giọng đọc ... Bấm "Khớp lại với giọng đọc" ... storyboard sẽ lấy tựa này ngay khi khớp xong.");
  the title itself is stored before that, as always (`title.json`). `bti/title/job.py`: the job's result `sentence` ends with it.
- `bti/draft/retime.py:retime(..., video_title=None)`: before the identity is applied again, `identity.video_title` is set to `video_title` (when given and different; `report["video_title"] = {from, to}`). Not applied when the moves are blocked
  (the document stays as it was) or when the storyboard has no identity style.
- `bti/editor/retime_api.py`: passes `bti.title.chosen_text(d)`: the title document wins over the storyboard's own `identity.video_title`, the same precedence the draft compiler has (`compile.py` is not touched).
- `bti/title/view.py`: `GET .../title` has `storyboard.off_voice` (used by point 11). Docs: `docs/AGENT_API.md` (the retime paragraph, the recipe for an old video: retime first, then the title; the title section), `skills/title/SKILL.md`, the `when` texts of `title.set`, `identity.set` and `storyboard.retime` in `bti/editor/state_api.py` (and `docs/AGENT_API.md` regenerated by `python -m bti.editor.hints`).

**Tests.** `tests/editor/test_retime_route.py` (real engine): the identity route answers `storyboard_off_voice` (409, `retry`, `fix`, `problems`) for a title, a style, and both, writes nothing, answers a stale revision as stale, and works after the retime;
a title set while off the voice is stored, the answer says so, the storyboard is untouched, `GET .../title` says `off_voice: true`, the retime writes it onto the beat (`report.video_title`), `off_voice` is false afterwards and the undo takes it away;
the title document wins over the storyboard's own title and a fitted storyboard with no title document is left alone (no revision written); `tests/title/test_title_job.py`: the job stores the title and its sentence ends with the off-voice sentence.

## 3. Undo of a retime

**Found.** `bti/ops/undo.py` restored the shots of a batch only. A retime's batch also changes `end` and `identity`; the two copies of the batch (`batch_NNNN.before.json` / `.after.json`) hold the whole document, so the data was there.

**Changed.** `bti/ops/undo.py`: `is_whole(record)` (every operation the record names is in `WHOLE_DOCUMENT_OPS = ("retime", "identity")`), `changed_parts(before, after)` (top-level keys other than `shots` and `approvals`, derived `_` keys ignored,
whose value differs), `restore_parts(...)`, and `find_conflicts(..., whole=False)` / `undo_changes(..., whole=False)` take the new keyword. `bti/ops/runner.py:run_undo` passes `whole` for a storyboard batch that is whole.
A part that was changed since is a conflict `{"thing": {"part": "end"}, "key": "part:end", "batches": []}` (the same rule as a shot: nothing is undone); the `changes` of the undo have `{"target": {"part": ...}, "time": null, "what": ...}` ("Điểm cuối của video: trở lại như trước khi sửa", "Kiểu mở đầu và tựa video: ..."). `bti/editor/state_api.py` uses the same call to decide whether an undo is available.
Batches of typed operations are unchanged (`whole` False: shots only). Decision: `"identity"` is listed although no code logs an identity application today (`PUT .../identity` writes no batch; the retime is the one batch that applies the identity); it costs nothing and a future logger needs no change here.
`docs/OPS.md` regenerated (`python -m bti.ops.doc`; the text in `bti/ops/doc.py`).

**Tests.** `tests/editor/test_retime_route.py`: after the undo the whole document equals the one before the retime (except `approvals`), the changes name the part `end`, a part changed since is a 409 `undo_conflict` that writes nothing; `tests/ops/test_undo_log.py`: a typed-operation batch is still undone with only its shots (the page changed `end` and `identity` meanwhile and they stay), `is_whole`, `changed_parts`, `restore_parts` and the part conflict as pure functions.

## 4. `outside_no_picture` on the simple picks page
`bti/editor/static/js/views/picks_rows_logic.js:issueSentence`: `case 'outside_no_picture': return W.issue.outsideNoPicture(line);` (the label was already in `labels.js`). Test: `tests/editor_frontend/picksrows.test.mjs` ("Đoạn 4 nói về thứ ngoài bức tranh nhưng chỉ có tranh chính: ...", and the no-id rule for the new code). The comment of the previous worker in `labels.js` that says the owner of that file "adds" the line is now out of date; I did not edit it (not my block).

## 5. Sentences for `web_budget` and `web_no_key`
`bti/picks/auto/texts.py:why`: `web_budget` ("Đã hết lượt tìm trên web của lần chạy này nên chưa tìm lại được "..." . Chạy lại để tìm tiếp.") and `web_no_key` ("Chưa có khóa để tìm trên web nên chưa tìm được "..." ngoài các nguồn miễn phí. Thêm khóa You.com vào máy chủ rồi chạy lại."). Test: `tests/picks/test_auto_job.py` (both differ from the general sentence, name the wanted thing, and fall back to "hình này" with no `what`).
Found while reading the code: no want gets the code `web_no_key` today (the code is the web client's refusal, kept in `search.json` as `web.stopped`, and the line is then `no_candidates`/`agent_none`); the sentence is ready for when a line carries it.

## 6. The opening shot in the page's twin
`bti/editor/static/js/shotsentence.js`: a shot with the id `s0000` reads `OPENING_WORDS.opening` ("Mở đầu: cả bức tranh") before the technique's own sentence, as `bti/output/shotwords.py` does. Golden file: the parity test builds two more cases (`opening/CAM-01`, `opening/CAM-03`: the shot with the overlays `ID-OPEN-01` and `ID-LABEL-01`) and `UPDATE_GOLDEN=1` regenerated the file; I checked that the only difference with the old file is those two appended cases (all 144 old cases and the technique table are identical).
Tests: `tests/editor_frontend/shotsentence.test.mjs` (the opening, with overlays, under another id, with an unknown technique), `tests/output/shotsentence_parity.test.mjs` (the golden file), `tests/output/test_shotwords.py` (the Python twin gives the same sentence for those two cases). Side effect: the mock storyboard (`bti/editor/static/mock/storyboard.json`) has a title card with the id `s0000`; `tests/editor_frontend/shotlist.test.mjs` now expects "Mở đầu: cả bức tranh" for it (the rule is by id, in both twins, as `Z.is_opening` is).

## 7. `launch_picks_auto.py` can run again
`tests/e2e/picks_auto/launch_picks_auto.py:make_plan`: every line has `kinds` and the `outside` lines a `fallback`; the Krakatoa line (nothing can fill it) is `["outside"]` with `entity` and `period`; the map line is `["outside", "journey"]` with two `places` (a map of one place is refused by the new rule); the idle line is `["idea"]`.
I could not run the script (it starts a second app instance). Guard: `tests/picks/test_auto_e2e_launcher_plan.py` takes `make_plan` out of the script with `ast` (the script patches the app when it is imported) and passes both plans (first run, later run) through `shapes.check_plan`.

## 8. One place for the limits of the two sessions; `allow` for `run_session`
`bti/picks/auto/session.py`: `PLAN_LIMITS` and `CHOOSE_LIMITS` (20 minutes / 80 steps, the old numbers) are removed; `bti/picks/auto/job.py` keeps the real ones (30/120 and 40/220) and the title job its own `LIMITS` (decision: the limits belong to the job that runs the session, so the tests that used `session.PLAN_LIMITS` now use `job.PLAN_LIMITS`; the work folder's task therefore says 120 steps and 30 minutes there).
`run_session(..., allow=None)`: the permission rules of a `claude` session; `session.allow_rules(windows=None, helpers=("check", "crop"))` builds them for the helpers a job's work folder has; None is the pictures job's. `bti/title/job.py` passes `session.allow_rules(helpers=("check",))` (`HELPERS = ("check",)`): no `./crop` form.
Tests: `tests/picks/test_auto_runners.py` (a session with its own rules gets exactly them on the `claude` command line; the default is unchanged; the limits exist once), `tests/title/test_title_job.py` (the title session's rules have no `crop`).

## 9. Web searches in the result of the automatic choice
`bti/editor/static/js/views/picks_logic.js:autoDetailText`: when `result.web.on` the second line ends with `tìm trên web 12/80 lần` (`PICKS_AUTO_LABELS.detail.web`, in a block of mine at the end of `labels.js`); `0/80` is said too (the switch was on and nothing needed it); no maximum known: `tìm trên web 3 lần`; switch off or no `web`: nothing. Test: `tests/picks/picks_logic.test.mjs`.

## 10. `docs/APP_GUIDE.md`
New subsection "Dòng nói về thứ ngoài bức tranh" in section 6 (the app looks for the real picture of the thing, a line without one shows the nearest detail and is listed in "Cảnh báo", the automatic run stops above about a third, exactly 34%, of those lines) and one bullet in section 13 next to the two things the run lets through. Also, for points 2 and 11: the title strip of the storyboard page and the off-voice behaviour in 5.9, and the sentence of section 7 that said the page has no field for the title.

## 11. The video's title on the storyboard page
**Changed.** `bti/editor/static/js/views/storyboard.js` mounts `mountTitlePanel` (the module of the script page, `titlepanel.js`; no second implementation: a test checks that the strip's class and the calls to the title routes exist in that one file) into a new row `#tbar` under the bars;
`takeIn` loads the new storyboard when the answer says the saved storyboard changed (like the identity box and the retime line do). `titlepanel.js`: the `.v-scr` prefix of the strip's styles dropped (the stylesheets are global; the `.v-scr` rule for the script page's own `#title-host` stays), the `takeIn` option, `takeStoryboard` after a pick, a typed title and a finished job.
`titlelogic.js`: `stripView(...).offVoice` and a note (`TITLE_LABELS.offVoice`: "Storyboard đang lệch với giọng đọc nên chưa nhận tựa này. Bấm "Khớp lại với giọng đọc" trước...") from `GET .../title` `storyboard.off_voice`; the toast after a title is stored while off the voice is a warning with the server's sentence; `storyboardChanged`.
`bti/editor/static/css/edit.css`: the root grid gets a row for `#tbar` and every child has its own `grid-row`, so the row coming or going moves no other (hand face: `44px auto 1fr 300px`, short screens `44px auto 1fr 160px`, simple face `auto auto 1fr`).
`#retime-container` moved from `#preview-tools` into `#tbar`: see "Seen, not changed" below, it is why the strip's own sentence can be followed.
Tests: `tests/editor_frontend/title.test.mjs` (3 tests), `tests/editor/test_retime_route.py` (the answer of `GET .../title` while off the voice, and after the retime).

## Seen, not changed (found on the way)
- **The simple face of the storyboard page hides `#preview-tools`** (`edit.css`: `.edit-root[data-mode="simple"] #preview-tools { display: none }`), and that row holds the box "Kiểu mở đầu và mốc chương" (`#identity-container`) and, until now, the line "Khớp lại với giọng đọc". So on the page the owner opens first, the style choice cannot be reached, and until this worker the retime button could not either, although `docs/APP_GUIDE.md` and the error sentence of `storyboard_off_voice` send the owner to it. I moved only the retime line (hidden until needed) into the new row; the style box is still in the hidden row. Needs a decision on where it belongs (probably the same `#tbar`).
- The strip and the new row were checked with `node --check`, the unit tests and the static test of the CSS rules; **nobody opened the page in a browser**.

## Decisions where the brief was silent
1. Privacy: "the project's name" is this software's name and abbreviation as the brief's own example shows; the folders `bti-*` and the YouTube origin are listed, not changed (above).
2. `PUT .../identity` is guarded for every call, not only for a title.
3. The title document wins over `identity.video_title` in a retime (the compiler's own rule); with no title document the storyboard's own title stays.
4. The limits live in `job.py` (not `session.py`).
5. `session.allow_rules` takes the list of helpers; `run_session(allow=...)` is the argument the brief names.
6. The undo of a whole-document batch checks every changed top-level part for a conflict (not only the shots); `"identity"` is a reserved whole-document operation although nothing logs it.
7. The golden file was regenerated by the documented command and its diff checked to be the two new cases only.
8. The mock storyboard's first shot (id `s0000`) reads as the opening in the shot list; the test was changed to say so.
9. `web_no_key` wording asks to add a You.com key to the server (the owner's own server).

## Needs another worker / left for the coordinator
- `labels.js`: the comment above `PICKS_PAGE_LABELS.issue.outsideNoPicture` (block of `linekinds`) still says the case in `picks_rows_logic.js` "needs" adding; it is added.
- The decision on the hidden style box (above) and a look at the page in a browser (the row `#tbar`, the strip on the simple face, the dialog from the storyboard page).
- Merge notes: `docs/AGENT_API.md`, `docs/OPS.md` regenerated by `python -m bti.editor.hints` and `python -m bti.ops.doc`; if `catalogue` regenerates `docs/AGENT_API.md` too, regenerate once after the merge. `tests/output/fixtures/shot_cases.json` must be regenerated after `catalogue`'s changes to `techniques.json` (`UPDATE_GOLDEN=1 node --test tests/output/shotsentence_parity.test.mjs`): the two `opening/*` cases are built by the test itself and stay.

## What I could not verify
- No browser: the title row, its CSS grid, the strip on both faces and the dialog were not seen.
- `tests/e2e/picks_auto/launch_picks_auto.py` and `websearch_proof.py` were not run (a second app, a real network); only their plan and their string are checked by tests.
- No real model, voice, render or outside request ran. A real `claude` session with the narrowed `--allowedTools` of the title job was not started (the command line is checked with the fake program of the tests).
- The privacy list is by reading and by search; a program I did not read (the `agy` and `claude` CLIs, `yt-dlp`, `faster-whisper`, pip, git) sends what it sends.

## Test results (snapshot `fixes3`, server, `BTI_NO_REAL_MODELS=1`)
One folder per run, never `-m slow`; summary lines exactly as printed.

| run | summary line |
|---|---|
| `tests/media` | `405 passed in 7.11s` |
| `tests/picks` (final) | `360 passed, 1 warning in 90.18s (0:01:30)` (the first run printed `1 failed, 359 passed, 1 warning in 92.36s (0:01:32)`: my new test `test_a_job_can_name_its_own_rules_...` assumed POSIX helper names on the Windows server; fixed, folder run again) |
| `tests/title` | `196 passed, 1 warning in 50.02s` |
| `tests/identity` | `88 passed in 1.91s` |
| `tests/draft` | `462 passed, 1 warning in 164.98s (0:02:44)` |
| `tests/ops` | `491 passed, 1 warning in 117.60s (0:01:57)` (one earlier run failed `test_docs_ops_md_is_current` until `docs/OPS.md` was regenerated) |
| `tests/state` | `320 passed, 1 warning in 188.10s (0:03:08)` |
| `tests/editor` | `529 passed, 1 warning in 263.38s (0:04:23)` |
| `tests/output` | `78 passed, 1 warning in 24.86s` |
| `tests/cli` | `131 passed, 1 warning in 52.28s` |
| `tests/auto` | `225 passed, 1 warning in 93.73s (0:01:33)` |
| extra: `tests/export` (the retime guard) | `81 passed, 2 skipped, 1 warning in 17.68s` |
| extra: `tests/script/test_providers.py` (OpenRouter and Gemini) | `19 passed in 0.57s` |
| `python -m bti.cli.docgen --check`, `python -m bti.ops.doc --check`, `python -m bti.editor.hints --check` (on the snapshot) | each exit 0, no output |

On the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs`:
`ℹ tests 481`, `ℹ suites 0`, `ℹ pass 480`, `ℹ fail 0`, `ℹ cancelled 0`, `ℹ skipped 1`, `ℹ todo 0`, `ℹ duration_ms 972.872083` (the skipped one needs a `.venv` on the Mac).
`node --check` on every JavaScript file I edited (`labels.js` after each edit).

New or changed test files: new `tests/media/test_privacy.py` (10), new `tests/picks/test_auto_e2e_launcher_plan.py` (2); changed `tests/media/test_http.py`, `test_web.py`, `tests/editor/test_retime_route.py` (+4 tests), `tests/ops/test_undo_log.py` (+3), `tests/picks/test_auto_job.py` (+1), `test_auto_runners.py` (+2), `test_auto_workspace.py`, `tests/title/test_title_job.py` (+1), `test_title_routes.py`, `test_title_storyboard.py`, `tests/output/test_shotwords.py` (+1), `shotsentence_parity.test.mjs`, `fixtures/shot_cases.json`, `tests/editor_frontend/picksrows.test.mjs`, `shotsentence.test.mjs`, `shotlist.test.mjs`, `title.test.mjs` (+3), `tests/picks/picks_logic.test.mjs` (+1), `tests/e2e/picks_auto/launch_picks_auto.py`, `websearch_proof.py`.

The snapshot `D:\code\behind-the-image\run\snap-fixes3\` is still there (`tools/deploy/snapshot_rm.sh fixes3` removes it); nothing else on the server was written.
