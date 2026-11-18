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
| Deploy a snapshot instead of the working tree (when the tree is mid-edit): `git archive HEAD | tar -x -C DIR`, overlay your files, then | `tools/deploy/deploy_windows.sh --root DIR` |
| Heavy pytest run under the heavy slot (lock folder, memory and production checks, 28 min limit, detached) | `scp tools/deploy/launch_heavy.ps1 winbox-lan:D:/code/behind-the-image/run/` then `ssh winbox-lan "powershell -NoProfile -ExecutionPolicy Bypass -File D:\code\behind-the-image\run\launch_heavy.ps1 -What \"what runs\" -Minutes 28 -PytestArgs \"tests/engine -m slow -q\""`; progress in `logs\heavy_run.log` (`LOCK TAKEN`, `LOCK RELEASED`, `EXIT=`) |
| Deploy, then run pytest on the server | `tools/deploy/remote_test.sh tests/script -q -x` |
| Run pytest without deploying | `tools/deploy/remote_test.sh --no-sync tests/editor -k name` |
| Run pytest in a private snapshot (no deploy lock, safe for concurrent workers) | `tools/deploy/snapshot_test.sh NAME -- tests/longjob -q` |
| Run one-off python in snapshot | `tools/deploy/snapshot_py.sh NAME -c "import bti"` |
| Remove private snapshot and archive | `tools/deploy/snapshot_rm.sh NAME` |
| Any one-off python check | `tools/deploy/remote_py.sh -c "import sys; print(sys.version)"` |
| The same in the Python 3.12 align venv | `tools/deploy/remote_py.sh --venv align -c "import faster_whisper"` |

- `deploy_windows.sh` packs `git ls-files -c -o --exclude-standard` (tracked plus untracked-not-ignored, skipping files deleted on disk) plus the ignored files under `style/` (technique preview clips, 5 MB, tests need them). Never sent: `.env*`, `books/ library/ projects/ demo_runs/ research_media/`, `._*`, `.DS_Store`. It copies one `code-<id>.tgz` (and `data-<id>.tgz`) to `_deploy\`, then runs `remote_update.ps1` on the server, which: takes the lock folder `run\deploy.lock` (waits up to 20 minutes, polling every 5 s; a lock older than 30 minutes is treated as abandoned and taken over), unpacks, mirrors every code folder with `robocopy /MIR` (the Mac tree is the truth) with `.venv*`, `cache`, `logs`, `run`, `_deploy`, `__pycache__` protected, copies top-level files, refreshes `.venv` when `requirements.txt` changed (hash in `.venv\req.sha256`), and releases the lock. `--data` extraction overwrites same-named files and deletes nothing. Two deploys at the same time wait for each other (tested). Mid-deploy a running test may see half-copied files; do not deploy while someone's pytest run is in progress unless you accept that.
- The app is NOT restarted by a deploy unless `--restart` is given (agents deploy often).
- `remote_test.sh` / `remote_py.sh` ship the arguments as a JSON file and `run\remote_run.py` starts the interpreter without any shell, so spaces, quotes and non-ASCII in arguments survive (tested with `-c "print('é ü \"q\" a b')"`). The run is not retried after a dropped connection (it would start the tests twice); scp and the preparatory ssh are tried three times. Output is UTF-8, streamed; the exit code is pytest's. `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1` and `HF_HOME=cache\hf` are set for the child.
- Long runs: the ssh session stays open the whole time (`ServerAliveInterval=30`). If you run a suite of more than a few minutes, run `remote_test.sh` in the background on the Mac and redirect its output to a file.

## Snapshot tests

Runs Python tests in an isolated, private copy of the repository on the Windows server, without touching the server's main working folder or disturbing the running app. Multiple workers can sync, run tests, and clean up snapshots simultaneously without stepping on each other or taking the deploy lock.

### Commands
| What | Command |
|---|---|
| Run tests in a snapshot (syncs tree + refdata if needed) | `tools/deploy/snapshot_test.sh NAME [--no-sync] [--refdata] -- <pytest arguments>` |
| Run a one-off python command in the snapshot environment | `tools/deploy/snapshot_py.sh NAME <python arguments>` |
| Remove snapshot and its archives | `tools/deploy/snapshot_rm.sh NAME` |

### Where things live
- `NAME` matches `[a-z0-9-]{1,24}`.
- Private snapshot checkout: `D:\code\behind-the-image\run\snap-NAME\` on the server (`run\` is never touched by a deploy).
- Archive files: `.scratch/snap/NAME.tgz` (Mac) and `D:\code\behind-the-image\run\snap-NAME.tgz` (server).
- Shared reference projects: `D:\code\behind-the-image\run\refdata\projects` (synced automatically if missing or with `--refdata`, shared read-only by all snapshots).
- Data junctions inside each snapshot:
  - `library` -> directory junction to `D:\code\behind-the-image\library`
  - `books` -> directory junction to `D:\code\behind-the-image\books`
  - `projects` -> directory junction to `D:\code\behind-the-image\run\refdata\projects`

### Rules
- Never write into the server's main code folders (`bti`, `tests`, `tools`, `config`, `prompts`, `style`, `skills`, `docs`) or main data folders (`projects`, `library`, `books`).
- Never stop, restart, or redeploy the app on port 8560; do not take `deploy.lock`.
- Removing a snapshot must never follow directory junctions into main data: always remove junctions with non-recursive `rmdir` first before deleting the snapshot folder (`snapshot_rm.sh` handles this).
- Tests run with `PYTHONUTF8=1`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`, and `BTI_NO_REAL_MODELS=1`.
- Heavy tests (`-m slow`, `-m server`) are refused unless `BTI_ALLOW_HEAVY=1`.

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

