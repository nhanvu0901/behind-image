STATUS: ready

# Windows server: how the app is deployed, tested and run

Written by the WIN agent, phase 1 (2026-11-16). The server is `DESKTOP-4V6D49N` (`ssh winbox-lan`, user `admin`), Windows 11, 16 threads, ~31 GB RAM, no NVIDIA card. It is PRODUCTION for the comic channel: read `docs/benchmarks/video_edit_benchmark_prompt.md` section 4 before doing anything beyond what is below. Our folder is `D:\code\behind-the-image\`; everything we install or create stays in it. The Mac is only for writing code; the app and every test run on the server.

## Rules in one list
- Comic repo `D:\code\comic-book-pipeline` is read-only (no edit, no git command that writes, no pip into its venvs).
- No system change: no system-wide install, PATH change, firewall rule, open port, scheduled task, service or start-up entry. Ask the owner.
- Never port 8550. Our app: `127.0.0.1:8560` on the server (never on 0.0.0.0).
- Never read, print or send a `.env` file or environment values. The deploy filters `.env*` out twice (pack and unpack).
- Never run `agy` with a prompt (`agy --version` and `agy models` only). `agy` is not signed in over ssh.
- Heavy jobs (many cores for more than a minute or two: full renders, the engine's `slow` sweep, voice synthesis, model runs) follow the lock protocol: `mkdir D:\bench\_heavy.lock` (atomic), `owner.txt`, free virtual memory above 12,000,000 KB, no production process (`_chatterbox_worker`, `stages.stage_4`, `stages.stage_5`, `ffmpeg` outside `D:\bench`), under 30 minutes, launched through `Invoke-CimMethod Win32_Process Create` so it survives the ssh session, lock removed at the end. `remote_test.sh` refuses `-m slow` (override: `BTI_ALLOW_HEAVY=1`, only inside the lock protocol). This is a note, not a parser: `remote_py.sh` checks nothing, so do not start renders, sweeps or voice work through it.

## Commands (all from the repo root on the Mac)
| What | Command |
|---|---|
| Deploy the working tree (code only) | `tools/deploy/deploy_windows.sh` |
| Deploy and also send `books/`, `library/`, `projects/` (no `cache`/`history`) | `tools/deploy/deploy_windows.sh --data` |
| Deploy and restart our app | `tools/deploy/deploy_windows.sh --restart` |
| Deploy, then run pytest on the server | `tools/deploy/remote_test.sh tests/script -q -x` |
| Run pytest without deploying | `tools/deploy/remote_test.sh --no-sync tests/editor -k name` |
| Any one-off python check | `tools/deploy/remote_py.sh -c "import sys; print(sys.version)"` |
| The same in the Python 3.12 align venv | `tools/deploy/remote_py.sh --venv align -c "import faster_whisper"` |

- `deploy_windows.sh` packs `git ls-files -c -o --exclude-standard` (tracked plus untracked-not-ignored, skipping files deleted on disk) plus the ignored files under `style/` (technique preview clips, 5 MB, tests need them). Never sent: `.env*`, `books/ library/ projects/ demo_runs/ research_media/`, `._*`, `.DS_Store`. It copies one `code-<id>.tgz` (and `data-<id>.tgz`) to `_deploy\`, then runs `remote_update.ps1` on the server, which: takes the lock folder `run\deploy.lock` (waits up to 20 minutes, polling every 5 s; a lock older than 30 minutes is treated as abandoned and taken over), unpacks, mirrors every code folder with `robocopy /MIR` (the Mac tree is the truth) with `.venv*`, `cache`, `logs`, `run`, `_deploy`, `__pycache__` protected, copies top-level files, refreshes `.venv` when `requirements.txt` changed (hash in `.venv\req.sha256`), and releases the lock. `--data` extraction overwrites same-named files and deletes nothing. Two deploys at the same time wait for each other (tested). Mid-deploy a running test may see half-copied files; do not deploy while someone's pytest run is in progress unless you accept that.
- The app is NOT restarted by a deploy unless `--restart` is given (agents deploy often).
- `remote_test.sh` / `remote_py.sh` ship the arguments as a JSON file and `run\remote_run.py` starts the interpreter without any shell, so spaces, quotes and non-ASCII in arguments survive (tested with `-c "print('é ü \"q\" a b')"`). The run is not retried after a dropped connection (it would start the tests twice); scp and the preparatory ssh are tried three times. Output is UTF-8, streamed; the exit code is pytest's. `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1` and `HF_HOME=cache\hf` are set for the child.
- Long runs: the ssh session stays open the whole time (`ServerAliveInterval=30`). If you run a suite of more than a few minutes, run `remote_test.sh` in the background on the Mac and redirect its output to a file.

## Start, stop, tunnel
- Start (detached through `Win32_Process Create`, logs to `logs\app.log`, refuses if 8560 is busy or memory is low):
  `ssh winbox-lan "powershell -NoProfile -ExecutionPolicy Bypass -File D:\code\behind-the-image\tools\deploy\start_app.ps1"`
- Stop (ends only the process tree in `run\app.pid`, only if its command line is ours):
  `ssh winbox-lan "powershell -NoProfile -ExecutionPolicy Bypass -File D:\code\behind-the-image\tools\deploy\stop_app.ps1"`
- Restart = stop then start, or `deploy_windows.sh --restart`.
- Health on the server: `ssh winbox-lan "curl.exe -s http://127.0.0.1:8560/api/health"` gives `{"ok":true,"engine":"real","media":"real"}`.
- Tunnel from the Mac (the Mac's 8560 is the owner's local app, so we use 8561): `ssh -N -L 8561:127.0.0.1:8560 winbox-lan &` then open `http://127.0.0.1:8561/`; stop it with `kill %1` (or the pid of that ssh). Tested: health and home page answer through it.
- `tools/run_editor.bat` is the foreground Windows twin of `run_editor.sh` (runs uvicorn in the console, installs requirements first); the server normally uses `tools/deploy/app.bat` (started by `start_app.ps1`; never edit it while the app runs).

