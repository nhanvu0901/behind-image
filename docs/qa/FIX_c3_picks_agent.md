# C3 picks: an agent that chooses the pictures of step 4 ("Để agent chọn hình") (worker c3picks)

Brief: `.scratch/agy_tasks/c3picks/TASK.md`. Design: `docs/design/2026-11-18-agent-first-design.html` ("Bước 4 mới: Chọn hình", "Agent chọn hình làm việc thế nào"). The code is
`bti/picks/auto/` (modules below), the briefings of the agent are `skills/picks_auto/PLAN.template.md` and `CHOOSE.template.md`, the route is in
`bti/editor/picks_api.py` (`POST` and `GET /api/projects/{pid}/picks/auto`), the page is `bti/editor/static/js/views/picks_auto.js` with the pure decisions in
`views/picks_logic.js`. No real model was called, no real request left a test; the only real requests are the six searches of section 11.

## 1. What it does

One long job (kind `picks`, so one at a time with the suggestion and clip jobs of the same project), four parts, each a part of the job in the shared runner
(progress, cancel, resume):

| Part | Who | Output |
|---|---|---|
| 1 `plan`: "Lập danh sách hình cần tìm (1/4)" | agent in a work folder | `out/plan.json` -> `cache/picks_auto/plan.json` |
| 2 `search`: "Tìm hình (2/4)" | code | `cache/picks_auto/search.json` (candidates, thumbnails in `thumbs/`) |
| 3 `choose`: "Chọn hình (3/4)" | agent in a work folder | `out/choice.json` -> `cache/picks_auto/choice.json` |
| 4 `write`: "Ghi vào chọn hình (4/4)" | code | typed operations, in batches |

Modules: `inputs.py` (what is read, the refusals), `shapes.py` (the two files, the check, the rules), `workspace.py` + `helper.py` + `images.py` (the work folder, `./check`,
`./crop`, contact sheets), `session.py` (one agent session, both runners, the limits), `search.py`, `write.py`, `job.py` (the parts, resume, start, `escalate`, the overview),
`store.py` (the cache folder), `texts.py` (every Vietnamese sentence the server makes). The job never approves, never calls the paid suggestion service (a test scans the
package for any way into it, and every test runs with all of them trapped), and writes only through `bti.ops`.

## 2. The shapes of the two output files

`out/plan.json` (`bti.picks.plan/1`), written by the agent, checked by `./check` and by the job with the same function (`shapes.check_plan`):

```json
{"schema": "bti.picks.plan/1",
 "regions": [{"name": "HEAD", "box": [0.10, 0.05, 0.30, 0.25], "what": "Khuôn mặt"}],
 "lines": [{"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "show": [
     {"type": "whole"},
     {"type": "detail", "region": "HEAD"},
     {"type": "context", "search": "Jan van Eyck portrait", "alt": ["van Eyck self portrait"], "kind": "portrait", "what": "Chân dung họa sĩ"},
     {"type": "map", "place": "Bruges, Belgium", "what": "Bản đồ Bruges"},
     {"type": "clip", "search": "canal boat", "what": "Kênh đào", "seconds": 6}]}]}
```

`box` is `[x0, y0, x1, y1]` in fractions of the painting (so it does not depend on the scaled copy the agent looks at; at least 0.02 on each side, at most 90% of the
painting). A line has 0 to 3 pictures; `"show": []` means nothing new. `kind` is `work|portrait|document|photo|place|other` (it picks the sources). Every target line must
have exactly one entry. `reason` is Vietnamese (the check refuses a reason with no accented letter), `search` is English words. Errors are listed with their place
(`lines[3] (b0007): ...`); `NOTE` lines say what the program changes by rule (second clip in a chapter dropped, clip on a painting line dropped, clip cut to 4 to 10 s,
alternatives beyond two ignored, an unused region dropped); `WARNING` lines are the pacing warning (the same framing for more than about 30 s of narration; it never blocks).
At most 30 pictures from elsewhere and 20 boxes per plan.

`out/choice.json` (`bti.picks.choice/1`):

```json
{"schema": "bti.picks.choice/1",
 "wants": [{"id": "b0003.1", "pick": 2, "reason": "Bản chụp chính bức chân dung, rõ nét."},
           {"id": "b0005.1", "pick": null, "reason": "Cả sáu hình đều là bản đồ của vùng khác."},
           {"id": "b0009.1", "pick": "B3", "reason": "Hình trong sách của bạn."}],
 "regions": [{"name": "MIRROR", "action": "keep", "reason": ""},
             {"name": "HEAD", "action": "adjust", "box": [0.08, 0.04, 0.32, 0.28], "reason": "Nới khung để thấy cả đầu."},
             {"name": "SKY", "action": "drop", "reason": "Khung không trúng bầu trời."}]}
```

