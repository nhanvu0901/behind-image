# FIX: one clean folder per painting (worker `outfolder`)

Branch `wt/outfolder`. No model call, no git command that writes, nothing in the server's main folder or its running app was touched; the real project `arnolfini-opus` was only read.

## 1. What was built

`bti/output/` fills `output/<artwork key>/` (beside `projects/`, not in git) as a project moves through its steps: `final.mp4` at its root, `README.md`, `state.json`, the parts `1_sources/` to `6_export/` and `log/`, and `INDEX.md` / `index.json` one level up. One function, `publish.sync`, decides and writes; it is called with one line each from the places in section 4. Around it: the rebuild (state action `output.build`, route `POST /api/projects/{pid}/output/build`, command `bti output <project> [--clean]`), the cleaning of the working folder's caches after a successful export (`bti/output/clean.py`, one switch in the settings dialog), `tools/deploy/fetch_video.sh`, and an index option for `tools/paintings_table.py`. Owner-facing text is Vietnamese (the README, the Markdown documents, the switch on the page, a section 15 of `docs/APP_GUIDE.md`).

The modules: `paths` (where, what the parts are called), `facts` (read-only: what the project says about itself), `parts` (one writer per part), `render` and `readme` (the Markdown), `shotwords` (the sentence of a shot), `times` (when a shot starts), `sheets` (regions sheet, contact sheets), `publish` (`sync`), `clean`, `hooks` (the middleware and the last part of the voice and export jobs), `index`, `api`, `fsutil` (atomic writes, hard links), `words` (Vietnamese words and formats).

## 2. The real project, built into `D:\code\behind-the-image\run\outfolder\output\` (read-only for the project, no cleaning)

