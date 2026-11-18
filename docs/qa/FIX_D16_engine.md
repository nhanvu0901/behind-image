# Fix Report: D16 - Parallel Draw-Check and Thread Safety

## 1. Cause
In the storyboard approval flow (`POST /api/projects/{pid}/approve`), the backend executes `draw_check` across all shots, overlays, and transitions to verify that every item in the storyboard can actually be rendered without error.
On the reference 82-shot project `arnolfini`, this requires drawing ~300 sample frames at 320 px width.

Prior to this fix:
- Samples were drawn completely serially in a single thread.
- On the Windows server (`DESKTOP-4V6D49N`), drawing the 300 samples serially took ~23 s from a cold start (15.5 s to 19 s warm).
- In R3B-001, `bti/editor/engine_adapter.py` introduced `draw_check_stepwise` to yield `ENGINE_LOCK` between samples, but because each sample draw still acquired `ENGINE_LOCK` serially, the total compute duration was not reduced and concurrent requests still had to interleave with serial CPU-heavy rendering.

## 2. Audit of Shared Mutable State
We performed a full code and AST audit of every piece of state touched during a frame draw (`scene.py`, `vfx.py`, `helpers.py`, image pyramids, fonts, media checks, registry, and technique modules):

| Component / File | Shared Mutable State | Concurrency Risk Before Fix | Fix Applied |
|---|---|---|---|
| `bti/engine/vfx.py` | `_FONT_CACHE: dict` & `_FONTS: dict` | Concurrent font lookup and `configure_fonts()` clearing/mutating without lock | Protected by `_FONT_LOCK = threading.RLock()`. Lookups use double-checked locking; font loading occurs outside lock. |
| `bti/engine/vfx.py` | `_BD: dict` (backdrop cache) | Concurrent `backdrop(ow, oh)` writes without lock | Protected by `_BD_LOCK = threading.RLock()` with double-checked locking. |
| `bti/engine/techniques/_t3common.py` | `_CACHE: dict` (serif font cache) | Concurrent `font("serif", size)` writes without lock | Protected by `_CACHE_LOCK = threading.RLock()`. |
| `bti/engine/storyboard.py` | `_MEDIA_OK: dict` (media check cache) | `media_problem()` writes and clears cache (`len > 4000`) without lock | Protected by `_MEDIA_LOCK = threading.RLock()`. |
| `bti/engine/registry.py` | `_BUNDLES: dict`, `_PATTERNS: dict` | `load_bundle()` and `_pattern()` cached entries populated dynamically without lock | Protected by `_BUNDLE_LOCK` and `_PATTERN_LOCK` (`threading.RLock()`). |
| `bti/engine/api.py` | `Project._scenes`, `Project._timings` | Project-level scene and timing caches accessed concurrently | Protected by `self._lock = threading.RLock()` on `Project`. |
| `bti/engine/guard.py` | `_state: threading.local` | Pixel count guard depth | Already thread-local (`threading.local()`). Verified thread-safe. |
| `bti/engine/base.py` | `IMAGES`, `LAYERS`, `MISC` | Process-wide LRU caches | Already protected by `_LRU._lock = threading.RLock()`. Verified thread-safe. |
| `bti/engine/helpers.py` | `_VIDEOS: OrderedDict` | Video frame decoders | Already protected by `_VLOCK = threading.RLock()`. Verified thread-safe. |
| `bti/engine/techniques/shorts.py` | `cv2.setRNGSeed` / `cv2.kmeans` | Global OpenCV RNG seed | Already protected by `_KM_LOCK = threading.Lock()`. Verified thread-safe. |
| `vfx.Img` (image pyramid) | `self.levels` | Multi-resolution image pyramid levels | Read-only after `__init__`. Verified thread-safe. |
| All renderers (`render`, `apply`, `view`) | Frame scratch buffers | Risk of shared buffers between frames | Verified via AST scan: 0 assignments to `self.*` during frame draw; all buffers are function-local. |

## 3. What Was Changed (`file:line`)
- `bti/engine/vfx.py`:
  - `L12, L32`: Added `threading` import and `_FONT_LOCK = threading.RLock()`.
  - `L50`: Protected `_FONTS` mutation and `_FONT_CACHE.clear()` in `configure_fonts()` under `_FONT_LOCK`.
  - `L60`: Protected `font_signature()` under `_FONT_LOCK`.
  - `L67-L86`: Thread-safe `font()` with double-checked locking.
  - `L172, L177-L189`: Added `_BD_LOCK = threading.RLock()` and double-checked locking in `backdrop()`.
- `bti/engine/techniques/_t3common.py`:
  - `L4, L21, L30-L42`: Added `_CACHE_LOCK = threading.RLock()` and double-checked locking in `font()`.
- `bti/engine/storyboard.py`:
  - `L12, L281, L314-L323`: Added `_MEDIA_LOCK = threading.RLock()` and synchronized cache access/clear in `media_problem()`.
- `bti/engine/registry.py`:
  - `L16, L117, L126-L132`: Added `_BUNDLE_LOCK` and synchronized `load_bundle()`.
  - `L180, L184-L188`: Added `_PATTERN_LOCK` and synchronized `_pattern()`.
