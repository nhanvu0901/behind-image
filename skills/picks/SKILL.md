---
name: bti-picks
description: Step 4 of Behind the Image, the pictures (the main painting, its regions and the pictures of each narration line). Use when `bti status <project>` shows the step `picks` as current.
---

# Step 4: the pictures (picks)

Read `AGENTS.md` first (the rules, the exit codes). This document is for the step `picks`.

## Goal

Decide, for every line of the approved narration, which picture is on the screen while it is spoken: the whole main painting, a named detail of it, or a picture from elsewhere. At the end the owner (or you,
if the owner allowed it) approves the picks, and the storyboard draft starts from them.

## What it needs and what it gives

- Needs: the narration approved. It can be worked while the voice (step 3) runs.
- Gives: `picks.json`: the **main painting** (`main_asset`), the pictures imported into the project (`assets`, each with its source, author and licence), the **regions** of each picture (a named spot with a centre and a radius, in pixels of the stored file) and, per narration line, the list of pictures
  with a `role` (`main`, `detail`, `context`, `compare`, `document`, `map`, `video`). A line with no picture shows the main painting again. The pictures agent also writes, per line, `kinds` (what the line does: one or two of
  `detail`, `whole`, `outside`, `compare`, `journey`, `dates`, `figure`, `inscription`, `construction`, `relations`, `idea`) and `missing` (`[{what, code}]`: the pictures it asked for and did not find); both are absent in a document made before.
- Unlocks: the storyboard draft (step 5), together with the voice.

## The actions and operations it uses

<!-- BEGIN GENERATED: actions -->
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `picks.search` | picks | Tìm hình |  |  |  |
| `picks.import` | picks | Nhập hình |  |  |  |
| `picks.import_book_image` | picks | Nhập hình từ sách |  |  |  |
| `picks.import_clip` | picks | Cắt clip video |  | machine_time: about 1 minute | yes |
| `picks.suggest` | picks | Gợi ý hình (tốn tiền) |  | paid: You.com calls, charged per beat | yes |
| `picks.put` | picks | Lưu chọn hình |  |  |  |
| `picks.auto` | picks | Để agent chọn hình |  | model: about 20 minutes | yes |
| `picks.retry_missing` | picks | Tải lại hình đã chọn |  |  | yes |
| `picks.edit` | picks | Nhờ agent sửa chọn hình |  | model: about 30 seconds | yes |
| `picks.ops` | picks | Sửa chọn hình |  |  |  |
| `picks.approve` | picks | Duyệt chọn hình | yes |  |  |
| `picks.cancel` | picks | Dừng |  |  |  |
<!-- END GENERATED: actions -->

Send operations with `bti ops <project> picks --file ops.json [--dry-run]`: the file is a JSON list of operations (or an object with `ops`, `scope`, `note`); the command reads the current
revision itself, a refused batch writes nothing, and every batch can be undone (`bti undo`). `bti schema ops picks` prints each operation with its fields and an example; the operations are:

<!-- BEGIN GENERATED: ops -->
| operation | what it does |
|---|---|
| `set_main` | Choose the main picture (the whole painting) of the video. |
| `set_region` | Set (add or replace) a named region of an asset: a point, with an optional radius, in pixels of the stored picture. |
| `remove_region` | Remove a named region of an asset (the pictures of a line that use it must be changed in the same batch, before this operation). |
| `set_picks` | Replace all the pictures of one narration line (use skip_beat to show the main picture instead). |
| `add_pick` | Add one picture to a narration line, at the end or at a position. |
| `remove_pick` | Remove one picture of a narration line, by its position among the pictures of the line (counting from 0, as the earlier operations of the batch left them). |
| `skip_beat` | Make a narration line show the main picture again (it keeps no pictures of its own). |
| `import` | Bring one found picture into the project (the same sources and code path as POST .../picks/import and .../picks/import-book-image). Imports run first, before anything is written; a dry run only checks the shape. Videos are cut by the long job, not here. A download is polite and patient (one request a second to a host; a refusal of "too many requests" is waited for, up to about six minutes before the error `source_rate_limited`): send a batch with an import with a long timeout. |
<!-- END GENERATED: ops -->

Pictures come from `picks.search` (the answer lists the `source` and `source_id` of each candidate) and are brought in with `picks.import`
(`--set source=commons --set source_id=... --set as_main=true` for the main painting), `picks.import_book_image` (a picture of the project's books) or the `import` operation inside a batch (it gets a
`ref`, and the later operations of the batch name the new picture as `$ref`). A clip is cut from a link by the long job `picks.import_clip` (`--set url=... --set start=12 --set end=19`). The paid suggestion
(`picks.suggest`) is never yours: the owner starts it on the page.

## Let the agent choose first, then correct with the request box