A want id is `<line>.<n>` (the n-th picture of the line). `pick` is the number on that want's own contact sheet, `"B<n>"` for a picture of the owner's books (one numbered
set shared by all wants), or `null`. Every wanted picture shown and every box shown must be decided.

## 3. One work-folder session or two

**Two separate sessions** (plan, then choose), not one process kept open for a second message. Why:
1. Between them there is the search, which runs code and the network and can take minutes (a source that says "wait", up to 30 wants, thumbnails). A session kept open that
   long holds an agent process and its quota for nothing, and the draft agent's own repair round (same process, same conversation) is made for seconds, not minutes.
2. Each session has its own limits (time, steps, one repair round) and its own focused folder: the second needs the contact sheets and the crops, not the first session's context.
3. Resume is by files: a cancelled or failed run keeps the plan and the search, and a different agent can take over after a quota failure ("Chuyển sang ... và chạy lại")
   without losing part 1. A kept-open conversation cannot be resumed (Claude Code keeps no session on disk by design, `--no-session-persistence`).
4. The runner allows one agent run at a time (`agy.LOCK`); two short runs release it between them.
The price is that the second session does not remember why the plan wanted a picture: the plan's `what` and the line's text and reason are in its inputs (`inputs/wants.json`).

## 4. The limits (a run that never ends)