- `bti/engine/api.py`:
  - `L33-L49`: Added `_default_check_threads()`: reads `check_threads` from `config/server.json` (defaults to 8 on Windows/server, 4 elsewhere).
  - `L77`: Added `self._lock = threading.RLock()` to `Project`.
  - `L107, L165`: Synchronized `_timing_for()` and `_scene()` under `self._lock`.
  - `L194-L200`: `Project.draw_check(storyboard=None, width=320, threads=None)`.
  - `L203-L277`: `Project.draw_check_iter(storyboard=None, width=320, threads=None)`:
    - Step 1 (compile): compiled once up front and yields.
    - Samples: submitted to `concurrent.futures.ThreadPoolExecutor(max_workers=n_threads)`.
    - Yields after each sample finishes.
    - Failures collected and reported in exact deterministic shot/sample order.
    - `finally: executor.shutdown(wait=True, cancel_futures=True)` guarantees immediate cleanup on completion, cancellation, or error.
- `bti/editor/engine_adapter.py`:
  - `L23-L43`: `draw_check_stepwise(project, storyboard=None, width=320, threads=None)`:
    - Holds `ENGINE_LOCK` ONLY for the first compile step.
    - Releases `ENGINE_LOCK` completely during thread-pool sample drawing so all concurrent editor requests are served immediately.
- `bti/editor/app.py`:
  - `L508-L510`: Updated approve comments and retained clean invocation of `draw_check_stepwise(p, saved)`.
- `tests/engine/test_d16_parallel_draw_check.py`:
  - New test suite covering `threads` argument, defaults, byte-identity comparison on `arnolfini` and `technique_lab`, undrawable reporting, cancellation thread cleanup, and exception thread cleanup.

## 4. Neighbouring Cases Covered
- Single-threaded fallback (`threads=1` or 1 sample job) executes directly without spawning a thread pool.
- Generator cancellation (`it.close()` midway) invokes `executor.shutdown(wait=True, cancel_futures=True)` to cancel pending futures and join active threads without leakage.
- Unhandled exceptions inside sample drawing cancel pending futures and terminate worker threads.
- Undrawable shots continue to report the exact `shot_id` and `path`.
- Deterministic error ordering: sample errors are collected by job index so output issues match serial order regardless of completion order in the pool.
- Backward compatibility: callers or monkeypatched fakes with `draw_check_iter(sb, width)` without `threads` keyword are handled transparently.

## 5. Tests, Counts, and Execution Locations
- **Windows Server Snapshot (`snap-dengine`, Python 3.14.0)** via `tools/deploy/snapshot_test.sh`:
  - `tests/engine/test_d16_parallel_draw_check.py`: **7 passed** in 69.08s
    - `test_draw_check_threads_parameter_accepted` PASSED
    - `test_default_check_threads` PASSED
    - `test_pooled_draw_check_frames_byte_identical_to_serial[arnolfini]` PASSED
    - `test_pooled_draw_check_frames_byte_identical_to_serial[technique_lab]` PASSED
    - `test_undrawable_shot_reported_for_right_shot` PASSED
    - `test_cancellation_does_not_leave_threads_behind` PASSED
    - `test_exception_in_sample_does_not_leave_threads_behind` PASSED
  - `tests/editor/test_round3_approve_lock.py`: **1 passed** in 8.85s
  - `tests/editor/test_round2_fixes.py -k test_approve_runs_draw_check`: **1 passed, 63 deselected** in 12.66s
  - `tests/engine -m "not slow"`: **241 passed, 14 skipped, 136 deselected** in 138.38s
- **Mac (Node.js)**:
  - `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`: **188 passed** in 700ms

## 6. Measurements on Windows Server (`snapshot_py.sh dengine`)
Measured on `DESKTOP-4V6D49N` with `projects/arnolfini` (82 shots, ~300 samples, 320 px):

| Metric | Before (Serial / R3B-001) | After (D16 Pooled Check) | Improvement |
|---|---|---|---|
| Direct `draw_check` (300 samples) | 15.51 s (warm) / 23.2 s (cold) | **3.39 s** (8 threads) | **4.6x - 6.8x faster** |
| Direct `draw_check` (4 threads) | 15.51 s | 4.95 s | 3.1x faster |
| Full `/api/projects/arnolfini/approve` wall time | ~17 - 24 s | **5.26 s** (total) | ~4x faster |
| Concurrent `GET /api/projects/technique_lab` during approval | 45 ms median (blocked during compile) | **103.0 ms median**, 188.9 ms max | < 0.2 s (target < 0.5 s) |
| Concurrent `GET .../technique_lab/frame` during approval | Waited behind serial frame queue | **45.6 ms median** | < 0.05 s (target < 0.5 s) |

Byte identity: All 300 sample frames from the pooled check on both `projects/arnolfini` and `projects/technique_lab` are 100% byte-identical to the serial check (verified by SHA-1 hash comparison of every frame).

## 7. Needs Another Worker
- `config/server.json`:
  `d-engine` does not own `config/server.json`. Currently, `_default_check_threads()` defaults to 8 on Windows (`os.name == "nt"`) and 4 elsewhere if `check_threads` is omitted from `config/server.json`. If desired, the worker owning `config/server.json` (CORE / t0) may explicitly declare `"check_threads": 8` in the `windows` block and `"check_threads": 4` in the `default` block.

## 8. Objections
None.

## 9. Left Open
None.