For a whole video the quickest way is to let the pictures agent choose first and to correct what it chose afterwards. `bti do <project> picks.auto --yes-cost --wait` plans what each line needs, searches the free picture
sources (never the paid suggestion), looks at the candidates and writes the choices as batches whose actor is the agent (it takes about twenty minutes; the answer says `Agent đã chọn hình cho 25/28 đoạn.`). It first says what each line does
(`kinds`): a line about a person, a place, an object, an event or a custom that is not in the painting asks for a picture of the thing itself, and when none is found the line shows the part of the painting its plan named (its fallback) and
lists what was not found in `missing` (in the result and in the line's `missing`), so nothing is lost silently; a line of an older plan with nothing found is left as it was and listed in `lines_without`. Name lines with `--set beats='["b0003","b0004"]'` to work on those only. It works on the lines that have no pictures; once every line has pictures, or the picks are approved, it needs `--set redo=true`
(refused as `picks_nothing_to_do` or `picks_approved` otherwise: the approval is dropped when it changes anything, so approve again after). It never approves.

The agent looks things up on Wikipedia first (free). The owner may also have switched on **the web search** ("Tìm hình trên web khi chọn hình tự động", `bti status` shows the extra cost as `up to N web searches`): then a line whose picture the
free sources do not have is searched on the web (You.com, paid, at most N searches a run) and one more short choosing session looks at the new candidates only. That switch is the owner's: `PUT /api/settings/web-search` from an agent is refused
(exit 3), and with it off nothing paid is ever called. The result's closing sentence then says how many web searches the run made, and a line that could not be searched for lack of budget is listed with the code `web_budget`.
Pictures found on the web have an unknown licence (`flag: unknown`): they show on the page flagged, for the owner to look at.

Then correct with `picks.edit` (the request box): one model call, about half a minute, `bti do <project> picks.edit --yes-cost --wait --set instruction="the first line shows only the face" --set scope='{"beats":["b0001"]}'`. It rearranges, adds and removes
pictures and regions the project already has, in one batch you can undo. It cannot import or look: when the job's result says `escalate` the request needs a picture the project does not have, so choose it with `picks.auto` for those lines, or search by hand (`picks.search`, `picks.import`).
The page's card does this in one click (the button "Để agent chọn hình" on the turn). A voice, a draft, a prompt-box turn and the agent's choice of pictures run one at a time on a project: while one runs the other is refused (exit 5, `agent_job_running` or `no_running_job` in `bti status`): wait for it
(`bti job <id> --wait`), then send yours. Both cost a model call: `--yes-cost` only when the owner asked for this work, and exit 3 (`spend_not_allowed`) when the owner did not allow model spending for the project.

**When a picture the agent chose could not be downloaded.** A source (Wikimedia Commons most often) may answer "too many requests". Every download is polite and patient (one request a second to a host, and a refusal is waited for: what the host asks, else
10, 30, 90 seconds, three times), so a download can take minutes: give a command that sends an `import` `--timeout 300`. When a picture is still refused, the line is written with its fallback and `missing` holds `{what, code: "import_limited"}` (the rest of that
source's pictures are listed the same way, without a request). Finish such a run with `bti do <project> picks.retry_missing --wait` (no model, no cost, no search): for each such line it reads the picture the agent chose from the saved files of the run, imports it
and writes the line again the way `picks.auto` would have (one batch per line, undoable); a line the owner changed meanwhile is left alone, a line whose source still refuses stays listed (`lines_still_limited`: call it again later), and a `web_budget` is not
retried here (that needs the paid search: `picks.auto` for those lines). It is listed in `bti status` only while a line says `import_limited`; `picks_saved_files` in its `needs` means the saved files of the run are gone: choose again with `picks.auto --set redo=true`.
An automatic run takes it once, before the pictures gate.

An automatic run (`bti run`) takes `picks.auto` by itself as one of its steps (and `picks.retry_missing` once after it), and at the picks gate it lets flagged pictures pass and stops only when more than a quarter of the narration lines have no picture, or when more than 34% of the lines about something
outside the painting (`outside_no_picture`: the picture of the thing itself was not found, the line shows only the main painting) are in that state (it says how many have none at its end, and the stop lists the lines); while it goes on, a hand-started `picks.auto`, `picks.edit` and `draft.edit` are refused (`agent_job_running`, exit 5): wait for it (`bti job <id> --wait`).

## A worked session

Fixture project `ops1` (a project with a narration of six lines and four pictures; the examples of `docs/OPS.md` are written for it). `bti ops ... --dry-run` checks a batch and writes nothing.

```text
# fixture: ops
$ bti schema ops picks
operations of the picks (send them with: bti ops <project> picks --file ops.json):
  set_main: Choose the main picture (the whole painting) of the video.
    required: asset
    example: {"op":"set_main","asset":"B"}
...
(bti schema ops picks --json gives every JSON Schema)
$ cat > ops.json <<'EOF'
[{"op": "skip_beat", "beat": "b0004"},
 {"op": "set_picks", "beat": "b0005", "items": [{"asset": "B", "role": "context"}], "reason": "the room"}]
EOF
$ bti ops ops1 picks --file ops.json --dry-run
dry run: nothing was written; 2 operation(s) applied; revision <rev>
changes:
  0:42   Đoạn 4: dùng lại tranh chính
  0:59   Đoạn 5: thay 1 hình
$ bti ops ops1 picks --file ops.json
batch batch_0001 written; 2 operation(s) applied; revision <rev>
changes:
  0:42   Đoạn 4: dùng lại tranh chính
  0:59   Đoạn 5: thay 1 hình
undo: bti undo <project> batch_0001
$ bti changes ops1 picks
batch        doc         actor                 time                 note
batch_0001   picks       cli:bti               <time>
    0:42   Đoạn 4: dùng lại tranh chính
    0:59   Đoạn 5: thay 1 hình
$ bti undo ops1 batch_0001
undone batch_0001; the undo is batch batch_0002; revision <rev>
  0:42   Đoạn 4: trở lại như trước khi sửa
  0:59   Đoạn 5: trở lại như trước khi sửa
$ bti approve ops1 picks
a person is needed: gate_needs_human (HTTP 403)
  detail: The picks gate can only be approved by the owner: automatic running is off for this project.
  fix: Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate (the switch on the page, PUT /api/projects/ops1/auto), then call again.
(exit 3)
```

## What a good result is

- **The main painting first.** Choose it before anything else (a picture of the whole work, as large as the source gives: the app keeps Wikimedia pictures at up to 3840 pixels wide). A licence flag ("restricted", "unknown", "small") never refuses a picture; the source and licence are kept for the video description.
- **Regions where the narration names a detail.** A line that points at the mirror, the hands or a signature shows the main painting with that region (`set_region`, then `role: detail` and `region` in the item). Place a region on what its name says: look at the picture.
- **Context lines need other pictures.** A line about a person, a place, a document, another work or a technique outside the painting needs a picture other than the main painting (`context`, `document`, `map`, `compare`), with its `role` set. A picture of the right kind of thing is better than the painting held for the whole line. `GET .../picks` warns `outside_no_picture` for each line whose `kinds` hold `outside` or `compare` and that shows only the main painting, and says `outside: {lines, with_picture, without: [beats]}`; a place that is merely mentioned wants a view of the place, a map is for a journey between two or more places. `set_picks` and `skip_beat` take `kinds` and `missing` too (an edit of the pictures keeps them unless it sends new ones; `[]` takes them away).
- **No pictures is a choice.** A line with no pictures shows the main painting again and the draft moves the camera over it; that suits lines that talk about the work in general. A line you do not want counted as missing is `skip_beat`.
- **Clips are rare.** At most one clip per chapter, 4 to 10 seconds, only for a context line, cut from a link with `picks.import_clip`; a video can never be the main painting.
- **Never invent.** A picture, a place or a name you cannot source is left out; the line stays on the main painting.
- **Check before the gate.** The approval needs the main painting, no missing file, no unknown picture or region, and the narration still approved. Run `bti status <project>`: `picks.approve` is ready when these hold.

## The refusals you will meet

| code | what to do |
|---|---|
| `picks_no_main`, `main_asset` | There is no main painting: import one (`picks.import` with `as_main` true) or `set_main` in a batch. |
| `picks_have_errors`, `picks_errors` | Read `issues` of `GET /api/projects/{pid}/picks` (a missing file, an unknown asset or region) and fix them. |
| `unknown_asset`, `unknown_region`, `unknown_beat`, `invalid_field` | The batch names something that does not exist: the refusal lists `allowed` and the path of the field (`ops[1].items[0].asset`). Fix that field, or import the picture / add the region first (in the same batch, with a `ref`). |
| `source_rate_limited` (exit 5) | A picture source asks for fewer calls (the app already waited and tried three times): wait `retry_after` seconds (about a minute) and send again; do not loop. For the pictures the agent chose, `picks.retry_missing` sends them again from the saved files. |
| `retry_nothing_to_do`, `retry_no_files` | `picks.retry_missing` needs a line whose `missing` says `import_limited` and the saved files of the last run (`cache/picks_auto`): without them choose again with `picks.auto` (`redo` true). |
| `source_unreachable`, `source_unavailable`, `source_timeout` (exit 5) | The service did not answer: try again in a minute, or take another source. |
| `import_failed`, `source_error`, `image_too_small` | Choose another picture or another source; nothing was written. |
| `video_not_main` | A clip cannot be the main painting: choose an image. |
| `stale_revision` (exit 5) | The picks changed under you: send the command again (it reads the new revision). |
| `agent_job_running` (exit 5) | Another agent job of the project runs (the agent's choice of pictures, a prompt-box turn or a draft): `bti job <id> --wait`, then send yours. |
| `picks_approved`, `picks_nothing_to_do` | `picks.auto` works on lines without pictures: name `beats` and send `redo` true to choose lines that already have pictures (an approved picks needs `redo`, and approving again after). |
| `narration_not_approved` | The narration is not approved (or changed): step 2 first. |
| `confirm_required`, `spend_needs_human`, `spend_not_allowed` (exit 3) | A paid call is the owner's: stop and ask. |
| `gate_needs_human` (exit 3) | The owner has not allowed you to approve this gate: stop and ask. |