Per session: **20 minutes** (the runner's own watchdog, which ends the process tree), **80 steps** (tool calls; counted from the runner's events, the tree is ended when the
count passes the limit), **one repair round** (the repair message goes into the same conversation, as the draft agent's does). All three are in the job's `meta.limits`, in
`GET .../picks/auto` (`limits`), in the briefing the agent reads, and the first two are in the progress line: `Lập danh sách hình cần tìm (1/4) - Agent đang lập danh sách hình:
bước 12/80, 3/20 phút.` Around them: part 2 (search) at most 10 minutes, part 4 (write) at most 25 minutes (the runner's own limit per part is 35), at most 150 lines, 30 wanted
pictures and 20 boxes per job, 6 candidates per wanted picture, 3 queries per wanted picture. A session that ends on a limit (or a timeout, or an error) still has its file used
when the file passes the check (a valid plan or choice is complete: the check wants every line and every wanted picture); otherwise the part fails with its sentence
(`picks_auto_limit`, `agy_timeout`, `picks_auto_no_output` ...). A part that stops on its time budget lists what it did not do (`time_up`) and a new start resumes.

## 5. What the task files say a good choice is (quoted)

`skills/picks_auto/PLAN.template.md`, section 5:
- "**A line about the painting shows the part it speaks of.** If the sentence names a mirror, the line shows the mirror (a box on it) ... Never a detail the sentence does not mention."
- "**A line about something outside the painting shows something other than the main painting.** ... Ask for a picture of *the thing itself* ... Do not fill a context line with the main painting because it is easier."
- "**Ask for the work itself, not for pictures about it.** ... A public-domain scan or photograph of the work is what you want; an illustration, a diagram or a page of commentary about it is a poor second."
- "**A map only when the line is about *where*.** ... A line that merely mentions a city in passing does not."
- "**The same framing does not stay on screen for more than about half a minute of narration** ... When several lines in a row would show the same thing, vary".
- "**Nothing invented, and what you cannot ask for is simply not asked for.**" and rule 5: "Names of people, works, places and dates in your search words must come from the line, the dossier or the facts."
- Clips: "a clip only on a context line ... at most one clip per chapter ... 4 to 10 seconds ... only for something that stock footage can show ...; never for a specific historical event or a work of art. Prefer none."
- Section 6 (boxes): "Check every box you propose with a crop and look at the crop before you write it into the plan."

`skills/picks_auto/CHOOSE.template.md`, section 3:
- "**Does it show the thing itself?** The named work, the named person, the named place, the named document, not something near it."
- "**Prefer a public-domain reproduction of the named work** (a photograph or high-quality scan of the work itself ...) **over illustrations or pictures about it.**"
- "**A flagged picture** ... is a last choice: pick it only if nothing unflagged shows the thing, and say so in the reason."
- "**A picture of a place** must be that place ... **A map** must be a map of the place the line means." "**A clip** must show what the line is about, not just something moving".
- "**Never use the main painting itself** (a full view of it) for a context line".
- "**When you are not sure**, answer `null`" and rule 5: "Never pick a picture you are not sure shows what the line says. ... A wrong picture on screen is worse than a line the owner fills in by hand".
- Boxes: `keep`, `adjust` (checked first with `./crop`), `drop` ("The lines that use it then show the whole painting instead."), "Never keep a box you have not looked at."

## 6. What the search part asks each source (part 2, code only)

The free sources the app has, through `bti.picks.service.search` (one source at a time, so a wait is per source), keyless ones first; Pexels and Pixabay only when their key is set.
The paid suggestion service and the paid video search (You.com, YouTube moments) are never called.

| Wanted picture | Sources asked | Query |
|---|---|---|
| context, `work` / `portrait` / `document` | Wikimedia Commons, The Met | the plan's `search`; each `alt` only while fewer than 3 candidates were found (first query asks 6 results of a source, an alternative 4) |
| context, `photo` / `place` | Commons, Pexels, Pixabay | same |
| context, `other` | Commons, The Met, Pexels, Pixabay | same |
| map | OpenStreetMap (Nominatim, one place) | the place name |
| clip | Pexels, Pixabay, Commons, searched as VIDEO | the plan's `search` (a pasted YouTube link and the You.com moment search are not used) |
| the owner's books | not searched (a book has no captions): its embedded pictures of at least 250 px, up to 24, are offered as one numbered set B1.. | |

Up to 6 candidates are kept, taken from the sources in turn; each gets a thumbnail (one download of the card's small picture, cached in `cache/picks_auto/thumbs/`, never an
original); a candidate whose thumbnail cannot be had is dropped (the agent can only choose what it saw); a candidate that is the main painting itself (found in the project's
index) is dropped. A source that says "too many requests" is left alone for the time it states for the rest of the run (`bti.media.http` already keeps the host quiet; the
wants that depended on it are `limited`, with the wait in plain words), nothing waits for minutes, and a resumed run asks again once the wait is over.

## 7. How the writes map to operations (part 4)

Pictures are downloaded first, outside any lock, one by one (`bti.picks.service.fetch_asset`; a refusal sinks only that picture). Then, with `actor: "agent:<model id>"`
(for example `agent:agy:gemini-3.8-flash-high`, `agent:claude:claude-opus-5-5@high`) and a `note`:

| Batch | Operations | Note |
|---|---|---|
| regions (one) | `set_region` for each box kept or adjusted (box -> centre and radii in pixels of the stored picture; a name already there with the same place is reused, another place gives `NAME_2`; never overwritten) | "Agent chọn hình: N vùng chi tiết trên tranh chính" |
| one per chapter | `import` with a `ref` for each picture the chapter uses, then `set_picks` (`reason` = the line's reason; each item `asset`, `region`, `role`, `note`) or `skip_beat` (a line that needs nothing new) | "Agent chọn hình: chương <tên>, N đoạn" |

Roles: whole painting `main`, a box `detail`, a found picture `context` (`document` for kind document), a map `map`, a clip `video`. A line with only some of its pictures is written with those, its note
ends "Chưa tìm được: ..." and the result lists what is missing; a line with none is left as it was and listed. A batch the document refuses is retried line by line, and a stale revision
(the owner saved meanwhile) is read again once. Every batch is a record of the change log (`GET .../changes`) and the newest 50 can be undone (`POST .../changes/{batch}/undo`).

## 8. The page

The bar `#pk-auto` between the top bar and the three columns: "Agent chọn hình", the agent select of the step `picks` (the same select as steps 2 and 5), the button **Để agent chọn hình**
(works on the lines without pictures; asks first when every line is settled or the picks are approved, because it then replaces pictures), while it runs a progress bar with the line of the
part and its limits and **Dừng**, at the end the sentence ("Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp."), what was made, the list of lines without a picture with the plain reason,
and **Chọn lại phần còn thiếu** (the job for exactly the lines without pictures). A failed job says why in one sentence; a quota failure shows the draft's message with its one button. Under the
pictures of a line: "Agent: <reason>" while the line is still as the agent wrote it (its note is the reason; the owner changing the note ends the tag). The state answer lists `picks.auto`
(`long_job`, `uses_model`, `cost: {kind: model, about: about 20 minutes}`, `agent`), before `picks.approve`; `bti.picks.auto.escalate(pid, pdir, beat_ids, note=...)` is the plain function for the
prompt box of step 4 (it works on exactly those lines, with `redo`, and puts the owner's words in the briefings).

## 9. Decisions where the brief was silent

1. **Two sessions** (section 3).
2. **Clips** come from the free sources' video search, not from YouTube or You.com (the brief forbids the paid service and the existing YouTube moment search is the paid one). A search card carries no duration,
   so the "4 to 10 seconds" rule is applied to what the plan asks for (cut to the rule, with a NOTE) and to the item's note ("clip khoảng 6 giây"); the clip is imported whole (the storyboard draft decides how long it
   is shown). "A clip on a painting line" means a line that shows the whole painting or a box of it.
3. **"Nothing new (the previous picture stays)"** is `skip_beat` (the line shows the main picture again, which is what an empty line already does in the draft); it counts as done, not as missing.
4. **A line with some pictures found** is written with them and counted done; what is missing is in its note and in the result (`missing`). Only a line with nothing is "chưa có hình phù hợp".
5. **Approved picks**: refused (`picks_approved`, 409) unless `redo`; with `redo` the first batch that changes anything drops the approval (as any save does; a batch that changes nothing leaves it), so the picks must be approved again. The page asks before it sends `redo`.
6. **The main painting is required** (`picks_no_main`): the design's mock lists the action while the page says "chưa chọn tranh chính"; I refuse, because the plan needs the painting to look at.
7. **Boxes are fractions of the painting** (not pixels, not the draft's scale), and a region is the ellipse whose bounding box is the box. Region names are CAPITALS_AND_DIGITS; a name already there is never overwritten; a dropped box shows the whole painting.
8. **Languages**: search words English; `reason` and `what` Vietnamese (the owner reads them), and the check refuses a reason without a single accented letter.
9. **Pacing** (the same framing for more than about half a minute, with `show: []` continuing the framing before) is a WARNING, not an error: a model that cannot fix it should not fail the job.
10. **Resume** is keyed on the request (narration revision, main painting, the lines the request covers, `redo`, the owner's words), not on the lines still left, so a run cancelled in the write part resumes with its plan and choice; the choose part runs again when the search found something new since its file was written.
11. **A session that ended on a limit, a timeout or an error still counts** when its file passes the check.
12. **The job shares the kind `picks`** with the suggestion and clip jobs (one at a time per project); the stepper says "Agent đang chọn hình." while it runs.
13. **State**: `picks.auto` is listed before `picks.approve`, `advances` only while no line has pictures, and its example body has `redo: true` when every line is settled or the picks are approved (so the body is valid as it stands). I changed `tests/state/test_state.py` (the exact lists of ids and the stand-in for the starter) because of it: the file is outside the list in the brief.
14. **The picks document has no "written by" mark**, so the reason of a line is its `note` (set by `set_picks`' `reason`) and the page shows "Agent: ..." only while the note equals the reason in `cache/picks_auto/last.json` (cumulative over runs).
15. **A line the owner fills while the job runs** is left alone (`lines_by_others` in the result) unless `redo`; a narration or main painting that changes meanwhile ends the job with `picks_auto_stale` and writes nothing.
16. **The `claude` runner** got one optional argument, `allow=` (`build_command` and `run`), so that this job names its own two helper commands (`./check`, `./crop`) instead of the draft's three; the default is the draft's, a test pins that. The Windows form (`.\check.cmd`, `.\crop.cmd`) is covered.
17. `picks.css`: the page root had two grid rows; it has three (the bar is the middle one). `docs/AGENT_API.md` was regenerated (`python -m bti.editor.hints`) and has a hand-written section 7. `docs/APP_GUIDE.md` has the part on step 4.
18. The browser probe ships the tree the way the existing probes do (`remote.mjs`: `deploy_windows.sh --pack-only`, which does nothing on the server and takes no lock, then a private temp folder); I did not run a deploy.

## 10. Tests (fakes only; Python on the server snapshot `c3picks`, one folder per run)

New, all in `tests/picks/`: `test_auto_shapes.py` (the two files: errors, notes, warnings, boxes inside and outside the picture, the clip rule, the pacing warning, the cap on wanted pictures, Vietnamese reasons), `test_auto_job.py`
(the whole job from an empty picks document to every line filled, the writes as batches with the agent as actor and an undo, `redo`, a line the owner filled, the refusals, a second start while one runs, a plan with two clips in a chapter and a clip on a
painting line, a box the choose step drops, a want with no candidates, a source that is rate limited (nothing waits for the 2 minutes it asks), a candidate with no thumbnail, an output repaired once, an output that fails twice, a tampered session, a quota failure,
a valid file taken after a limit, and resume after a cancel in each of the four parts), `test_auto_workspace.py` (the work folders, `./check` and `./crop` run as the agent runs them, the contact sheets, the briefings), `test_auto_runners.py` (the REAL runner modules `agy` and `claudecode`
against the draft tests' fake executables: command lines, the two helper commands in the permission rules, the repair round into the same conversation, the step limit and the time limit ending a session that does not end and killing its processes, cancel, tamper, quota, "not installed", and whole jobs through each runner),
`test_auto_search.py` (what each kind of wanted picture asks, the caps, thumbnails, the wait a source asked for, the owner's books), `test_auto_api.py` (the routes, the refusals with `code`/`fix`/`retry`, the state answer). Node: `tests/picks/picks_logic.test.mjs` (+10: the result sentence,
the buttons, the progress line, the reason under a line). The paid service is trapped in every test (`paid` fixture: a call is recorded and raises; the `env` fixture fails the test if one was made), and a test reads the package's syntax tree for any way into it.

The summary lines, exactly as printed (`-q`):

```
tests/picks   : 207 passed, 1 warning in 51.10s
tests/media   : 363 passed in 3.16s
tests/ops     : 468 passed, 1 warning in 104.27s (0:01:44)
tests/state   : 233 passed, 1 warning in 138.23s (0:02:18)
tests/editor  : 481 passed, 1 warning in 238.40s (0:03:58)
tests/draft   : 358 passed, 1 warning in 142.22s (0:02:22)
tests/longjob : 69 passed, 1 skipped, 1 warning in 6.97s
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
              : ℹ tests 352 / ℹ pass 351 / ℹ fail 0 / ℹ skipped 1
```

The skipped node test is the existing `ISSUE_CODES` template check that needs `.venv/bin/python` (not on the Mac); the skipped longjob test was skipped before. Before my files `tests/picks` had 92 tests, now 207. `tests/state/test_state.py` was changed (see decision 13); every other existing test file is untouched.

## 11. The browser probe, exactly as printed

`BTI_SSH_HOST=winbox-cmd node tests/e2e/picks_auto/picks_auto.mjs` (second instance on the server: port 8577, folder suffix `c3p`, the two agents are mock agents with the names of the real two, the agent in a work folder is a fake runner, the sources are fakes;
stopped afterwards: no listener on 8577, the private repo folder removed). Screenshots: `.scratch/stages_ui/shots/picks_auto-01..07-*.png`.

```
PASS the machine default is Gemini 3.8 Flash (the mock agent carrying that name)
PASS the instance carries the demo project and the fakes
PASS the bar is on the page, with the agent select of the step and the button
PASS the select offers the two agents of the step "picks" and shows Gemini 3.8 Flash
PASS the button says "Để agent chọn hình" and can be pressed
PASS "Chọn lại phần còn thiếu" is not there before a run, and the intro says the agent never approves
PASS the six lines are there with no pictures
PASS the bar at rest: no leftovers, no raw words
PASS while it runs the state is "running", the button and the select are locked, "Dừng" is there
PASS the progress line names the part (1/4) and shows the steps and the minutes against their limits
PASS the line "mỗi lượt tối đa 20 phút và 80 bước" is there
PASS a progress bar is drawn
PASS the other buttons that start a job are not offered meanwhile (the agent is working)
PASS the bar while it runs: no leftovers, no raw words
PASS after "Dừng" the bar says so and the button is back
PASS nothing was written to the picks
PASS the job is recorded as cancelled
PASS the progress went through the parts of the design (at least the first one was seen), then the result
PASS the result is one sentence: 5 of 6 lines, 1 without a fitting picture
PASS the second line says what was made (2 new pictures, 2 regions, 1 line that needs nothing new)
PASS "Chọn lại phần còn thiếu" is offered
PASS the line without a picture is named with the plain reason
PASS the result: no leftovers, no raw words
PASS the lines show their pictures: 1, 1, 0, 2, 2 and the last one "bỏ qua" (nothing new)
PASS line 1 shows the whole painting with the agent's reason under it
PASS line 2 shows the region MIRROR of the main painting and its reason
PASS line 3 has no picture and no reason (it was left as it was)
PASS line 4 shows a map and a video clip, and its reason
PASS line 6 needs nothing new: skipped, with its reason
PASS the picks are not approved: the owner stays the one who approves
PASS every write is a batch of the change log with the agent as actor
PASS the fake agent was asked twice for this run: plan, then choose
PASS it runs (the state says so)
PASS and ends with a sentence about the one line it worked on
PASS the button is gone: no line is missing any more
PASS line 3 now has its picture
PASS the picture is the portrait the source found
PASS and the reason
PASS a second plan and choice were made, for ONE line only (the others were not asked again)
PASS after the second run: no leftovers, no raw words
PASS after a reload the last result is still there
PASS and the reasons under the lines
PASS once the owner changes the note, the line is no longer shown as the agent's
PASS and the note was saved
PASS a dialog asks whether to choose everything again (it replaces the pictures)
PASS declining starts nothing
PASS a file that fails the check twice ends with the plain sentence, no raw error
PASS the pictures of the owner and of the earlier run are untouched
PASS after a failed run: no leftovers, no raw words
PASS the state lists picks.auto as a long job that uses a model and costs time, not money
PASS GET .../picks/auto has the last result and the reasons
PASS no failed request in the page (apart from the refusals the checks provoked)

52 pass, 0 fail
```

It presses "Để agent chọn hình", sees the progress line with the limits (`Lập danh sách hình cần tìm (1/4) - Agent đang lập danh sách hình: bước N/80, M/20 phút.`), presses "Dừng" (nothing written), runs to the end (5 of 6 lines, the line that nothing can fill named with its plain reason, lines
filled with "Agent: ..." reasons under their pictures, line 6 "bỏ qua"), presses "Chọn lại phần còn thiếu" (the second run works on ONE line and ends "Agent đã chọn hình cho 1/1 đoạn."), reloads (result and reasons still there), changes a note (the tag goes), starts again with every line settled
(a dialog asks first; declining starts nothing), then a failing agent ("Agent chưa chọn xong: ..."; nothing changed). The first run of the probe (before I made the launcher put its fake sources in after `launch.py` had put its own) had failures that were mine: the Commons and Met fixtures of
`launch.py` answered every query, and the machine default agent was not set; the probe also showed me the middle grid row (`picks.css`), fixed.

## 12. The real searches (6 of the 6 allowed, from the snapshot `c3picks`, `tests/e2e/picks_auto/real_search.py`; no original downloaded)

Run by `tools/deploy/snapshot_py.sh c3picks tests/e2e/picks_auto/real_search.py` through `asearch.run` with the real sources, a three-second pause before every request, the plain User-Agent of `bti.media.http`, queries about the Arnolfini painter and Bruges only. Output as printed
(the thumbnails: the two small pictures of the first candidates, 2 more requests; the Met search asks object by object, 1 + 3 requests):

```
SEARCH 1: source=commons kind=image query='Jan van Eyck self portrait' -> 6 result(s), 0 error(s), 0.8 s
   - File:Portrait of a Man in a Turban (Jan van Eyck) with frame.jpg | Portrait of a Man in a Turban (Jan van Eyck) with  | 1920x2448 | licence=PD | flag=None | author=Jan van Eyck
   - File:Portrait of a Man in a Turban (Jan van Eyck).jpg | Portrait of a Man in a Turban (Jan van Eyck) | 1920x2605 | licence=PD | flag=None | author=Jan van Eyck
   - File:Portrait of a Man by Jan van Eyck-small.jpg | Self-portrait | 1920x2635 | licence=PD | flag=None | author=Jan van Eyck
   - File:Eyck, Jan van - Portrait of a Man (Self Portrait?) - National Gal | Eyck, Jan van - Portrait of a Man (Self Portrait?) | 3840x5233 | licence=PD | flag=None | author=Jan van Eyck
SEARCH 2: source=met kind=image query='Jan van Eyck self portrait' -> 3 result(s), 0 error(s), 1.3 s
   - 436538 | Portrait of a Man | 0x0 | licence=CC0 | flag=None | author=Jan Gossart (called Mabuse)
   - 435897 | Head of Christ (Ecce Homo) | 0x0 | licence=CC0 | flag=None | author=Petrus Christus
   - 435896 | Portrait of a Carthusian | 0x0 | licence=CC0 | flag=None | author=Petrus Christus
THUMB 1: commons File:Portrait of a Man in a Turban (Jan van Eyck)  -> cache/picks_auto/thumbs/3f39bc9b1dafbd49.jpg (0.2 s)
   thumbnail stored at 330 x 421 (the picture the agent would be shown)
THUMB 2: met 436538 -> cache/picks_auto/thumbs/96dfdfa979e3e20f.jpg (0.2 s)
   thumbnail stored at 463 x 625 (the picture the agent would be shown)
SEARCH 3: source=commons kind=image query='Madonna of Chancellor Rolin Jan van Eyck' -> 6 result(s), 0 error(s), 0.8 s
   - File:La Vierge du chancelier Rolin - Jan van Eyck - Musée du Louvre Pe | La Vierge du chancelier Rolin - Jan van Eyck - Mus | 3840x3872 | licence=PD | flag=None | author=Jan van Eyck
   - File:Jan van Eyck 070 Virgin of Chancellor Rolin adj.jpg | Jan van Eyck 070 Virgin of Chancellor Rolin adj | 1920x2054 | licence=PD | flag=None | author=Jan van Eyck
   - File:Jan van Eyck The Virgin of Chancellor Rolin.jpg | The Virgin of Chancellor Rolin | 816x900 | licence=PD | flag=small | author=Jan van Eyck
   - File:Van eyck madonna of chancellor rollin.jpg | Van eyck madonna of chancellor rollin | 717x768 | licence=PD | flag=small | author=Jan van Eyck
SEARCH 4: source=met kind=image query='Madonna of Chancellor Rolin Jan van Eyck' -> 3 result(s), 0 error(s), 0.5 s
   - 436283 | Virgin and Child in a Niche | 0x0 | licence=CC0 | flag=None | author=Jan van Eyck
   - 436102 | Virgin and Child with Four Angels | 0x0 | licence=CC0 | flag=None | author=Gerard David
   - 201375 | Sleeping Cupid | 0x0 | licence=CC0 | flag=None | author=
SEARCH 5: source=osm kind=image query='Bruges, Belgium' -> 1 result(s), 0 error(s), 0.4 s
   - 102016009:13:51.20855:3.22677:Brugge | Bản đồ Brugge | 2400x1350 | licence=ODbL | flag=None | author=© OpenStreetMap contributors
SEARCH 6: source=commons kind=video query='canal boat Bruges' -> 0 result(s), 0 error(s), 0.4 s

WHAT THE SEARCH PART KEPT
w1 context status=found    code=None candidates=6
   n=1 commons | File:Portrait of a Man in a Turban (Jan van Eyck) with frame | Portrait of a Man in a Turban (Jan van E | image
   n=2 met | 436538 | Portrait of a Man | image
   n=3 commons | File:Portrait of a Man in a Turban (Jan van Eyck).jpg | Portrait of a Man in a Turban (Jan van E | image
   n=4 met | 435897 | Head of Christ (Ecce Homo) | image
   n=5 commons | File:Portrait of a Man by Jan van Eyck-small.jpg | Self-portrait | image
   n=6 met | 435896 | Portrait of a Carthusian | image
w2 context status=found    code=None candidates=6
   n=1 commons | File:La Vierge du chancelier Rolin - Jan van Eyck - Musée du | La Vierge du chancelier Rolin - Jan van  | image
   n=2 met | 436283 | Virgin and Child in a Niche | image
   n=3 commons | File:Jan van Eyck 070 Virgin of Chancellor Rolin adj.jpg | Jan van Eyck 070 Virgin of Chancellor Ro | image
   n=4 met | 436102 | Virgin and Child with Four Angels | image
   n=5 commons | File:Jan van Eyck The Virgin of Chancellor Rolin.jpg | The Virgin of Chancellor Rolin | image
   n=6 met | 201375 | Sleeping Cupid | image
w3 map  status=found    code=None candidates=1
   n=1 osm | 102016009:13:51.20855:3.22677:Brugge | Bản đồ Brugge | image
w4 clip status=none     code=no_candidates candidates=0

searches made: 6, thumbnails fetched: 2, limited sources: {}
```

What it shows: for a portrait or a named work Commons gives exactly the right pictures first (public domain, 1920 to 3840 px renditions, `flag` empty, the "small" flag on the two small ones), the Met gives a few related works and some noise ("Sleeping Cupid" for the Rolin Madonna) which the choosing step has to reject; OpenStreetMap
finds the place ("Brugge", the name of the city in the local language, the card title is "Bản đồ Brugge"); a clip search for "canal boat Bruges" on Commons finds nothing (the want is then listed as not found, `no_candidates`); the two thumbnails download in 0.2 s each as small JPEGs (330 x 421 and 463 x 625).
Nothing was limited by a source; the "wait" paths were tested with fakes only.

## 13. What I could not verify (no real model was called)

Only a real run can show: (1) whether Gemini through `agy` and Opus through `claude` actually **open and look at the contact sheets and crops** (`view_file` / `Read` of a `.jpg` in the folder) rather than answering from the text lists; the events of each session are kept in `cache/picks_auto/runs/<time>/*-events.jsonl`;
(2) whether the models follow the briefings (boxes in fractions, accents in the reasons, at most 30 wanted pictures, a context line that is really about something else), how many repair rounds they need, and whether 80 steps and 20 minutes are right for a 28-line video (the progress line shows the steps and minutes used);
(3) the Windows form of the helper commands under `agy` (the `.cmd` wrappers are the draft's form, run here only through `python -m`); (4) the permission rules of `claude` for `./crop --box ... -o look/...` (a test pins the command line, but only the real program says what it refuses; the confinement text tells the agent to carry on when something is refused); (5) the quality of the choice (what the Met noise does to a
sheet of six, whether the agent rejects the wrong pictures); (6) the real import of an OpenStreetMap map (60 tile requests, about 70 s; the write part is limited to 25 minutes in all and cancel waits for the picture in hand) and of a stock video through ffmpeg; (7) how the page reads at the sizes the owner uses (the screenshots are 1700 and the page is not responsive, as before).

**How the coordinator should run the first real one, on a copy of a project:** (a) on the server make a copy of a real project that has an approved narration and a main painting (copy the folder to `projects/<id>-agent`, never touching the original; the narration must be approved in the copy), restart nothing; (b) check the agents first (quotas: the memory
says both Antigravity pools were exhausted on 2026-11-18 and reset about 11-24/25; Claude Code on the server must be signed in with `claude auth login`) with `GET /api/agents` (an agent that cannot run says why); (c) open the copy at step 4 "Chọn hình", choose the agent in the new bar, press "Để agent chọn hình" (or `POST /api/projects/<id>-agent/picks/auto` with `{}`), and watch the progress line; (d) afterwards read
`cache/picks_auto/plan.json` (`notes` and `warnings` say what the program changed or noticed) and `search.json`, look at the lines and the reasons, then `GET .../changes` and undo a batch to see it go back; (e) if a session fails, its work folder stays in the server's temp folder as `bti-picks-*` (inputs, the agent's `out/`, its `look/` crops) and the transcript is in `cache/picks_auto/runs/`;
send those two to whoever tunes the briefings. Run it with the cheaper agent first (a small video, `beats` naming one chapter) before a whole video.

## 14. Needs another worker / for the coordinator

- The prompt-box worker: `bti.picks.auto.escalate(pid, pdir, beat_ids, note="...", model=None)` starts the job for exactly those lines (it sets `redo` and puts the owner's words in the briefings); it answers the job's record or raises `AutoError(code, message, status, **extra)` (the codes of section 9 and `docs/AGENT_API.md` section 7). I did not touch their part.
- The restyle of step 4: my bar is self-contained (`views/picks_auto.js`, `#pk-auto`, the block marked c3picks at the end of `picks.css`, the middle row of `.pk-root`); `picks.js` has six small marked edits (import, `auto` variable, the bar's host in `BAR`, `autoWhy` under the tray, the suggestion tab ignoring this job, the note input removing the tag).
- `tests/state/test_state.py` was changed by me (decision 13); `docs/OPS.md` is untouched (no operation was added or changed).
- Left on the server, not deleted by me (the rule on deleting): three work folders `bti-picks-*` and the launcher's `bti-picks-auto-choices.json` in the server's temp folder (the failing-agent step of my three probe runs keeps its work folder for inspection, as the draft does; the app's own `workspace.clean_old()` removes `bti-picks-*` older than two days), a folder `c3picks-real-*` inside my snapshot `run\snap-c3picks\` (the six real searches; `tools/deploy/snapshot_rm.sh c3picks` removes the whole snapshot), and the snapshot itself.
- Not done, on purpose: no approval of any kind; no change of the storyboard draft (`bti/draft/` is untouched except the one optional argument of `claudecode.py`); no installs.

## 15. Files

New: `bti/picks/auto/` (`__init__`, `images`, `helper`, `inputs`, `job`, `search`, `session`, `shapes`, `store`, `texts`, `workspace`, `write`), `skills/picks_auto/` (`PLAN.template.md`, `CHOOSE.template.md`), `bti/editor/static/js/views/picks_auto.js`, `tests/picks/auto_*.py` and `test_auto_*.py`, `tests/e2e/picks_auto/` (`launch_picks_auto.py`, `picks_auto.mjs`, `real_search.py`), this report.
Changed (small, local): `bti/editor/picks_api.py` (the two routes), `bti/editor/state_api.py` (the action, one builder, three lines in `_load_picks`/`Ctx`), `bti/editor/hints.py` (six codes), `bti/picks/__init__.py` (the stepper's sentence while the agent works), `bti/draft/providers/claudecode.py` (the optional `allow=`),
`bti/editor/static/js/{labels,errmsg}.js` (blocks marked `c3picks`), `views/picks.js`, `views/picks_logic.js`, `css/picks.css`, `docs/AGENT_API.md` (regenerated + section 7), `docs/APP_GUIDE.md` (the part on step 4 and the files table), `tests/picks/picks_logic.test.mjs`, `tests/state/test_state.py`.