## Environments (inside our folder only)
- `.venv`: Python 3.14.0 (made earlier from the comic interpreter, home is the system 3.14), 406 MB. `pip install -r requirements.txt` was run on 2026-11-16; every package has a cp314 Windows wheel (numpy 2.5.5, opencv-python 5.0.0.93, Pillow 13.0.0, pymupdf 2.1, pydantic-core 2.50.4, onnxruntime 1.32.0): no package had to be built, no fallback to 3.12 needed. `pytest` is in `requirements.txt`. Note that `pymupdf` 2.1 pulls `pymupdf4llm`, `pymupdf-layout` and `onnxruntime` (large); the Mac may have a lighter set.
- `.venv-align`: Python 3.12 (`C:\Users\ADMIN\AppData\Local\Programs\Python\Python312`), 285 MB, `faster-whisper` 1.2.1 (ctranslate2 4.9.0, CPU only). Created with `...\Python312\python.exe -m venv D:\code\behind-the-image\.venv-align` then `.venv-align\Scripts\python.exe -m pip install faster-whisper`.
- Model cache `D:\code\behind-the-image\cache\hf` (464 MB): `Systran/faster-whisper-small.en`. Exact download command (cmd.exe, nothing loaded, no heavy work):
  `set HF_HOME=D:\code\behind-the-image\cache\hf&& set HF_HUB_DISABLE_TELEMETRY=1&& D:\code\behind-the-image\.venv-align\Scripts\python.exe D:\code\behind-the-image\tools\deploy\download_model.py small.en`
  To use it set `HF_HOME` to that folder (the model is under `hub\`); `remote_run.py` already does.
- Not installed anywhere on purpose: torch, chatterbox (voice uses the comic repo's `.venv-chatterbox` by file path, see `R7_build_facts.md` E4).
- Tools on PATH (system, unchanged): ffmpeg/ffprobe 8.1 full build, git 2.53, Python 3.12 and 3.14 under `C:\Users\ADMIN\AppData\Local\Programs\Python\`.

### pip freeze, `.venv` (Python 3.14.0)
```
annotated-doc==0.0.6
annotated-types==0.8.0
anyio==4.16.0
attrs==26.1.0
certifi==2026.10.23
click==8.5.1
colorama==0.4.6
fastapi==0.163.1
flatbuffers==25.12.19
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
iniconfig==2.3.1
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
networkx==3.7
numpy==2.5.5
onnxruntime==1.32.0
opencv-python==5.0.0.93
opentelemetry-api==1.45.2
packaging==26.3
pillow==13.0.0
pluggy==1.7.0
protobuf==7.36.2
psutil==7.2.2
pydantic==2.14.3
pydantic_core==2.50.4
Pygments==2.21.0
pymupdf==2.1
pymupdf4llm==2.1
pymupdf_layout==2.1
pytest==9.2.0
python-multipart==0.0.34
PyYAML==6.0.3
referencing==0.37.0
rpds-py==2026.9.1
starlette==1.10.0
tabulate==0.10.0
typing-inspection==0.4.5
typing_extensions==4.16.0
uvicorn==0.54.0
```
### pip freeze, `.venv-align` (Python 3.12)
```
anyio==4.16.0
av==19.0.2
click==8.5.1
colorama==0.4.6
ctranslate2==4.9.0
faster-whisper==1.2.1
filelock==4.2.10
flatbuffers==25.12.19
fsspec==2026.9.0
h11==0.16.0
hf-xet==1.8.0
httpcore2==2.16.2
httpx2==2.16.2
huggingface_hub==2.4.0
idna==3.20
numpy==2.5.5
onnxruntime==1.32.0
packaging==26.3
protobuf==7.36.2
PyYAML==6.0.3
tokenizers==0.23.3
tqdm==4.70.1
truststore==0.10.5
typing_extensions==4.16.0
```

## Suites on the server, 2026-11-16 (code of that afternoon, `-W ignore`, one suite at a time, no `slow`)
| Suite | Result | Notes |
|---|---|---|
| `tests/script tests/editor tests/library` | 485 passed, 26 failed, 6 skipped (4 min 41 s) | 1 of the 26 (the styles preview test) passed after the preview clips were added to the deploy, so 25 remain. A second full run finished: 25 failed, 486 passed, 6 skipped in 4 min 33 s (the 25 are the table below). |
| `tests/media` | 85 passed, 5 failed (1 s) | not platform problems (see table) |
| `tests/engine -m "not slow"` without `test_real_projects_draw.py` | 231 passed, 1 failed, 14 skipped, 133 deselected (1 min 41 s) | skips: reel copies, `.scratch/r1`, lab projects that are not on the server |
| `tests/engine/test_real_projects_draw.py` (not marked `slow`) | 3 real projects pass (see "Why tests were slow") | about 23 to 29 s each on the server (about 6 s on the Mac); computing, not waiting |
| `tests/deep -m "not timing"` | 0 passed: 1 collection error, 194 setup errors | the suite cannot start on Windows (below) |

## Portability failures
| Test(s) | Class | Cause (file:line) | What phase 2 should do |
|---|---|---|---|
| 17 in `tests/script/test_antigravity.py` (`test_success_reads_the_json_envelope`, `..._empty_temp_folder...`, `test_failures_are_refused_with_a_kind[*]` x9, `test_prompt_states_english_and_no_tools`, `test_hard_timeout`, `test_one_call_at_a_time`, `test_models_listing_...`, `test_no_fallback_to_a_paid_api`, `test_cancel_kills_agy_and_its_children`) | POSIX-only fake program | the fake `agy` is a `#!/bin/sh` file made executable (`tests/script/test_antigravity.py:57`); `CreateProcess` answers `[WinError 193] %1 is not a valid Win32 application` at `bti/script/providers/antigravity.py:105` | apply the stash version of `antigravity.py` and `test_antigravity.py`, make the fake a `.cmd` or a tiny python launcher |
| `test_a_60000_character_prompt_reaches_the_cli_whole` | Windows command-line limit | the prompt is a `-p` argument (`antigravity.py:69/105`); `CreateProcess` allows about 32,767 characters: `[WinError 206]` | the stash moves the prompt to stdin (stream-json); keep that |
| `tests/editor/test_round3_scanners.py::test_valid_rows_with_odd_bytes_and_duplicates`, `::test_slug_is_checked_against_a_fresh_list`, `::test_no_lock_is_held_while_the_cli_runs` | POSIX-only fake program | `#!/bin/sh` script written at `test_round3_scanners.py:99-100` | same as above |
| `tests/editor/test_round3_scanners.py::test_depth_scan_is_linear_and_still_right` | timing | `test_round3_scanners.py:29`: 0.113 s against a 0.05 s limit on 2 MB (the server is slower than the Mac) | widen the limit or mark `timing` |
| `tests/editor/test_round2_fixes.py::test_project_files_of_the_wrong_shape_or_kind_are_409_and_recover` | POSIX-only call | `os.geteuid()` at `test_round2_fixes.py:760` (and the mode-000 file trick after it) | `skipif(os.name == "nt")` |
| `tests/deep/test_round3_backend.py` (whole `tests/deep` run aborts) | POSIX-only call | `os.geteuid()` at module level, `test_round3_backend.py:102`: collection error; use `--continue-on-collection-errors` to see the rest | `getattr(os, "geteuid", lambda: 1)()` |
| all 194 tests of `tests/deep` | POSIX-only program | `tests/deep/conftest.py:33` clones projects with `cp -Rc` (APFS); there is no `cp` on Windows: `[WinError 2]` | `shutil.copytree` fallback |
| `tests/library/test_library.py::test_counts[hagen_wgps-80]`, `::test_hagen_layout` | path length (MAX_PATH 260) | the book file name is about 230 characters; `D:\code\behind-the-image\books\<name>` is over 260, so `os.path.exists` is False although the directory listing shows it; `pymupdf.open(f)` at `bti/library/extract.py:25` (`config.book_pdf`, `bti/library/config.py:33-38`) raises `no such file`. Other books pass. | open the file through Python with a `\\?\` prefix and give pymupdf the bytes, or a short alias; do not enable long paths system-wide (a system change) |
| `tests/media/test_api.py` (`test_search_candidate_shape_and_licence_flags`:27, `test_import_rejects_licence_before_download`:75, `test_import_too_small`:85, `test_met_non_pd_rejected`:106, `test_add_upload_requires_fields_and_licence`:122) | real (not platform) | the tests expect the old blocking licence gate and key set; the PICKS agent was changing `bti/media` and its tests while the suite ran (the test file itself says "CHANGED (advisory gate...)"). Fake opener raises `unexpected URL`. I did not run the Mac side to compare (not allowed). | PICKS to settle; re-run |
| `tests/engine/test_t2_annot_highlight.py::test_lab_project_validates_and_every_shot_renders_fast_and_deterministically` | timing | `test_t2_annot_highlight.py:357`: six shots took 0.15 to 0.33 s against the fast-render limit | widen the limit on Windows |
| `tests/editor/test_integration_real.py::test_styles_are_merged_registry_with_preview_fallback` | deploy gap, fixed | the 70 preview `.mp4` clips under `style/gae/previews` are git-ignored, so a deploy that sends only non-ignored files lacked them; `deploy_windows.sh` now sends ignored files under `style/` | none |

Not seen as failures but known: path separators (the code uses `pathlib` and passed), encodings (`PYTHONUTF8=1` is set for every run and for the app; Vietnamese text in test data passed), fonts (Century Gothic is on the server, Futura is not: layout differs about 6 %; no test failed on it).

Other things learned
- Test files that need a real `agy`, the network or `demo_runs` were skipped or failed as listed; no test started anything heavy.
- Earlier text in this file claimed some runs took 10 to 25 minutes while idle. That was WRONG: it came from my own waiting (tool timers), not from the clock. See "Why tests were slow".
- `_deploy\` still holds old files from the first attempt (`code.tgz`, `data.tgz` 669 MB, helper `.ps1`). They are ours; safe to delete when space matters.
- `pymupdf` 2.1 installs `onnxruntime` and `pymupdf4llm`: heavy but harmless.

## What is left for phase 2 (after round 3 is committed)
1. Apply the stash for the four tracked files: `bti/editor/__main__.py` (UTF-8 streams), `bti/media/clips.py` (uses `bti/proc.py`), `bti/script/providers/antigravity.py` (stdin, Windows `agy` lookup) and `tests/script/test_antigravity.py`; rewrite the POSIX fakes as portable ones.
2. Fix the portability table above: `geteuid` (2 files), `cp -Rc` in `tests/deep/conftest.py`, MAX_PATH for the Hagen book, the three timing limits, the `slow` marker on `test_real_projects_draw.py`.
3. `agy` is not signed in over ssh (see design section 9): the owner decides how the app runs in the desktop session.
4. The heavy-job lock (`D:\bench\_heavy.lock`, memory and production checks) is not coded in `bti/`; the long-job runner (CORE) must take it for voice and render.
5. Per-agent folders: all agents share one tree and one `.venv`; deploys replace the whole tree, so two agents should not edit different branches' code at once. If that becomes a problem, give each agent its own `BTI_REMOTE` folder (the scripts honour `BTI_REMOTE`, but each would need its own `.venv`).

## Comic repo check (must be identical before and after)
`git -C D:\code\comic-book-pipeline status --short` before and after phase 1 (6 lines each, identical):
```
?? .chatterbox-runtime-cache/
?? assets/voices/arthur_ref.wav
?? data/
?? test_clip_1_1.py
?? voice_samples/build_voice_variant_20261110.py
?? voice_samples/machiavelli_20261110_status.json
```

## Why tests were slow (measured 2026-11-16, server clock 18:00 to 18:10)
Finding: nothing waits. My first report said the draw tests took 10 to 25 minutes while idle, and that a rerun was "slow and idle". That was a mistake in my own time keeping: I measured by the number of timer waits I had issued, not by the clock. The file times of the logs show the first full run ended 21:55 Mac time, the engine run took 100 s, and the whole draw run was killed after about 4 minutes. Measured now, with a clock:
| Measurement | Result |
|---|---|
| `open_project(...).draw_check()` on the server, outside pytest (`tools/deploy/probe_draw.py`, faulthandler stack every 15 s: always in `bti/engine/scene.py:195 frame_at`, called from `api.py:230 draw_check_iter`) | arnolfini 23.2 s, arnolfini_edit 23.4 s, technique_lab 28.7 s; `open` 0.0 s |
| same check, CPU time against wall time | wall 23.1 s, CPU 31.5 s (16 cores, OpenCV threads): it computes, it does not wait |
| same check inside pytest (`test_draw_check_of_a_real_project_is_clean[arnolfini]`, `-o faulthandler_timeout=20`) | 23.36 s call, 0.01 s setup: the test set-up adds nothing |
| `shutil.copytree` of `projects\arnolfini` (16 files, 105 MB) and `technique_lab` (27 files, 43 MB) into the temp folder `C:\Users\ADMIN\AppData\Local\Temp` | 0.1 s each: copying and the antivirus scanning of written files are not a cost (Defender settings untouched) |
| the three real projects in one pytest file | about 75 s in all |
| full `tests/script tests/editor tests/library` | 273.6 s (second run), 281.5 s (first run): same, so no run-to-run variation |
| `tests/engine -m "not slow"` without the draw file | 100.8 s |
So the server is simply about 4 times slower than the Mac for the engine's drawing (23 s against 6 s for the 82-shot project): per-frame compute, mostly in `scene.frame_at`. Not antivirus, not child processes, not a lock, not stdout. Suspects not needed: no `agy models`, ffprobe or PowerShell start sits on that path. What did turn out wrong was my first run of `remote_test.sh`: the child's stdout was block-buffered when piped, so a log stays empty until 8 KB are written; that is fixed (`PYTHONUNBUFFERED=1` in `remote_run.py`) and is the real reason a log looked frozen. A second small fix: `remote_run.py` now sets `PYTHONPATH` to the project folder, so `remote_py.sh some_script.py` can import `bti`.
Fix / advice: none needed for correctness. For speed, tell the agents that `tests/engine/test_real_projects_draw.py` costs about 75 s and the whole first suite about 4.5 minutes on the server, and run subsets (`-k`, one file) while developing.
