# QA Report: Task T0 - Snapshot Tests on Windows Server

## 1. What was built

We created a private snapshot test system that allows concurrent workers to sync, execute Python tests, and run arbitrary Python scripts on the Windows server without touching the main deployment folder (`D:\code\behind-the-image`), without taking the deploy lock, and without disturbing the running web app on port 8560:

- `tools/deploy/snapshot_test.sh NAME [--no-sync] [--refdata] -- <pytest arguments>`:
  - Validates `NAME` matching `^[a-z0-9-]{1,24}$`.
  - Syncs the Mac working tree (tracked and untracked not ignored, plus ignored clips under `style/`; strictly excludes `.env*`, `books/`, `library/`, `projects/`, `demo_runs/`, `research_media/`, `.scratch/`, `.venv*`) to `.scratch/snap/NAME.tgz` and transfers it to the server at `D:\code\behind-the-image\run\snap-NAME.tgz`.
  - Unpacks into `D:\code\behind-the-image\run\snap-NAME\` such that files deleted locally disappear from the server snapshot as well.
  - Configures directory junctions:
    - `run\snap-NAME\library` -> `D:\code\behind-the-image\library`
    - `run\snap-NAME\books` -> `D:\code\behind-the-image\books`
    - `run\snap-NAME\projects` -> `D:\code\behind-the-image\run\refdata\projects`
  - `--refdata` (or automatically when `run\refdata\projects` is missing): packs reference projects (`arnolfini`, `arnolfini_edit`, `arnolfini-from-books`, `technique_lab`, `demo_stub`, `lab_annot`, `lab_diagrams`, `lab_layouts`, `lab_text`, omitting `cache` and `history`) to `D:\code\behind-the-image\run\refdata\projects`.
  - Refuses heavy tests (`-m slow` and `-m server`) unless `BTI_ALLOW_HEAVY=1`.
  - Runs pytest with `PYTHONUTF8=1`, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`, and `BTI_NO_REAL_MODELS=1` via `-p no:cacheprovider`, streaming UTF-8 output and propagating exit code.

- `tools/deploy/snapshot_py.sh NAME <python arguments>`:
  - Executes one-off python commands with the identical snapshot working directory and environment.

- `tools/deploy/snapshot_rm.sh NAME`:
  - Safely deletes the snapshot: removes directory junctions (`library`, `books`, `projects`) first using non-recursive `rmdir` so target folders are never touched, removes `run\snap-NAME\`, and removes local/server archive `.tgz` files.

- Documentation:
  - Added "Snapshot tests" section to `docs/WINDOWS.md` detailing purpose, commands, directory layout, and hard safety rules.

---

## 2. Verification Outputs

### 1. `tools/deploy/snapshot_test.sh t0 --refdata -- tests/longjob -q`
```
== sync reference projects to run/refdata/projects
== pack snapshot t0
== copy snapshot t0 to server
== unpack snapshot t0 and setup junctions
Junction created for D:\code\behind-the-image\run\snap-t0\library <<===>> D:\code\behind-the-image\library
Junction created for D:\code\behind-the-image\run\snap-t0\books <<===>> D:\code\behind-the-image\books
Junction created for D:\code\behind-the-image\run\snap-t0\projects <<===>> D:\code\behind-the-image\run\refdata\projects
........................................s.............................   [100%]
============================== warnings summary ===============================
tests/longjob/test_longjob_manager.py::test_routes
  D:\code\behind-the-image\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
69 passed, 1 skipped, 1 warning in 6.83s
```
**Exit code:** 0.

---

### 2. `tools/deploy/snapshot_test.sh t0 --no-sync -- tests/editor -q`
```
........................................................................ [ 17%]
........................................................................ [ 34%]
........................................................................ [ 52%]
........................................................................ [ 69%]
........................................................................ [ 87%]
.....................................................                    [100%]
============================== warnings summary ===============================
..\..\.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\code\behind-the-image\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
413 passed, 1 warning in 224.90s (0:03:44)
```
**Counts:** 413 passed, 0 skipped, 0 failed.
**Reference projects skip check:** NO tests were skipped for "reference projects are missing".

---

### 3. Concurrent Syncs (`t0a` and `t0b`) & Teardown
- Launched `t0a` and `t0b` simultaneously in background. Both completed successfully:
  ```
  rc1=0 rc2=0
  == pack snapshot t0a
  == copy snapshot t0a to server
  == unpack snapshot t0a and setup junctions
  Junction created for D:\code\behind-the-image\run\snap-t0a\library <<===>> D:\code\behind-the-image\library
  Junction created for D:\code\behind-the-image\run\snap-t0a\books <<===>> D:\code\behind-the-image\books
  Junction created for D:\code\behind-the-image\run\snap-t0a\projects <<===>> D:\code\behind-the-image\run\refdata\projects
  ....                                                                     [100%]
  4 passed in 0.09s
  == pack snapshot t0b
  == copy snapshot t0b to server
  == unpack snapshot t0b and setup junctions
  Junction created for D:\code\behind-the-image\run\snap-t0b\library <<===>> D:\code\behind-the-image\library
  Junction created for D:\code\behind-the-image\run\snap-t0b\books <<===>> D:\code\behind-the-image\books
  Junction created for D:\code\behind-the-image\run\snap-t0b\projects <<===>> D:\code\behind-the-image\run\refdata\projects
  ....                                                                     [100%]
  4 passed in 2.64s
  ```
- Removed both snapshots via `snapshot_rm.sh t0a && tools/deploy/snapshot_rm.sh t0b`:
  ```
  == remove snapshot t0a on server
  == remove local archive
  snapshot t0a removed
  == remove snapshot t0b on server
  == remove local archive
  snapshot t0b removed
  ```
- Post-run verification of server state:
  - App PID: `3928` (unchanged from baseline `3928`)
  - Hash of `D:\code\behind-the-image\bti\editor\app.py`: `6FB2C90E3B0A74067B6C270F1C661BA7709FBCE49B731073C0F5474D55FABE22` (unchanged from baseline)
  - Health check `GET http://127.0.0.1:8560/api/health`: `{"ok":true,"engine":"real","media":"real"}`
  - Main `library` directory contents: `books`, `cache`, `clean_text`, `dossiers`, `overrides`, `text_audit`, `artworks.json`, `unparsed.json` (fully intact)

---

## 3. Anything Odd / Notes

- **cmd.exe chaining quirk:** In Windows `cmd.exe`, chaining commands as `if exist <path> <cmd> && <cmd2>` treats `<cmd2>` as conditional on the `if` evaluating to true. Grouping conditionals with parentheses `(if exist <path> <cmd>) & <cmd2>` ensures sequential execution regardless of whether the path exists.
- **Starlette warning:** `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated` emitted by `fastapi.testclient`; normal for the installed environment package versions.