`publish.sync(<arnolfini-opus>, <my output root>, explicit=True, clean=False)` from my snapshot on the server: 42 files written in 8.4 s (the contact sheets are most of that), the second call wrote nothing (`unchanged`), no warning. The tree, with sizes (`final.mp4`, the audio and the pictures are **hard links** of the project's own files: of the 1.0 GB shown, **2.8 MB are new bytes on disk**; `st_nlink` is 2 for the three files checked):

```
INDEX.md                                544 B
eyck-the-arnolfini-portrait/   (998.7 MB, 38 files)
  1_sources/   (29.7 KB, 5 files)
    brookehitching_mad_011.txt             3.2 KB
    dossier.json                           8.1 KB
    hodge_aid_003.txt                      6.4 KB
    payne_gae_002.txt                     11.4 KB
    sources.md                              656 B
  2_script/   (85.1 KB, 4 files)
    narration.json                        24.5 KB
    narration.md                          16.8 KB
    outline.json                          24.9 KB
    outline.md                            18.9 KB
  3_voice/   (87.9 MB, 3 files)
    mix.m4a                               17.8 MB
    narration.wav                         70.0 MB
    timing.json                          124.6 KB
  4_pictures/   (12.6 MB, 9 files)
    albrecht_durer_1500.jpg                4.0 MB
    credits.txt                            1.3 KB
    jacopo_della_quercia.jpg             369.7 KB
    las_meninas_diego.jpg                  4.0 MB
    main.jpg                               3.2 MB
    picks.json                            32.2 KB
    portrait_man_turban.jpg              444.3 KB
    portrait_philip_good.jpg             115.0 KB
    regions.jpg                          504.5 KB
  5_storyboard/   (1.9 MB, 8 files)
    contact_sheet_01.jpg                 305.5 KB
    contact_sheet_02.jpg                 302.4 KB
    contact_sheet_03.jpg                 317.8 KB
    contact_sheet_04.jpg                 318.7 KB
    contact_sheet_05.jpg                 323.0 KB
    contact_sheet_06.jpg                 195.4 KB
    shots.md                              18.5 KB
    storyboard.json                      133.9 KB
  6_export/   (4.6 KB, 3 files)
    chapters.txt                            196 B
    description.txt                        1.7 KB
    report.json                            2.7 KB
  README.md                              3.2 KB
  final.mp4                            896.2 MB
  log/   (60.2 KB, 3 files)
    changes.md                            33.3 KB
    jobs.json                             16.0 KB
    jobs.md                               10.8 KB
  state.json                             6.8 KB
index.json                              463 B
```

What I looked at as the owner would, and fixed: the README, `narration.md`, `shots.md`, `outline.md`, `jobs.md`, `changes.md`, one contact sheet (`contact_sheet_01.jpg`: 20 frames, each with its number and time on the frame and the plain sentence under it, Vietnamese diacritics drawn) and `regions.jpg` (the main painting with 31 numbered regions and a legend with their names). Things a person would have stumbled on and that I changed: the legend of the regions sheet was cut short and the filled ellipses darkened the painting (wider legend, lighter fill); a `show` word `D7 the signature above the mirror` read as a dossier name that did not fit (a `D<n>` in front of words that describe the picture is dropped, a bare `D5` is the dossier's name, as the app itself reads it); the notes column of `jobs.md` repeated the voice engine; the line about the contact sheets in the README had doubled backticks; a rebuild did not rewrite a part whose revision had not changed (now a rebuild writes every settled part again; a file whose content is the same is left alone).

The other real project, `scream` (outline, narration, voice and picks approved, no storyboard yet), was built into the same private output root as well: 41 files in 1.3 s, no warning; its README says "Đang làm. Đang ở bước 5, Dựng hình", lists steps 1 to 4 as done with their dates (an approval made before the approver was recorded reads "không ghi"), has no `final.mp4`, `5_storyboard/` or `6_export/` yet, and `INDEX.md` lists both paintings (`done` / `in progress`).

### The README as written

````markdown
# The Arnolfini Portrait

Jan van Eyck · 1434

**Đã xong.** Video đã xuất và nằm ở `final.mp4` (12 phút 44 giây).

- Dự án: `arnolfini-opus` · Thư mục này: `output/eyck-the-arnolfini-portrait/`
- Cập nhật lần cuối (theo dự án): 19/11/2026 11:50

## Video

| | |
|---|---|
| Tệp | `final.mp4` |
| Độ dài | 12 phút 44 giây (764,5 giây) |
| Dung lượng | 896 MB |
| Độ phân giải | 1920 × 1080, 30 khung hình/giây |
| Số chương | 8 |
| Độ lớn tiếng | -15,0 LUFS (đỉnh -1,7 dB) |
| Xuất xong lúc | 19/11/2026 11:50 (máy dựng mất 14 phút 23 giây) |

Kiểm tra tự động: tất cả 10 mục đều đạt.

## Các bước

| # | Bước | Tình trạng | Xong lúc | Ai duyệt | Agent | Nằm ở |
|---|---|---|---|---|---|---|
| 1 | Tác phẩm | xong | 19/11/2026 08:03 | — | — | `1_sources/` |
| 2 | Kịch bản | xong | 19/11/2026 08:30 | Dàn ý: Lệnh bti (arnrun); Lời dẫn: Lệnh bti (arnrun) | Opus 5.5 High | `2_script/` |
| 3 | Giọng đọc | xong | 19/11/2026 09:26 | — | chatterbox + whisper | `3_voice/` |
| 4 | Chọn hình | xong | 19/11/2026 09:27 | Chọn hình: Lệnh bti (arnrun) | Opus 5.5 High | `4_pictures/` |
| 5 | Dựng hình | xong | 19/11/2026 11:36 | Storyboard: Lệnh bti (arnrun) | Opus 5.5 High | `5_storyboard/` |
| 6 | Xuất video | xong | 19/11/2026 11:50 | — | — | `final.mp4, 6_export/` |

## Trong thư mục này

- `final.mp4`: video đã xuất, 12 phút 44 giây, 896 MB.
- `1_sources/`: nguồn sách (5 tệp), danh sách nguồn `sources.md`, hồ sơ `dossier.json`.
- `2_script/outline.md`: dàn ý (8 chương, 55 dữ kiện).
- `2_script/narration.md`: lời dẫn (8 chương, 62 dòng, 1762 từ). Cùng thư mục có hai tệp JSON.
- `3_voice/`: giọng đọc (`narration.wav`), bản trộn (`mix.m4a`), thời gian từng từ (`timing.json`, 1762 từ).
- `4_pictures/`: tranh chính (`main.*`) và 5 hình khác trên màn hình, `picks.json`, `regions.jpg` (31 vùng vẽ trên tranh chính), `credits.txt`; đã bỏ 6 hình không dùng.
- `5_storyboard/`: `shots.md` (113 cảnh bằng lời thường), `storyboard.json`, 6 tờ ảnh tổng hợp (mỗi cảnh một khung hình).
- `6_export/`: `description.txt` (mô tả đăng video), `chapters.txt` (mục lục), `report.json` (báo cáo kiểm tra).
- `log/`: `changes.md` (44 lần sửa), `jobs.md` (34 việc dài).

## Xem gì tiếp

- Xem video `final.mp4`.
- Đọc `2_script/narration.md` (lời dẫn) và `5_storyboard/shots.md` (từng cảnh bằng lời thường).
- Lướt nhanh cả video qua các tờ ảnh `contact_sheet_01.jpg` đến `contact_sheet_06.jpg` (mỗi cảnh một khung hình, có số và giờ).
- Xem `4_pictures/credits.txt` và `6_export/description.txt` trước khi đăng.
- Chép video về máy: `tools/deploy/fetch_video.sh eyck-the-arnolfini-portrait`.

## Các lần làm trong thư mục này

| Dự án | Lần ghi đầu | Lần ghi cuối | Tới bước |
|---|---|---|---|
| `arnolfini-opus` | 19/11/2026 12:50 | 19/11/2026 13:21 | Xuất video |

---
Tệp này do ứng dụng viết, đừng sửa tay: lần ghi tiếp theo sẽ ghi đè. Ghi lại từ dự án bất cứ lúc nào: `bti output arnolfini-opus`.
````

### `state.json` (schema `bti.output/1`): the shape, with the real example (long lists cut)

```json
{
 "schema": "bti.output/1",
 "key": "eyck-the-arnolfini-portrait",
 "artwork": {
  "key": "eyck-the-arnolfini-portrait",
  "title": "The Arnolfini Portrait",
  "artist": "Jan van Eyck",
  "year": "1434"
 },
 "project": "arnolfini-opus",
 "project_created": "2026-11-19T08:03:43-08:00",
 "updated": "2026-11-19T11:50:42-0800",
 "current": null,
 "status": "done",
 "steps": [
  {
   "step": "artwork",
   "label": "Tác phẩm",
   "state": "done",
   "reached": "2026-11-19T08:03:43-08:00"
  },
  {
   "step": "script",
   "label": "Kịch bản",
   "state": "done",
   "reached": "2026-11-19T08:30:25-0800"
  },
  "... (4 more)"
 ],
 "reached": {
  "artwork": "2026-11-19T08:03:43-08:00",
  "script": "2026-11-19T08:30:25-0800",
  "voice": "2026-11-19T09:26:04-0800",
  "picks": "2026-11-19T09:27:03-0800",
  "edit": "2026-11-19T11:36:19-0800",
  "export": "2026-11-19T11:50:42-0800"
 },
 "gates": {
  "outline": {
   "approved": true,
   "by": "cli:arnrun",
   "at": "2026-11-19T08:07:13-0800",
   "stands": true
  },
  "narration": {
   "approved": true,
   "by": "cli:arnrun",
   "at": "2026-11-19T08:30:25-0800",
   "stands": true
  },
  "picks": {
   "approved": true,
   "by": "cli:arnrun",
   "at": "2026-11-19T09:27:03-0800",
   "stands": true
  },
  "storyboard": {
   "approved": true,
   "by": "cli:arnrun",
   "at": "2026-11-19T11:36:19-0800",
   "stands": true
  }
 },
 "agents": {
  "script": "Opus 5.5 High",
  "picks": "Opus 5.5 High",
  "edit": "Opus 5.5 High",
  "voice": "chatterbox + whisper"
 },
 "video": {
  "file": "final.mp4",
  "seconds": 764.47,
  "size_bytes": 939766710,
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "frames": 22934,
  "chapters": 8,
  "loudness": {
   "lufs": -15.0,
   "lra": 3.0,
   "true_peak": -1.7
  },
  "report_status": "ok",
  "checks": [
   {
    "key": "video",
    "status": "ok",
    "value": "h264",
    "expected": "h264",
    "note": ""
   },
   {
    "key": "duration",
    "status": "ok",
    "value": 764.49,
    "expected": 764.47,
    "note": ""
   },
   "... (8 more)"
  ],
  "created": "2026-11-19T11:50:42-0800",
  "render_seconds": 862.8
 },
 "parts": {
  "sources": {
   "rev": "cb13d715109afbafd609e83ef2ccaa2f5dc57d2a",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "1_sources/brookehitching_mad_011.txt",
    "1_sources/dossier.json",
    "... (3 more)"
   ],
   "out_of_date": false,
   "reason": null
  },
  "outline": {
   "rev": "b04f37e50b5562d8c33840c0555e385046efb8b4",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "2_script/outline.md",
    "2_script/outline.json"
   ],
   "out_of_date": false,
   "reason": null,
   "counts": {
    "chapters": 8,
    "facts": 55
   }
  },
  "narration": {
   "rev": "20fc7a75f28e6bab3ff4d111c81030401bebef61",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "2_script/narration.md",
    "2_script/narration.json"
   ],
   "out_of_date": false,
   "reason": null,
   "counts": {
    "chapters": 8,
    "lines": 62,
    "words": 1762
   }
  },
  "voice": {
   "rev": "1cce7a74ff8d64214d2230688603d53f654f3b2a",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "3_voice/narration.wav",
    "3_voice/mix.m4a",
    "3_voice/timing.json"
   ],
   "out_of_date": false,
   "reason": null,
   "duration": 764.47,
   "words": 1762
  },
  "pictures": {
   "rev": "36322357cf285dd5bd79c7a0edc5cfbc8397c2c4",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "4_pictures/main.jpg",
    "4_pictures/portrait_man_turban.jpg",
    "... (7 more)"
   ],
   "out_of_date": false,
   "reason": null,
   "basis": "storyboard",
   "count": 6,
   "regions": 31,
   "unused_left_out": 6
  },
  "storyboard": {
   "rev": "efdeaa7d9e28c3b6241e475428e11e8227287f3830ec502dd5b4684218262668",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "5_storyboard/shots.md",
    "5_storyboard/storyboard.json"
   ],
   "out_of_date": false,
   "reason": null,
   "counts": {
    "shots": 113
   }
  },
  "export": {
   "rev": "474eebac6c4bb8535709d6fac3b45b717e3085a4",
   "at": "2026-11-19T13:21:16-0800",
   "files": [
    "final.mp4",
    "6_export/description.txt",
    "... (2 more)"
   ],
   "out_of_date": false,
   "reason": null,
   "sheets": [
    "5_storyboard/contact_sheet_01.jpg",
    "5_storyboard/contact_sheet_02.jpg",
    "... (4 more)"
   ],
   "sheets_for": "474eebac6c4bb8535709d6fac3b45b717e3085a4"
  }
 },
 "revisions": {
  "outline": "b04f37e50b5562d8c33840c0555e385046efb8b4",
  "narration": "20fc7a75f28e6bab3ff4d111c81030401bebef61",
  "voice": "1cce7a74ff8d64214d2230688603d53f654f3b2a",
  "picks": "36322357cf285dd5bd79c7a0edc5cfbc8397c2c4",
  "storyboard": "efdeaa7d9e28c3b6241e475428e11e8227287f3830ec502dd5b4684218262668",
  "export": "474eebac6c4bb8535709d6fac3b45b717e3085a4"
 },
 "clean": null,
 "log": {
  "changes": 44,
  "jobs": 34,
  "auto_runs": 0
 },
 "warnings": [],
 "last_sync": {
  "moment": "proof",
  "at": "2026-11-19T13:21:16-0800"
 },
 "fingerprint": "b35b2d0644f9...",
 "runs": [
  {
   "project": "arnolfini-opus",
   "first_write": "2026-11-19T12:50:12-0800",
   "last_write": "2026-11-19T13:21:16-0800",
   "reached": "export",
   "writes": 5
  }
 ]
}
```

`runs` has one record per time the folder was filled from a project (`project`, `first_write`, `last_write`, `reached`, `writes`), newest last; a new project of the same artwork adds a record and keeps the earlier ones. `parts.<name>.rev` is the revision of the document the part was made from; `out_of_date`/`reason` mark a part whose document changed or whose approval was withdrawn. `warnings` holds `{code, part, detail, sentence}`.

### What the cleaning would remove from this real project (a DRY RUN: nothing was removed)

`clean_project(<arnolfini-opus>, dry_run=True)`: **1,898,043,890 bytes (1.77 GiB) in 1,549 files**: `cache/export` (the render parts and the joined video, about 1.8 GB), `cache/frames` (1,500 preview frames), `cache/thumbs`, `cache/picks_auto/runs`, `cache/longjobs/work`, 13 `cache/longjobs/*.log`, 1 `cache/wave_*.json`. What stays of `cache/`: the 4 script job records and the 30 long-job records (they are what the app lists and what `log/jobs.md` is made from), `cache/draft/` (the request box's thread and turns), the rest of `cache/picks_auto/`. Nothing outside `cache/` is touched.

## 3. The cleaning: exactly which paths, and how the project was proved to still work

Removed after a successful export (`bti/output/clean.py`, an explicit list, never "everything under cache/"):

```
cache/export/              render parts, joined video, mux scratch. part_key() contains the storyboard's revision, so after any edit no part is reused anyway
cache/frames/              the page's preview frames, made again when a frame is asked for
cache/thumbs/              thumbnails of the page, made again on demand
cache/previews/            the "Xem thử" clips, made again on demand
cache/uploads/             scratch of an upload in progress
cache/picks_auto/runs/     transcripts of the pictures agent's runs; nothing reads them back
cache/voice/               the voice stage's scratch folder
cache/wave_*.json          the waveform of the mix for the page, made again on demand
cache/longjobs/work/       work folders of the long jobs (Part.is_done decides by the files a part writes, not by these)
cache/longjobs/*.log       text logs of the long jobs (not the records)
```

Kept: `cache/jobs/*.json`, `cache/longjobs/*.json`, `cache/draft/`, `cache/picks/` (the paid suggestions), the rest of `cache/picks_auto/`, and everything that is not under `cache/` (documents, `changes/`, `history/`, `proposals/`, `media/`, `audio/`, `voice/`, `export/`, `auto_runs/`). It runs only inside the last part of the export job (or with `bti output <project> --clean`), only when the export stands and its check card has no `error`, only when no other job of the project runs (the automatic run does not count), and only when `clean_after_export` is on (default). The README of the folder says how much was freed.

How it was proved (`tests/output/test_clean.py`, `test_stays_working.py`): the exact list (a path not on it is never touched: a `cache/zzz/other.bin` survives); every document, change record, history copy, picture, audio and export file is byte-identical before and after; the freed byte count equals the size of the listed files; skipped after a failed export, after an export whose check card says `error`, while another job runs, and when the switch is off; the calling job's own log stays. `test_after_cleaning_the_project_opens_previews_edits_and_exports_again` uses the operations' fixture project, the real engine and the real routes: it runs the real export job (fake tools), checks `cache/export` is gone, then opens the project (`GET /api/projects/{pid}`, `/state`, `/export`, `/changes`, `/longjobs`), previews (`GET .../frame` returns a JPEG and `cache/frames` is made again), edits (a typed storyboard operation through `POST .../storyboard/ops`, which marks the published parts out of date), is refused an export until it is approved again (`approval_stale`), approves, and exports again: the folder then has the new revision, nothing is out of date, and the cleaning ran again.

## 4. Where each part is written, and the hooks

Parts and their moments: `1_sources/` when the project is made (and kept current if `source/` changes); `2_script/outline.*` when the outline is approved; `2_script/narration.*` when the narration is approved; `3_voice/` when the voice is done; `4_pictures/` when the picks are approved (the main painting and the pictures the picks give to lines), narrowed to the pictures the shots show when the storyboard is approved; `5_storyboard/` (`storyboard.json`, `shots.md`) when the storyboard is approved; `final.mp4`, `6_export/` and the contact sheets when the export is done; `state.json`, `README.md`, `log/` and the index at every one of these moments and at every change. Each part is written only while its gate stands; when its document changes later it is marked out of date, never silently left looking current.

| moment | what calls `publish.sync` | file | line | note |
|---|---|---|---|---|
| project made (sources) | after `POST /api/library/projects` | `bti/editor/app.py` | 106 | the middleware reads the new project's id from the answer |
| outline approved | after `POST .../outline/approve` | `bti/editor/app.py` | 106 | same middleware (one block) |
| narration approved | after `POST .../narration/approve` | `bti/editor/app.py` | 106 | same |
| voice done | last part `output` of the voice job | `bti/voice/run.py` | 243 | 4 lines |
| picks approved | after `POST .../picks/approve` | `bti/editor/app.py` | 106 | same |
| storyboard approved | after `POST .../approve` | `bti/editor/app.py` | 106 | same |
| export done (video, contact sheets, 6_export, cleaning) | last part `output` of the export job | `bti/export/run.py` | 359 | 4 lines |
| any edit, withdrawn approval, new draft (marks parts out of date) | after every successful POST/PUT/PATCH/DELETE under `/api/projects/{pid}/` | `bti/editor/app.py` | 106 | same |
| rebuild on demand | `output.build` action, `POST .../output/build`, `bti output` | `bti/editor/app.py` | 958 | router include; the action is in state_api.py:179, the command in cli/main.py:546 |

The other places that were edited (marked `outfolder`):

| file | what | lines |
|---|---|---|
| `bti/editor/app.py` | `create_app(output_root=...)`, `app.state.output_root`, `output_hooks.register`, the router | 71, 102, 958 |
| `bti/editor/state_api.py` | `Spec output.build`, `Ctx.output_root`, `b_output_build`, `build_state(output_root=...)` and the `warnings` key | 179, 255, 831, 961 |
| `bti/editor/hints.py` | three codes `output_disabled`, `output_not_applicable`, `output_failed` | 320 |
| `bti/cli/main.py`, `bti/cli/render.py` | the command `bti output`, the `warnings:` lines of `bti status`, `output_lines` | 546, 161, 275 |
| `bti/settings.py`, `bti/editor/settings_api.py` | the switch `clean_after_export` (`GET/PUT /api/settings/output`) | 173, 38 |
| `bti/editor/static/js/labels.js`, `outputswitch.js`, `settings.js` | `OUTPUT_LABELS` (block at the end of labels.js), the switch box, two marked lines in settings.js | 863, 11 |

Not changed: `script_api.py`, `picks_api.py` (the middleware makes per-route hooks unnecessary), `errmsg.js` (no new page error), `bti/auto_run/`, `bti/longjob/`.


## 5. Decisions where the brief was silent

1. **Where the root is.** `BTI_OUTPUT_ROOT` when set, else `output/` beside the projects folder (so `D:\code\behind-the-image\output\` on the server). An app made with an explicit projects folder and no `output_root` has none (`create_app(projects_root=...)` in every other stage's tests), so no other test writes an `output/`; `create_app(output_root=...)` turns it on, `False` off.
2. **No edits in `script_api.py` / `picks_api.py`.** The moments of the gates are reached by one ASGI middleware (`hooks.OutputSyncMiddleware`, one block in `app.py`): after a successful POST/PUT/PATCH/DELETE under `/api/projects/{pid}/...` (an approval, a save, an operation, an import) or after `POST /api/library/projects` (the new project) the folder of that project is brought up to date on a background thread (never delays the answer; two changes in a row are one write). The two moments that are not requests are reached by a last part (`output`) of the voice job and of the export job (4 lines each in `voice/run.py` and `export/run.py`, only when the app has an output folder). The same function also marks parts out of date at every change, which per-route hooks could not do without touching every edit route.
3. **"Settled" means the gate stands**, read from the documents: outline `approved_fresh`, narration `narration_approval`, picks `approval_state`, storyboard `storyboard_approval == fresh`, voice `bti.voice.describe == done` (running jobs not counted), export manifest present and `stale_reason` None. The six step states in `state.json` are made the same way (`done`, `current`, `stale`, `locked`), not from the page's step bar, so a job that is running when the folder is written never hides what it has just made.
4. **Out of date.** A part keeps its old files and is marked `out_of_date` with `reason` `changed` (its document's revision differs from the published one) or `approval_withdrawn` (same revision, the gate no longer stands); the README lists them under "Phần đã cũ". It comes back when the gate stands again and the part is rewritten.
5. **Pictures.** Before the storyboard is approved: the main painting (`main.<ext>`) and the pictures the picks give to lines; once the storyboard is approved and published: only the pictures its shots show (`bti.export.describe.used_assets`, the list the video's credits use), the others are removed from the folder. Files are named by asset key. `regions.jpg` uses the storyboard's regions of the main painting once there is one. On the real project 12 pictures exist, 6 are on screen.
6. **Big files are hard links** (`final.mp4`, the audio, the pictures) when the drive allows (`os.link`, then a rename of the link under its final name), else copies, always through a `.part` name first. Safe because the app only ever writes a file by renaming a new one over the old one (`bti.fsio.atomic_replace`): the published copy then stays the old version until the next sync. It saves a second 900 MB per video; a copy is the fallback.
7. **One folder per painting, newest project owns it.** A sync from a project other than the folder's last one is skipped (`older_project`) unless the other project is gone or newer (by `created_at`); the rebuild command always takes over. A takeover removes what the earlier project made (its numbered parts, log and video) and keeps `state.json`'s `runs`. This keeps `arnolfini-live` (same painting, older) from overwriting the finished `arnolfini-opus` folder by an edit.
8. **Reference projects** (`protected`, `imported`, no `project.json`) have no folder: automatic syncs skip them, `output.build` is not listed for them and answers `output_not_applicable`.
9. **The cleaning list** is exactly the one in `bti/output/clean.py` (section 3). Decided by reading what writes and what reads each path: the job records (`cache/jobs/*.json`, `cache/longjobs/*.json`) STAY because the app lists them and `log/jobs.md` is made from them (only their `.log` and `work/` go); `cache/draft/` stays (the request box's thread and turns, undo); `cache/picks/` stays (paid suggestions); `cache/picks_auto/` stays except `runs/` (the page shows `last.json`). It never runs while another job of the project runs, never after a failed export or an export whose check card says `error`, and never when `PUT /api/settings/output {"clean_after_export": false}`. A rebuild cleans only with `--clean`.
10. **`log/jobs.md` survives the app's pruning** (the runner keeps 30 records per project): every row is also kept in `log/jobs.json` and merged by id, for the same project. `changes.md` is made from the change log as it is (the log keeps 200 records per document).
11. **Words.** Every Markdown document is Vietnamese; ids of techniques in free text (a request that says `CAM-03`) are written as the registry's Vietnamese name, a detail the dossier calls `D5` by its own name. `state.json` and `index.json` keep English keys; only `warnings[].sentence` is Vietnamese there.
12. **`shots.md` and the page stay in step** through one shared set of cases: `tests/output/fixtures/shot_cases.json` (144 real shots and the 85 techniques as base and as overlay, with the sentence the page's `shotSentence` makes). `tests/output/shotsentence_parity.test.mjs` (Node, Mac) checks the JavaScript side against it (`UPDATE_GOLDEN=1` regenerates it); `tests/output/test_shotwords.py` (server) checks the Python twin. A change of a phrase in `labels.js` fails the first test until the file is regenerated, and then the second until `bti/output/shotwords.py` says the same.
13. **Contact sheets**: 5 columns x 4 rows of 384 px frames per sheet, the frame cut 40% into each shot, the shot number and time on the frame and the plain sentence under it, in `5_storyboard/contact_sheet_NN.jpg`; made after the export with `ffmpeg` (the export settings' program), four calls at a time; the scratch folder is made inside the output folder (nothing goes to the system's temp folder). A video that cannot be cut is a warning (`output_sheets_failed`), the video is still published, and it is not retried at every change.
14. **Warnings.** A problem writing the folder never fails the step that called: `notify` catches everything, keeps the last failure and the state answer carries `warnings: [{code, detail, sentence}]` (the key exists only when the app has an output folder and something is wrong); `bti status` prints them.
15. **The automatic run's log** (`log/auto_runs.md`) is written at every sync; a run that ends after the export is in it at the next sync or rebuild (the run has no moment of its own, and `bti/auto_run/` is not in the list of files to edit).
16. **`bti output`** is the command, `output.build` the action (step `export`, always ready, no cost, `auto_ok` true). The route is synchronous (a few seconds with contact sheets).
17. **`tools/deploy/fetch_video.sh`** copies to `~/Desktop/Claude Render/<key>.mp4` through a `.part` name; `BTI_REMOTE_OUTPUT` and `BTI_FETCH_DIR` replace the two ends (so it can be tried without the real folders).
18. **`tools/paintings_table.py <index.json>`** adds the status `done` (a finished video in the index) before `in-progress`; with an index, the fixed `PROJECTS` list and the "in-progress" notes of the research are not used.
19. **`.gitignore`** has `/output/` anchored: an unanchored `output/` would also hide `bti/output/` and `tests/output/`.

## 6. Tests: the summary lines exactly as printed

```
tests/output   77 passed in 17.19s
tests/export   78 passed, 2 skipped in 15.46s
tests/editor   488 passed in 249.08s (0:04:09)
tests/state    295 passed in 187.78s (0:03:07)
tests/cli      127 passed in 39.16s
tests/script   262 passed, 7 skipped in 29.38s
tests/picks    235 passed in 53.19s
tests/draft    400 passed in 130.06s (0:02:10)
tests/auto     185 passed in 67.64s (0:01:07)

node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs
ℹ tests 443
ℹ pass 442
ℹ fail 0
ℹ skipped 1
```

## 7. Commands for the coordinator

After the deploy, ON THE SERVER from `D:\code\behind-the-image`. The Python side (the middleware, the last job parts, the action `output.build`, the settings route) only runs in the app after a restart deploy (`tools/deploy/git_deploy.sh --restart`), which needs the owner's yes that names the deploy; the page files (the settings switch) change with a plain pull:

```
tools\bti.bat output arnolfini-opus            # builds output\eyck-the-arnolfini-portrait\ from the finished project (about 10 seconds, hard links, no cleaning)
tools\bti.bat output scream                    # builds output\munch-the-scream\ (a project in progress: the parts that are settled)
tools\bti.bat output arnolfini-opus --clean    # only when the owner agrees: also frees about 1.8 GB of caches of the finished project
type output\INDEX.md                           # the index; output\index.json is what tools/paintings_table.py reads
```

Do NOT run `output` for `arnolfini-live` (same painting as `arnolfini-opus`, older): a rebuild takes the folder over. From the Mac:

```
BTI_SSH_HOST=winbox-cmd tools/deploy/fetch_video.sh eyck-the-arnolfini-portrait   # -> ~/Desktop/Claude Render/eyck-the-arnolfini-portrait.mp4, only that file
scp winbox-cmd:D:/code/behind-the-image/output/index.json /tmp/index.json && python3 -I tools/paintings_table.py /tmp/index.json   # the queue table with what the index says
```

Regenerated documents (`python -m bti.cli.docgen`, `python -m bti.editor.hints`): `AGENTS.md` (one table row), `skills/export/SKILL.md` (one row) and `docs/AGENT_API.md` (one action row, three code rows) are already updated in the worktree; their tests are green.


## 8. What I could not verify

- **The running app.** Nothing was deployed or restarted: the middleware, the last job parts and the page switch were run only in the tests (the app in the test process with `TestClient`, the real engine for the preview and the operations, the real export job with the fake tools of `tests/export`). The first real export through the new last part will show whether `ffmpeg` is on the PATH of the app's own process (the contact sheets need it; if not, the video is still published and a warning says so).
- **The page.** The switch in the settings dialog was checked with `node --check`, with Node tests for its words and its one decision, and by the Node tests of the other pages (no browser was opened).
- **The real library route.** `POST /api/library/projects` is faked in the test (the middleware reads the id from its answer); the route itself was not run (it needs the library).
- **The cleaning on real data.** Only a dry run on `arnolfini-opus` (which paths and how many bytes), because the brief forbids cleaning there; the real removal is proved on fixture projects and on the operations' fixture project with the real engine.
- **The fetch script against the real `output/` folder** (it does not exist until the first build); it was run against a small file in `run/outfolder/` on the server, and with a missing key.
- **Hard links** were proved on the server's drive (the proof folder and the project are on `D:`); the copy fallback is tested by making `os.link` fail.
- **A file that is open elsewhere** (a player holding `final.mp4` on Windows) makes the replace of that file fail after three seconds: it is a warning and the next sync tries again; not tried with a real player.
- **The ssh outage rule** was not needed: the server answered every call.
