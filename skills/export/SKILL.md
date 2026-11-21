---
name: bti-export
description: Step 6 of Behind the Image, the export (the finished video, its description and chapters). Use when `bti status <project>` shows the step `export` as current.
---

# Step 6: the export

Read `AGENTS.md` first (the rules, the exit codes). The export is the last and the second most expensive step: about 25 minutes of the server's machine time for a 12-minute video (about 2 minutes per minute of video).

## Goal

The finished video as one MP4, with a check sheet, a description that lists the chapters, the books used and the source and licence of every picture, and the chapter list.

## What it needs and what it gives

- Needs: the storyboard approved and still matching (gate `storyboard`), the audio mix and `timing.json` of the voice.
- Gives: the files of `export/` (the video, the check sheet with the length, the number of frames, the loudness and the chapter list, the description, the chapters), a manifest the page reads. Read them with `GET /api/projects/{pid}/export` (the answer lists `files` with their `url`).
- No subtitles are made: the narration is never burned into the picture; labels and annotations of the storyboard are kept.

## The actions it uses

<!-- BEGIN GENERATED: actions -->
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `export.start` | export | Xuất video |  | machine_time: about 25 minutes | yes |
| `export.cancel` | export | Dừng |  |  |  |
| `auto.run` | export | Chạy tự động |  | machine_time: the sum of what it may start from where the project stands | yes |
| `auto.cancel` | export | Dừng |  |  |  |
| `output.build` | export | Ghi thư mục output |  |  |  |
<!-- END GENERATED: actions -->

The export is rendered in ~60-second parts cut at shot starts and joined at the end. Each part is keyed only by what decides its frames (the shots and overlays playing inside it, their assets and regions, anchored word times, style, fps, width, quality, and `RENDER_VERSION` — not the whole storyboard revision). Cancelling (`bti job <id> --cancel`, or the `export.cancel` action) keeps the finished parts; starting again goes on from there, also after a server restart.
If you make a small edit to the storyboard and approve again, only the parts whose frames changed are rendered again — unchanged parts are reused and audio is muxed again. The job's progress lines and result carry `parts_total`, `parts_rendered`, and `parts_reused`; `GET /api/projects/{pid}/export` shows `parts_reused` and `parts_to_render` in `plan`. If you change the storyboard or the voice after exporting, the step says it needs exporting again; the old video stays until a new one is made.

## A worked session

Fixture project `arn` (the storyboard is approved; the export job here is a stand-in that ends at once, the real one prints a line each time something changes and takes about 25 minutes).

```text
# fixture: book storyboard_approved
$ bti status arn
project: arn   stage: approved   current step: export (Xuất video)
automatic running: off (an agent approves no gate; the owner approves on the page or turns it on there)
approvals: outline human; narration human; picks human; storyboard human
...
next: bti do arn export.start --yes-cost --wait   (Xuất video)
$ bti do arn export.start
a person is needed: cost_not_confirmed
  detail: export.start costs machine_time (about 25 minutes).
  fix: Run it again with --yes-cost when the owner asked for this work.
(exit 3)
$ bti do arn export.start --yes-cost --wait
started job <job> (export.start)
...
done: <any>
```

## The output folder and the cleaning

When the export is done the app also fills `output/<artwork key>/` (beside `projects/`; one folder per painting, named by the library's artwork key, or by the project id for a project made without one): `final.mp4` at its root, `README.md` (one page, in Vietnamese: where the video stands), `state.json`, and the parts `1_sources/`, `2_script/`, `3_voice/`, `4_pictures/`, `5_storyboard/` (with the contact sheets of the video), `6_export/` and `log/`. The folder fills as the project moves (each part when its gate is approved, the voice when it is done, the video when the export is) and marks a part as out of date when its document changes after it was published. The app writes it; never edit or delete anything in it. `bti output <project>` fills (or refills) it from the project as it stands (action `output.build`); `bti output <project> --clean` also does the cleaning below.

After a SUCCESSFUL export the app removes the working folder's caches (joined scratch `cache/export/video_all.mp4`, stale parts, preview frames and clips, the transcripts of the pictures agent's runs, job logs; the exact list is in `bti/output/clean.py`) and **keeps** the current export's `cache/export/parts` (~840 MB for an 11-minute video) so a later small edit reuses unchanged parts. The output folder's `README.md` says how much was freed and how many parts were kept (`kept_parts`, `kept_parts_bytes`). It never cleans after a failed export, while another job of the project runs, or when the owner switched it off in the settings. The documents, `changes/`, `history/`, `cache/draft/`, `cache/export/parts` of the current export, and the job records stay, so the project opens, previews, edits and re-exports unchanged parts without re-rendering them. A problem writing the folder never fails the export: it is a `warnings` entry of `bti status` with its sentence. The video is never copied anywhere else by an agent: the owner fetches it with `tools/deploy/fetch_video.sh <artwork key>`.

## What a good result is

- The step is `done` and the check sheet says what it should: the length of the video matches the audio, the number of frames matches the length, the loudness is in range, and the chapter list matches the narration's chapters.
- Before you tell the owner it is ready, read the description (`GET /api/projects/{pid}/export`, key `description`): a picture whose licence is unclear carries a note for the owner to check before publishing. The export is never blocked by it; the owner decides.
- The export is a one-way spend of the machine's time: start it only when the owner asked, once the storyboard is approved, and do not start a second one while one runs.

## The refusals you will meet

| code | what to do |
|---|---|
| `not_approved`, `approval_stale`, `storyboard_approved` | Approve the storyboard first (the owner, or you if allowed): any change after the approval needs a new one. |
| `no_audio`, `no_timing`, `audio_mix`, `timing` | The voice is missing: step 3. |
| `no_running_job`, `longjob_running` (exit 5) | An export already runs: `bti job <id> --wait`. |
| `part_missing`, `join_failed`, `mux_failed` (exit 5) | A rendered part is missing or the join failed: call `export.start` again, the finished parts are kept. |
| `frames_mismatch` | The video has the wrong number of frames: call `export.start` again; if it repeats, run `storyboard.validate`. |
| `plan_failed`, `undrawable`, `render_failed` | The storyboard has something the engine cannot draw: `storyboard.validate`, fix it with `bti ops ... storyboard`, approve again. |
| `interrupted` (exit 5) | The server restarted while the job ran: start it again. |
| `cost_not_confirmed`, `spend_not_allowed` (exit 3) | A cost needs `--yes-cost` and the owner's permission: ask. |