## Suites on the server, phase 2 (2026-11-16, `-W ignore`, one suite at a time)
Code on the server: HEAD `ba8ac37` plus the phase 2 changes below (deployed from a snapshot, `deploy_windows.sh --root DIR`, because another agent was editing `app.py` on the Mac).
| Suite | Result |
|---|---|
| `tests/script tests/editor tests/library` | 574 passed, 6 skipped (6 min 1 s) |
| `tests/media` | 106 passed (5 s) |
| `tests/engine -m "not slow"` | 234 passed, 14 skipped, 136 deselected (1 min 36 s) |
| `tests/deep -m "not timing"` | 1 failed on the first run (`test_sweep.py::test_technique[HI-02]`, a timing limit, fixed: see below), then 214 passed, 4 skipped, and HI-02 alone passes |
| `tests/longjob` | 65 passed, 1 skipped (12 s) |
| `tests/voice` | 64 passed, 1 skipped (48 s) |
| `tests/picks` | 43 passed (6 s) |
| `tests/draft` | 82 passed (1 min 17 s) |
| `tests/export` | 92 passed, 2 skipped (22 s) |
| `tests/engine -m slow` (heavy slot, `launch_heavy.ps1`) | 136 passed in 14 min 41 s; lock `D:\bench\_heavy.lock` taken at 19:09:28 and released at 19:24:11 server time, checks passed (no production process, memory above the floor). The first attempt failed at set-up in 72 s on `import resource` (POSIX only): `tests/engine/test_validate_draw_sweep.py` `_maxrss()` now uses the Windows peak working set. |
Run each stage folder in its own pytest call (`tests/voice`, `tests/draft`, ...): their `conftest.py` files share the module name `conftest`, and `from conftest import ...` then finds the first one (collection errors when mixed). Skips are the ones that need `demo_runs` or the reel copies, the mode-000 tests (not possible on Windows) and a symlink test.

