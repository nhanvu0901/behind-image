# BUILD_core: long jobs, heavy slot, server config (CORE, phase 1)

## Interface status

**PUBLISHED (2026-11-16).** `bti/longjob/__init__.py` exports `manager`, `Part`, `Context`, `Busy`, `PartError`, `router` (lazy), `LongJobManager`, `HeavySlot`, `load_config`. Compiles and imports on the Mac. Signatures follow section 4 of the design; the choices where it was open:

```python
from bti.longjob import manager, Part, Busy, PartError

job = manager.start(kind="voice", pid=pid, project_dir=d, parts=[Part(key=, title=, run=fn, heavy=True, est_seconds=900), ...], meta={})
#  -> the job's public record (a dict; job["id"] is the id). Raises Busy (Busy.job = the running job's record) when this
#     project already has a queued/waiting/running job of this kind. ValueError for a bad kind/pid/parts; ProjectGone (OSError) if d is missing.
#  kind: [a-z][a-z0-9_-]{0,31}; pid: [a-z0-9][a-z0-9_-]{0,63} (the app's PID_RE); part keys unique.
fn(ctx) -> dict | None          # the returned dicts are merged, in order, into job["result"]
ctx.progress(fraction, note="")  ctx.log(text)  ctx.cancelled() -> bool
ctx.run_process(cmd, cwd=None, env=None, on_line=None) -> int   # own process group; killed as a tree on cancel/overrun; the child is gone on return
ctx.workdir  # Path: <project>/cache/longjobs/work/<kind>/ (stable per kind, so a resumed job finds earlier scratch files)
ctx.job_id, ctx.meta
manager.get(job_or_id) / manager.cancel(job_or_id) -> bool / manager.active(pid, kind=None) -> record | None
manager.for_project(pid, kind=None) -> [record]  /  manager.wait(job_or_id, timeout)  (tests, scripts)
```

Additions beyond section 4 (all optional, nothing renamed):
- `Part(..., is_done=fn)`: `fn(ctx) -> bool`, asked **before** the heavy slot is taken. True = the part is done at once ("Đã có sẵn, bỏ qua."). Without it, a part that finds its output current just returns at once, but a heavy part would first wait for the slot. Stages with heavy parts should pass `is_done`.
- `PartError(code, message)`: raise it from a part to fail the job with your own `error_code` and a Vietnamese sentence.
- Record fields beyond the spec: `finished`, `meta`; each part also has `heavy`, `est_seconds`. `progress` of a job is weighted by `est_seconds` (60 s when missing).
- `manager.configure(projects_root=..., heavy=...)`, `manager.startup()` (release a dead lock of ours; also done lazily on the first heavy part).
- Fakes for any stage's tests: `bti.longjob.fakes` (`FakeClock`, `FakeProbes`, `FakeLockFolder`). Off the server (config block `"default"`, no lock folder) the heavy slot is the in-process mutex only, so stage tests need nothing.
- Config: `from bti.longjob import load_config; cfg = load_config()` gives `cfg.voice` (python, worker, reference_voice, exaggeration, cfg_weight, temperature, seed) or `None`, `cfg.aligner` (python, model, compute_type, beam_size) or `None`, `cfg.render_threads`, `cfg.part_seconds`, `cfg.lock_dir`. `None` means "the program is not available on this machine": use the fake or say so plainly.

States: job `queued | waiting | running | done | error | cancelled | interrupted`; part the same. Error codes set by the runner: `part_timeout` (35 min), `part_failed` (an exception in a part), `part_stuck`, `heavy_unavailable` (lock folder unusable), `project_gone`, `longjob_internal`, `interrupted` (after a restart). Not-found codes of the routes: `longjob_not_found`, `project_not_found`, `longjob_bad_kind`.

Routes (in `bti.longjob.api.router`, registered in phase 2): `GET /api/longjobs/{id}`, `POST /api/longjobs/{id}/cancel` (answers the record), `GET /api/projects/{pid}/longjobs?kind=` (`{items: [...]}` newest first).

## What exists

| File | What |
|---|---|
| `bti/longjob/manager.py` | `LongJobManager`, `Part`, `Context`, `Busy`, `PartError`; persistence in `projects/<pid>/cache/longjobs/<id>.json` (+ `<id>.log`); 35 min part limit (injectable clock); restart gives `interrupted`; keeps 30 records per project |
| `bti/longjob/heavy.py` | `HeavySlot`, the probe interfaces, real probes (`SystemProbes`: PowerShell/CIM on Windows, `ps` elsewhere), `DirLockFolder`, `owner.txt` format |
| `bti/longjob/fakes.py` | `FakeClock`, `FakeProbes`, `FakeLockFolder` |
| `bti/longjob/config.py` | reads `config/server.json` |
| `bti/longjob/api.py` | the router |
| `config/server.json` | `windows` and `default` blocks |
| `bti/proc.py` (WIN's) | used for `group_kwargs()` and `kill_tree()`; not edited |

Interpretations of section 4 worth knowing:
1. Heavy part = in-process mutex first, then (server only) the lock folder; the 35 min limit counts from the moment the slot is held, not from the wait.
2. A foreign lock older than 60 minutes: the benchmark said "stop and tell the human". The runner **reports** it (`slot.alerts`, and the part's note says so in Vietnamese) and keeps waiting, so the owner can cancel or free it. It never removes it. A lock whose `owner.txt` is missing or has another host or another `app=` marker counts as foreign.
3. "Ours" = `app=behind-the-image` and the same host in `owner.txt`. Release at the end of a part removes the folder only if the pid is also ours. A dead-pid lock of ours is released at start-up and also at each retry (otherwise a crashed second instance would block forever).
4. Memory unknown (probe failed) on the server counts as "not free", with a note.
5. "No ffmpeg that is not ours": an ffmpeg is ours when it descends from this process or its command line contains the repo path (`own_markers`).
6. A part that ignores cancel is abandoned after 10 s (its thread is a daemon); its child processes are already killed.

## Tested

**Server run (Windows, .venv Python 3.14): 65 passed, 1 skipped (the POSIX-only grandchild test), 8 s.** Includes `test_longjob_server.py` (3 tests marked `server`: real free-memory probe, process list, pid check; read-only). Only change needed for Windows: a test patched `bti.longjob.manager.KEEP_PER_PROJECT` by dotted path, which resolves to the `manager` instance because the package exports it under that name; it now uses `sys.modules`. Run with `tools/deploy/remote_test.sh tests/longjob`.

- `tests/longjob/test_longjob_heavy.py` (about 25 tests): owner.txt format; take and release; release on exception; no lock folder = in-process only; mutex serialises, tells the waiter and is cancellable; low and unknown memory wait 60 s (fake clock); production patterns (three) block; foreign ffmpeg blocks, ours (child, grandchild, own path) does not; foreign lock waits and is never removed; older than 60 min is reported not removed; lock without owner.txt, same pid on another host and another `app=` are foreign; our dead lock released at start-up and at retry, a live one and foreign ones kept; release leaves a lock that is no longer ours; cancel while waiting; retry cadence (11 attempts in 600 s, one-second slices); owner write failure; real `DirLockFolder` on a temp folder.
- `tests/longjob/test_longjob_manager.py` (about 28 tests): parts in order, results merge; progress weighted and visible; same kind refused (also under 8 racing starts), other kind or project allowed; bad arguments; cancel kills the child and a grandchild (pid checked dead); `run_process` code and lines; overrun at 35 min with a fake clock kills the child; a part that ignores cancel is abandoned; `part_failed` and `PartError` codes; resume with `is_done`; workdir; restart gives `interrupted`; listing, pruning, deleted project never re-created; two heavy parts of two projects never overlap; `waiting` state with the Vietnamese note; cancel while waiting; `is_done` skips the slot; slot released after each part and after a failure; the three routes.
- `tests/longjob/test_longjob_config.py` (4 tests): both blocks, fallbacks.
- No test takes the real `D:\bench\_heavy.lock`, runs PowerShell probes, or waits real minutes (the only real waits are child processes and sub-second thread timeouts).
- Not covered by any test: `SystemProbes` on Windows (PowerShell/CIM output parsing, `pid_alive` through ctypes). A `server`-marked check on the server is worth one run (`SystemProbes().free_virtual_kb()`, `.processes()`).

## Wiring plan for phase 2 (nothing edited yet)

- `bti/editor/app.py`: after `root` is known, `from bti.longjob import manager, router as longjob_router; manager.configure(projects_root=root); manager.startup(); app.include_router(longjob_router)`; then one `include_router` per stage router (`voice_api`, `picks_api`, `draft_api`, `export_api`), each guarded by a try/import so a missing stage does not break the app until all four exist. Delete-project must refuse or cancel a project with an active long job (`manager.active(pid)`), same as it does for script jobs.
- `bti/editor/pipeline_api.py`: step states from each stage's `state(project_dir)` (`none|running|stale|done`): step 3 from `bti.voice.state`, step 4 from `bti.picks.state`, step 6 from `bti.export.state`; `running` shown on the stepper from `manager.active(pid, kind)` as well.
- `bti/library/projects.py`: stage inference `voiced`, `picked`, `storyboard`, `approved`, `rendered` as "the furthest step for which every earlier step is done" from those states; one pure function taking the four state dicts, unit-tested.
- `static/js/{router,stepper}.js`: routes `voice`, `picks`, `export` mount the views of VOICE, PICKS, EXPORT; the three placeholder views are removed. Stepper shows waiting/running/stale per step.
- `labels.js`, `errmsg.js`: merge the lists in each agent's report plus the runner codes above.
- `bti/editor/proposals.py`: `apply` with `accept: "all"` on a project without `storyboard.json` adopts the proposal's document as the first storyboard (with `_rev` check skipped because there is no base).
- Step 5 view: hook `draftpanel.js` (DRAFT) into the storyboard view's toolbar; the panel polls `/api/longjobs/{id}`.
- `docs/APP_GUIDE.md`: merge the guide sections from the four reports.

## Open questions

- Should `start` return only the id? I return the record (a dict with `id`); `get/cancel/wait` take either. Say if the other agents expect a bare string.
- Real probes (`SystemProbes` on Windows) are untested until the server run; they only matter when `lock_dir` is set.