## Portability failures of phase 1, and how each was fixed
| Cause | Fix (file) |
|---|---|
| `#!/bin/sh` fake `agy` (`WinError 193`) | the fake is a Python script started through the interpreter: a `.cmd` launcher on Windows, a `#!python` script elsewhere (`tests/script/test_antigravity.py`, `tests/editor/test_round3_scanners.py`, `tests/deep/test_round3_backend.py`) |
| prompt as `-p` argument over the 32 KB command line limit (`WinError 206`) | the stash version of the provider: prompt on standard input as one stream-json line (`bti/script/providers/antigravity.py`) |
| `os.geteuid` | `tests/editor/test_round2_fixes.py:760`, `tests/deep/test_round3_backend.py:102`: not run on Windows (no mode-000 files there) |
| `cp -Rc` | `tests/deep/conftest.py`: the clone copy only on macOS, `shutil.copytree` elsewhere |
| book path over 260 characters | `bti/library/config.py` `long_path()`: `book_pdf()` returns the `\\?\` extended-length path on Windows when the path is 240 characters or longer; pymupdf opens it. No file renamed, no setting changed. |
| timing limits | `tests/engine/test_t2_annot_highlight.py:357` 0.15 s to 0.75 s (5x; the Windows server needs 0.15 to 0.33 s; the limit only guards "a shot renders fast", a real slowdown is seconds); `tests/deep/sweep.py` `WARM_LIMIT_MS` 300 to 1500 (5x; measured 373 ms; a frame that is not cached takes seconds) and `tests/deep/test_sweep.py:54` uses it. `test_round3_scanners.py` had already been made a ratio by the round 3 fix. |
| slow | `tests/engine/test_real_projects_draw.py`: the three-project test is marked `slow` (about 75 s on the server) |
| `tests/media` | green now that the PICKS agent finished |
Also from the stash: `bti/editor/__main__.py` (UTF-8 stdout and stderr), `bti/media/clips.py` (`bti/proc.py` for the process group and the tree kill), and `antigravity.py` keeps every round 2 and round 3 behaviour (lenient model list, `LIST_TIMEOUT_S = 8`, slug filter, duplicate removal) while adding: `find_agy` for `%LOCALAPPDATA%\agy\bin` and `PATHEXT`, a Windows environment whitelist, `check_cli` (refuses an `agy` without `--settings` and `--input-format`), stream-json in and out, process-tree kill. The stream-json event shapes (`init`, `step_update`, `result`) are those the stash author wrote; they are NOT verified against a real `agy` run (no prompt may be run from here, and `agy` is not signed in on the server). The first real script run must check them.

## Parallel draw check (measurement only, no product change)
Scratch scripts `tools/deploy/probe_parallel.py` and `probe_parallel_cold.py` (through `remote_py.sh`; copy to `run\` first): the 300 samples of the draw check of `arnolfini` (82 shots, 320 px), drawn with `scene.frame_at` from a thread pool; every frame is hashed and compared with the serial result.
| Run | Wall time | Frames identical to serial |
|---|---|---|
| serial (cold process, includes the cv2 and asset warm-up) | 23 s | reference |
| serial, warm | 17 to 19 s (CPU 27 s) | reference |
| 4 threads, first thing in the process | 9.3 s | 300 of 300 |
| 8 threads, first thing in the process | 7.1 s | 300 of 300 |
| 4 / 8 threads after a serial pass (warm caches) | 6.6 s / 5.2 s | 300 of 300 |
| 16 threads, OpenCV single-threaded, warm | 4.9 s (CPU 41 s) | 300 of 300 |
So frames are drawn correctly in parallel (byte for byte), and 4 threads give about 2.5 times, 8 threads about 3.3 times from a cold start. Threads share the scene object; no error or difference appeared in 300 samples, but that is evidence, not a proof of thread safety of every technique (caches inside `scene` are the place to review before a change). The engine was not changed.

## Scheduled task `bti-editor` (prepared, NOT created)
Why: `agy` is signed in at the server's desktop; a process started over ssh or `Win32_Process Create` cannot see that sign-in. A task that runs in the desktop session can. This is a system change. I was told the owner approved it, but that reached me only through the coordinator agent, not from the owner or the permission system, so I did NOT create it. Everything is prepared and nothing else changes until someone with the owner's yes runs the one command:
- Create (once, on the server, as `admin`): `powershell -NoProfile -ExecutionPolicy Bypass -File D:\code\behind-the-image\tools\deploy\create_task.ps1`. It registers one task `bti-editor` for the current user, interactive logon, normal privileges, NO trigger, action `powershell -WindowStyle Hidden -File tools\deploy\task_app.ps1` (which starts `run\app.bat` hidden and writes `run\app.pid`). The owner sees at most a brief flash of a window.
- `start_app.ps1` already uses it when the task exists and a user is at the console (`schtasks /run /tn bti-editor`, waits for port 8560, prints the session id); otherwise it prints one line, "starting WITHOUT the desktop session: agy will not be available", and starts the old way. `stop_app.ps1` is unchanged (pid in `run\app.pid`, command line checked).
- Remove: `schtasks /delete /tn bti-editor /f`.
- Proof to run after creating it: stop the running app, `start_app.ps1`, then `GET /api/models?refresh=1` through the tunnel must list the Antigravity models with `agy.ok` true, and `Get-Process -Id <pid> | Select SessionId` must show the console session (`query user`).

## For CORE
- Nothing in your files failed on Windows. Mid-edit states do fail (`app.py` passing `longjobs=` to a `pipeline_api.make_router` that did not take it yet): agents who test on the server should deploy a snapshot (`--root`) of HEAD plus their own files while the tree is mid-edit.
- The stage test folders must be run one per pytest call (the shared module name `conftest`); renaming the shared helpers (for example `tests/draft/conftest.py` helpers imported by `tests/voice` and `tests/export`) or `--import-mode=importlib` would remove that rule. Left as it is.
- `bti/draft/workspace.py` already writes `.cmd` wrappers on Windows; `agy.py` has Windows lookup. `config/server.json` `windows.lock_dir` is the real `D:/bench/_heavy.lock`: any test that builds the default `HeavySlot` on the server would take the REAL lock; tests must pass a fake lock folder (they do today).

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
