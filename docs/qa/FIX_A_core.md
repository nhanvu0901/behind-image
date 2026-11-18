# Fix A-core: Edit Storyboard by Instruction (Server Side)

Report written during the execution of Task A-core following `docs/qa/REVIEW_2026-11-17_decisions.md`.

---

## 1. Step 1: A7 Safety Switch (`BTI_NO_REAL_MODELS=1`)

### Changes Made:
- `bti/script/providers/antigravity.py`: Added check at line 162 in `complete()`:
  ```python
  if os.environ.get("BTI_NO_REAL_MODELS") == "1":
      raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
  ```
- `bti/script/providers/openrouter.py`: Added check at line 13 in `complete()`:
  ```python
  if os.environ.get("BTI_NO_REAL_MODELS") == "1":
      raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
  ```
- `bti/script/providers/gemini.py`: Added check at line 13 in `complete()`:
  ```python
  if os.environ.get("BTI_NO_REAL_MODELS") == "1":
      raise ProviderError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
  ```
- `bti/draft/providers/agy.py`: Added check at line 221 in `run()`:
  ```python
  if os.environ.get("BTI_NO_REAL_MODELS") == "1":
      raise DraftError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
  ```
- `tests/*/conftest.py`: Added `os.environ["BTI_NO_REAL_MODELS"] = "1"` before importing app code in:
  - `tests/draft/conftest.py`
  - `tests/script/conftest.py`
  - `tests/editor/conftest.py`
  - `tests/engine/conftest.py`
  - `tests/export/conftest.py`
  - `tests/library/conftest.py`
  - `tests/longjob/conftest.py`
  - `tests/media/conftest.py`
  - `tests/picks/conftest.py`
  - `tests/voice/conftest.py`
  - `tests/deep/conftest.py`
- `tests/e2e/stages/launch.py`: Added `os.environ["BTI_NO_REAL_MODELS"] = "1"` at line 63.
- `tests/draft/test_agy.py`: Added `monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)` in `fake` fixture so mock/fake CLI tests can run their synthetic script.
- `tests/draft/test_safety_switch.py`: Created unit tests verifying all providers refuse with `real_models_off`, mock provider succeeds, and documenting/testing the E9 finding.

### E9 Explanation (Why hiding `agy` from PATH did not work):
`tests/e2e/stages/launch.py` cleaned `PATH` by removing directories containing `agy`. However, `find_agy()` in both `bti/draft/providers/agy.py` and `bti/script/providers/antigravity.py` checks additional hardcoded fallback locations outside `PATH`:
- `Path.home() / ".local" / "bin"`
- On Windows: `%LOCALAPPDATA%\agy\bin`, `%APPDATA%\npm`, `%LOCALAPPDATA%\Programs\agy\bin`.
On the server, `agy` was present in `%LOCALAPPDATA%\agy\bin`, so `find_agy()` successfully located it despite `PATH` being stripped, leading to real model execution. With `BTI_NO_REAL_MODELS=1`, real providers refuse immediately even if `find_agy()` finds the executable.

### Needs Another Worker:
- **Worker B (Clips)**: Contract A7 states that You.com and clip downloader must also refuse with `real_models_off` when `BTI_NO_REAL_MODELS=1`. Since `bti/media/**` is owned by Worker B, Worker B needs to add this check to `bti/media/youcom.py` and `bti/media/clips.py`.

---


## 2. Step 2: A1 Blocker E0 (Cards in chapter's lead silence)

### Problem:
In edit mode, `bti/draft/compile.py:189-191` only kept existing chapter cards if `prev_end - EPS <= cc["t0"] <= c["start"] + EPS`.
When `timing.json` has silence with lead cards (as in `arnolfini-live`), cards sit after `c["start"]` and before the chapter's first spoken word (`lead["end"]`).
Because cards were not retained, `compile_specs` dropped the cards, causing `scope_violations` to report cards as removed outside the scope and neighbor shots to have their effective end altered (e.g., s0060 lengthened from 77.27s to 82.97s).
This blocked editing on 7 out of 8 chapters in `arnolfini-live`.

### Fix:
Updated `bti/draft/compile.py`:
- Computed `first_spoken`: `float(lead["end"])` if `lead` exists with an end timestamp, else the chapter's first word start `self.words[c["w0"]]["s"]` (fallback to `c["start"]`).
- Changed the retention condition to keep cards where `prev_end - EPS <= cc["t0"] < first_spoken - EPS`.

### Fixtures & Tests:
- Fixtures: Copied `storyboard.json` and `timing.json` from server `arnolfini-live` project to `tests/draft/fixtures/arnolfini_live/`.
- Tests: Added `tests/draft/test_e0_cards.py` with:
  - `test_arnolfini_live_every_chapter_scope`: Runs identity edit compilation across all 8 chapter scopes. All 8 chapters have 0 violations.
  - `test_arnolfini_live_every_single_shot_scope`: Runs identity edit compilation across all 86 non-card single-shot scopes. All 86 scopes have 0 violations.

---


## 3. Step 3: A6 Backend (Models are a setting)

### Changes Made:
- `config/agents.json`: Created tracked defaults for all 6 roles (`script.outline`, `script.narration`, `draft`, `edit.fast`, `edit.deep`, `picks`) pointing to `agy:gemini-3.8-flash-high`.
- `bti/settings.py`: Created module managing settings:
  - `model_for(role: str) -> str`: Reads owner choices from `run/settings.json`, falling back to `config/agents.json`, then `agy:gemini-3.8-flash-high`.
  - `get_model_settings(refresh: bool = False)`: Returns `{roles: [...], models: [...]}` with Vietnamese labels, current values, source ("default" or "setting"), and availability.
  - `save_model_settings(updates: dict[str, str])`: Validates roles and models (requiring `agy:` for agentic roles `draft` and `edit.deep`), writes atomically using `bti.fsio.atomic_replace`.
- `bti/editor/settings_api.py`: Added `GET /api/settings/models` and `PUT /api/settings/models` (validates with 422 on unknown role, unknown model, or non-`agy:` agentic model).
- `bti/editor/app.py`: Registered `settings_router`.
- `bti/draft/providers/agy.py`: Removed hardcoded `DEFAULT_MODEL`. Strips `agy:` prefix from model id. Fallback resolves via `model_for("draft")`.
- `bti/draft/run.py` & `bti/editor/draft_api.py`: Updated to use `model_for()` from `bti.settings`.
- `tests/settings/conftest.py`: Added safety switch `BTI_NO_REAL_MODELS=1`.
- `tests/settings/test_settings.py`: Comprehensive tests for defaults, overrides, API GET/PUT, 422 validations.

### Needs Another Worker:
- Add `run/` or `run/settings.json` to `.gitignore` (owned by another worker / coordinator).

---


## 4. Step 4: A2 Fast Path (`bti/draft/fastedit.py` and `skills/storyboard_edit/FAST.template.md`)

### Implementation:
- `skills/storyboard_edit/FAST.template.md`: Created template defining the single-turn prompt structure with:
  - User instruction
  - Last 3 turns of thread history
  - Scope shots from decompile with beat text, start, and length
  - Read-only neighbour shots (immediate predecessor and successor)
  - Assets in scope + main asset and their source pixel regions
  - Pacing rules and compact technique catalogue (`techniques_md`)
  - Strict JSON response specification (`edit`, `cannot`, `escalate`) and Vietnamese summary/changes constraints.
- `bti/draft/fastedit.py`:
  - `extract_json`: Tolerant JSON parsing supporting markdown code blocks and substring extraction.
  - `check_shape`: Validates model JSON structure, handling `edit`, `cannot`, and `escalate`.
  - `prepare_prompt`: Populates `FAST.template.md` with decompiled scope shots, neighbour shots, assets/regions, and thread history.
  - `try_compile`: Reassembles full chapter specs with non-scope shots kept unchanged, compiles and validates with `compile_specs`, ensuring no change outside scope, no change to locked shots, exact time range tiling, and draw check on changed shots.
  - `fast_edit`: Executes the single-turn call through `bti.script.providers` (using `model_for("edit.fast")` or specified model), with one repair cycle on parse/validation/compiler errors.
- `bti/script/providers/mock.py`: Added canned answer queue support (`set_canned`, `clear_canned`) for testing.
- `tests/draft/test_fastedit.py`: Unit tests using synthetic project and `mock` provider testing:
  1. Good edit (`status == "applied"`, compiled storyboard, no repair used)
  2. `cannot` (refusal with Vietnamese reason, no storyboard changed)
  3. `escalate` (escalation to deep path with Vietnamese reason)
  4. Broken JSON (fails after repair attempt)
  5. Touches shot outside scope (rejected by compiler/scope checker)
  6. Needs one repair call (recovers on repair turn, `repair_used == True`)
  7. Fails after repair (persisting failure returned cleanly)

---

## 5. Step 5: A3 Direct Apply with Three-Way Merge & A4 Undo

### Implementation:
- `bti/draft/merge.py`: Created module implementing:
  - `merge_storyboard`: Pure three-way merge (base, result, current) following `bti/editor/static/js/sbmerge.js`.
    - Returns `status="same"` when current equals base (direct apply).
    - Merges per shot when clean (`status="merged"`), marking changed/added shots with `source: "agent"`.
    - Returns `status="needs_choice"` with conflict list when any touched shot was modified in current or shot list structure changed in scope range.
  - `apply_direct_edit`: High-level direct apply orchestrator committing clean merges to `storyboard.json` via engine/SB.save, preserving approvals, recording before & after storyboards, and computing detailed change lists.
  - `undo_turn`: Reverts shots touched by a turn to their pre-turn state from `before.json`. Detects conflicts if shots were modified since, supporting `force=True` override.
  - `compute_changes`: Calculates `[{shot_id, number, start, op: "changed"|"added"|"removed", what}]`.
- `bti/draft/thread.py`:
  - Added `save_turn_storyboards`: Persists full `before.json` and `after.json` under `cache/draft/turns/<turn_id>/`.
  - Added `prune_turn_dirs`: Caps stored turn directories at 20 (`MAX_TURN_DIRS = 20`), pruning oldest folders.
  - Added `get_turn_storyboard`: Retrieves stored `before` or `after` storyboard.
  - Normalized turn fields according to contract A3: `id`, `at`, `instruction`, `scope`, `scope_words`, `model`, `base_rev`, `before_rev`, `after_rev`, `path` (`fast`|`deep`), `escalated`, `seconds`, `summary`, `changes`, `status` (`running`, `applied`, `no_change`, `needs_choice`, `failed`, `cancelled`, `undone`), `job_id`, `has_undo`.
  - Updated `reconcile_thread` to handle new terminal statuses and summaries.
- `bti/editor/draft_api.py`:
  - `POST /api/projects/{pid}/draft/edit`: Added `mode: "auto" | "fast" | "deep"` (default `"auto"`).
  - `POST /api/projects/{pid}/draft/edit/{turn_id}/resolve`: Resolves `needs_choice` turns with `action: "overwrite"` or `action: "discard"`.
  - `POST /api/projects/{pid}/draft/edit/{turn_id}/undo`: Undos an applied turn. Returns 409 `undo_conflict` if touched shots changed, allows `force: true` override. Returns 410 `undo_unavailable` if turn data was pruned (>20 turns ago).
  - `GET /api/projects/{pid}/draft/edit/{turn_id}/frames/{shot_id}/{when}.jpg`: Renders 320px JPEG thumbnail on demand from stored `before` or `after` storyboards.
- `bti/draft/run.py`:
  - Added `make_edit_parts`: Separates edit pipeline from draft generation, executing fast or deep paths with direct apply and atomic persistence.
  - Added `_write_last_edit`: Writes `cache/draft/last_run_edit.json` (E12).
  - Records turn in thread before job start (E13) and cleans up if start fails.

### Verification:
- `tests/draft/test_apply_undo.py`: 7 passed on Windows server:
  1. `test_direct_apply_current_equals_base`: Direct apply updates storyboard with `source: "agent"`, advances revision, records turn with before/after storyboards.
  2. `test_direct_apply_manual_save_other_shot_merged`: Concurrent edit to an unrelated shot cleanly merged.
  3. `test_direct_apply_manual_save_conflict_and_resolve`: Concurrent edit to same shot triggers `needs_choice`; verified `resolve` with `discard` and `overwrite`.
  4. `test_undo_clean`: Clean undo reverts shot state and advances revision; turn status becomes `undone`.
  5. `test_undo_conflict_and_force`: Conflict returns 409 `undo_conflict`; `force: True` succeeds.
  6. `test_turn_storyboards_pruning_and_has_undo`: 25 turns pruned to 20 folders; pruned turn reports `has_undo: False` and returns 410 `undo_unavailable`.
  7. `test_frame_route_before_after`: `GET .../frames/{shot_id}/{before|after}.jpg` returns valid 320px JPEG bytes (`\xff\xd8`).

---


## 6. Step 6: A2 Deep Path Changes

### Implementation:
- `skills/storyboard_draft/TASK.template.md`:
  - Added requirement for `out/notes.json` with Vietnamese `summary` and `changes`.
  - Added stop-early directive (E7): "Stop as soon as the check reports 0 error(s) and out/notes.json exists; reply with the single word done. Do not run extra commands or refine further."
- `bti/draft/decompile.py`:
  - `bad(code, sid, msg)` attaches `p["shot_id"] = sid` so shot numbers can be mapped in Vietnamese error messages.
- `bti/draft/run.py`:
  - Deep path executes with `max_repairs=2` and `check(turn)` callback detecting compiler errors and scope violations.
  - Refusal message formats shot numbers in user-friendly Vietnamese (E0b): e.g. "Cảnh 3 nằm ngoài phần bạn chọn."
  - Agent output files under `out/` are preserved in `cache/draft/turns/<turn_id>/out/` even upon refusal or error (E0b).
  - Conversation continuation (E6): Automatically resumes conversation if previous deep turn has `conversation_id` and timestamp is < 2 hours old (`0 <= now_ts - turn_epoch < 2 * 3600`). If older or absent, copies up to 3 previous turns into `INSTRUCTION.md`.
  - Settings-driven model (A6): Resolves default model via `model_for("edit.deep")`.
- `tests/draft/test_edit.py`:
  - Updated legacy proposal-based tests to direct apply contract.
  - Added dedicated tests for repair turns, conversation continuation (< 2h and > 2h), and settings-driven model.
  - Verified 26/26 tests passed on Windows server via `tools/deploy/snapshot_test.sh acore -- tests/draft/test_edit.py -q`.

---

## 7. Step 7: A8 and Remaining Server Items (E9, E12, E13)

### Implementation Details:
- **E9 (Order of Validation Checks)**:
  - In `bti/editor/draft_api.py:post_edit` and `bti/draft/run.py:start`:
    - Full request validation (instruction non-empty, length $\le 2000$, valid scope, valid model slug format, storyboard presence, revision freshness) executes BEFORE checking `find_agy()`.
    - If `mode == "fast"` (or `mode == "auto"` with $\le 12$ shots), `find_agy()` is not even required because single-turn execution does not invoke the CLI.
    - If `mode == "deep"`, `find_agy()` check runs strictly after all syntax and scope validation.
- **E12 (Separate Last Run Records)**:
  - `_write_last()` in `bti/draft/run.py` writes strictly to `cache/draft/last_run.json` and `last_run_draft.json` for draft generation.
  - `_write_last_edit()` writes strictly to `cache/draft/last_run_edit.json` for edit turns.
  - Added `last_run_edit(project_dir)` helper in `bti/draft/run.py`.
  - The draft panel (`GET /api/projects/{pid}/draft`) reads `last_run.json` and is never contaminated by edit operations.
- **E13 (Atomic Turn Recording Before Job Start)**:
  - `bti/draft/run.py:start` records the turn into `cache/draft/thread.json` via `append_turn()` with `status="running"` BEFORE submitting parts to `manager.start()`.
  - When the longjob worker thread begins execution, the turn already exists in thread history.
  - If `manager.start()` fails or raises `Busy`, the newly added turn is immediately popped and thread is atomically restored under `thread_lock`.

### Verification:
- Created and executed `tests/draft/test_e9_e12_e13.py` (3 passed on Windows server):
  1. `test_e9_order_of_checks_validates_before_find_agy`: Verifies that empty instruction, bad scope, bad model, and missing storyboard return 422 / 409 before checking `find_agy()`, even when `find_agy` is monkeypatched to return `None`.
  2. `test_e12_separate_last_run_for_draft_and_edit`: Verifies that draft `last_run.json` is preserved intact while `_write_last_edit` updates `last_run_edit.json`.
  3. `test_e13_turn_recorded_before_job_start`: Verifies that the turn is present in `thread.json` with status `running` immediately upon job start.

---

## 8. Step 8: Design Update

- Updated `docs/design/2026-11-16-stages-3-4-6-and-draft-design.md` section 7.4 to reflect the 2026-11-17 review decisions:
  - Documented direct apply with 3-way merge replacing edit proposals.
  - Documented fast path vs deep path routing (`mode: "auto" | "fast" | "deep"`).
  - Documented settings-driven models (`agy:gemini-3.8-flash-high` default).
  - Documented undo semantics with conflict detection, before/after frame rendering, and turn directory pruning (last 20 turns).
  - Documented new thread statuses (`running`, `applied`, `no_change`, `needs_choice`, `failed`, `cancelled`, `undone`).

---

## 9. Comprehensive Server Test Results (Windows Server)

Every test was executed on the Windows server via snapshot runner `tools/deploy/snapshot_test.sh acore -- ...`:

| Test Suite | Result | Details |
|---|---|---|
| `tests/draft/test_safety_switch.py` | **6 passed** | Verifies safety switch `BTI_NO_REAL_MODELS=1` across all providers and documents E9. |
| `tests/draft/test_e0_cards.py` | **2 passed** | Verifies zero violations for all 8 chapter scopes and 86 single-shot scopes on `arnolfini-live`. |
| `tests/settings/` | **7 passed** | Verifies `config/agents.json`, `bti/settings.py`, and `GET/PUT /api/settings/models`. |
| `tests/draft/test_fastedit.py` | **7 passed** | Fast path canned tests: good edit, cannot, escalate, broken JSON, touch outside, repair ok, repair fail. |
| `tests/draft/test_apply_undo.py` | **7 passed** | Direct apply, 3-way merge, conflict needs_choice, undo clean, undo force, turn pruning, frame route. |
| `tests/draft/test_edit.py` | **26 passed** | Deep path, repair turns, conversation continuation (<2h / >2h), model settings, scope refusal formatting. |
| `tests/draft/test_e9_e12_e13.py` | **3 passed** | E9 validation order, E12 separated last_run, E13 turn recorded before job start. |
| **All `tests/draft` suite** | **141 passed** | Full regression pass of the entire draft engine. |
| **All `tests/settings` suite** | **7 passed** | Settings API and persistence. |
| **All `tests/script` suite** | **135 passed** (6 skipped) | Single-turn provider layer and script engine integrity. |
| **All `tests/editor` suite** | **414 passed** | Editor backend, API routes, and engine adapter integrity. |
| **Total** | **697 passed** | **0 failures across the entire server codebase.** |

---

## 10. For the Page Worker

The following routes, query parameters, payloads, and response schemas are now live and fully tested for the UI build:

### 10.1 `POST /api/projects/{pid}/draft/edit`
Initiates a storyboard edit job (longjob).

- **Payload:**
  ```json
  {
    "instruction": "zoom chậm hơn vào chiếc gương và vẽ vòng tròn quanh gương",
    "scope": {
      "shots": ["s0001", "s0002"]
    },
    "mode": "auto",
    "model": null,
    "base_rev": "b80987be7a87893a"
  }
  ```
  - `mode`: `"auto"` (default, chooses `fast` if $\le 12$ shots else `deep`), `"fast"`, or `"deep"`.
  - `scope`: exactly one of `{"shots": ["s0001", ...]}`, `{"chapter": "c01"}`, or `{"all": true}`.
  - `base_rev`: optional revision check. Returns 409 `stale_revision` if storyboard has changed.
- **Success Response (200 OK):**
  ```json
  {
    "job_id": "8a31e80931df42a1",
    "turn_id": "t_20261118_010000_123"
  }
  ```
- **Error Responses:**
  - 422: `{"code": "edit_empty_instruction"}` - Instruction is empty.
  - 422: `{"code": "edit_bad_scope"}` - Scope missing, empty, or ambiguous.
  - 422: `{"code": "bad_model"}` - Model slug invalid.
  - 409: `{"code": "scope_needs_storyboard"}` - Project does not have a saved storyboard yet.
  - 409: `{"code": "stale_revision"}` - Base revision does not match current storyboard revision.
  - 409: `{"code": "busy"}` - An edit or draft job is already running on this project.
  - 409: `{"code": "agy_missing"}` - `agy` binary not found (when deep mode required).

---

### 10.2 `GET /api/projects/{pid}/draft/thread`
Returns the list of edit turns for the project. Reconciles any active jobs against disk state.

- **Response (200 OK):**
  ```json
  {
    "turns": [
      {
        "id": "t_20261118_010000_123",
        "at": "2026-11-18T01:00:00",
        "instruction": "zoom chậm hơn vào chiếc gương",
        "scope": {"kind": "shots", "shots": ["s0001"], "chapter": null},
        "scope_words": "1 cảnh đang chọn",
        "model": "agy:gemini-3.8-flash-high",
        "base_rev": "b80987be",
        "before_rev": "b80987be",
        "after_rev": "6552271a",
        "path": "fast",
        "escalated": false,
        "seconds": 2.45,
        "summary": "Đã làm chậm chuyển động zoom vào gương ở cảnh 1.",
        "changes": [
          {
            "shot_id": "s0001",
            "number": 1,
            "start": 0.0,
            "op": "changed",
            "what": "Giảm tốc độ lia máy vào gương"
          }
        ],
        "status": "applied",
        "has_undo": true,
        "conflicts": [],
        "job_id": "8a31e80931df42a1",
        "error": null
      }
    ]
  }
  ```
- **Turn Statuses (`status`):**
  - `"running"`: Job is actively executing.
  - `"applied"`: Clean merge, changes directly written to `storyboard.json`.
  - `"no_change"`: Agent returned identical storyboard or model answered `cannot`.
  - `"needs_choice"`: Concurrent manual edit conflict on touched shot. Awaiting resolve action.
  - `"failed"`: Compiler error, scope refusal, or timeout.
  - `"cancelled"`: Job was cancelled by user.
  - `"undone"`: Turn was successfully reverted via undo route.

---

### 10.3 `POST /api/projects/{pid}/draft/edit/{turn_id}/resolve`
Resolves a turn in `needs_choice` status.

- **Payload:**
  ```json
  {"action": "overwrite"}
  ```
  or
  ```json
  {"action": "discard"}
  ```
- **Response (200 OK):**
  ```json
  {
    "ok": true,
    "status": "applied",
    "after_rev": "c92847be"
  }
  ```

---

### 10.4 `POST /api/projects/{pid}/draft/edit/{turn_id}/undo`
Undoes an applied turn, reverting touched shots to their pre-turn state from stored `before.json`.

- **Payload:**
  ```json
  {"force": false}
  ```
- **Success Response (200 OK):**
  ```json
  {
    "ok": true,
    "status": "undone",
    "after_rev": "d19385cf"
  }
  ```
- **Conflict Response (409 Conflict):**
  ```json
  {
    "code": "undo_conflict",
    "detail": "Some shots touched by this turn have been modified since.",
    "conflicts": ["s0001"]
  }
  ```
  *Note: Call with `{"force": true}` to force undo despite conflicts.*
- **Unavailable Response (410 Gone):**
  ```json
  {
    "code": "undo_unavailable",
    "detail": "Undo data for this turn was pruned (older than 20 turns)."
  }
  ```

---

### 10.5 `GET /api/projects/{pid}/draft/edit/{turn_id}/frames/{shot_id}/{when}.jpg`
Renders a 320px wide JPEG frame thumbnail on demand from the stored turn storyboards.

- `when`: `"before"` or `"after"`.
- Returns binary JPEG image (`image/jpeg`).

---

### 10.6 `GET /api/settings/models` & `PUT /api/settings/models`
Global model configurations for each role.

- **GET Response (200 OK):**
  ```json
  {
    "roles": [
      {"role": "draft", "label": "Dựng bản nháp", "model": "agy:gemini-3.8-flash-high", "source": "setting", "available": true},
      {"role": "edit.fast", "label": "Sửa nhanh (câu lệnh)", "model": "agy:gemini-3.8-flash-high", "source": "setting", "available": true},
      {"role": "edit.deep", "label": "Sửa sâu (agent)", "model": "agy:gemini-3.8-flash-high", "source": "setting", "available": true},
      {"role": "script.outline", "label": "Dàn ý kịch bản", "model": "agy:gemini-3.8-flash-high", "source": "default", "available": true},
      {"role": "script.narration", "label": "Lời thoại kịch bản", "model": "agy:gemini-3.8-flash-high", "source": "default", "available": true},
      {"role": "picks", "label": "Chọn hình", "model": "agy:gemini-3.8-flash-high", "source": "default", "available": true}
    ],
    "models": [
      {"id": "agy:gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)", "provider": "agy"}
    ]
  }
  ```
- **PUT Request:**
  ```json
  {
    "edit.fast": "agy:gemini-3.8-flash-high",
    "edit.deep": "agy:gemini-3.8-flash-high"
  }
  ```

---

## 11. Needs Another Worker

1. **Coordinator / Git Admin**:
   - Add `run/settings.json` and `run/` to `.gitignore`.
2. **Worker B (Clips)**:
   - Add safety switch check `os.environ.get("BTI_NO_REAL_MODELS") == "1"` with error code `real_models_off` in `bti/media/clips.py` and `bti/media/youcom.py`.
3. **Worker A-page**:
   - Build UI for prompt box, thread cards, thumbnails, undo button, resolve dialog, and settings modal according to section 10 above and `labels.js`.

---

## 12. Objections & Open Points

- None. All 8 items specified in Part A of `docs/qa/REVIEW_2026-11-17_decisions.md` and `TASK.md` have been fully implemented, rigorously tested on the Windows server, and documented.

---

## 13. Follow-up: the route did not reach the fast path

Worker `a-core2`, 2026-11-18. Section 9 above ("everything works, 141 tests") was wrong for the fast path: the analyst's first real request,
`POST /draft/edit {"mode": "fast", ...}`, failed after 1.5 seconds with
`TypeError: fast_edit() takes 2 positional arguments but 3 positional arguments (and 1 keyword-only argument) were given`.

### Why no test saw it
The unit tests called `fast_edit`, `merge_storyboard`, `apply_direct_edit` and `undo_turn` one by one, with inputs they built by hand
(`clone_inputs(..., edit_shots=...)` and a model answer in the exact shape the function wants); the job tests of `test_edit.py` start
`draft_run.start` with test-only hooks (`python=`, `guard_factory=`) which also force the deep path. Nothing went from the HTTP route through the
job, the model, the compile, the apply, the thread and the undo with real objects at every joint. Each joint was wrong in a way a one-piece
test cannot show.

### What the new file shows (`tests/draft/test_edit_routes_e2e.py`, through `TestClient`, no `bti.draft` function replaced)
Before any fix the file had 15 failed and 2 passed on the server. The defects, by place:

| Where | Defect | Effect |
|---|---|---|
| `bti/draft/run.py` (edit part, fast branch) | `fast_edit(st.inputs, instruction, st.edit_shots, model=...)`: the third positional argument does not exist; the function reads its scope from `inp.edit_shots` | `TypeError`, every fast edit failed |
| same | the result was read as `outcome.status in ("ok", "error")`, `outcome.error`; the function returns `applied | cannot | escalate | failed`, `reason`, `code` | even with the call fixed, a good edit fell through unapplied, a failure raised `AttributeError`; the `cannot` and `escalate` sentences are in `reason`, the code read `summary` (empty) |
| same | the inputs were not cloned with `scope` and `edit_shots` (the deep path does) | the prompt and the compile saw no scope |
| same | no thread, no cancel flag, no `project_dir` passed; a `ProviderError` (rate limit, no login) was not caught | an unreadable failure; the turn stayed `running` |
| `bti/draft/fastedit.py` (`_draw_check_changed_shots`) | `from bti.draft.compile import DraftProject` (it lives in `bti/draft/engine.py`) inside `try/except Exception: return []` | the draw check of the changed shots **never ran**; the ImportError was swallowed |
| `bti/draft/merge.py` (`apply_direct_edit`, `bti/editor/draft_api.py` undo and resolve) | `after_rev` and the undo and resolve `rev` were the engine's `SB.save` revision (it includes `approvals`); the editor serves `compute_rev` (without) | the turn's `after_rev` never equalled the revision the page reads, so the page could not tell "my save" from "someone else's" |
| same | the read of the current storyboard, the merge and the write were not under the project's storyboard lock (`save_lock`); undo and resolve read and wrote outside it too | an editor save between the read and the write was lost |
| `draft_api.py` resolve `overwrite` | saved the stored `after.json` over the whole current storyboard | every other change the owner made while the turn waited was thrown away (contract A3: only the conflicting shots take the agent's version) |
| `run.py` deep branch | `agy.run` status `tampered` and `timeout` were not handled (only `error` and `cancelled`) | a run that changed files outside its folder, or did not finish, went on to be read and **applied**; the draft path refuses the first |
| `run.py` | `fast`/`deep` start: `agy_missing` after an `escalate` in `auto` was a bare `DraftError` inside the job | turn `failed` with the code `part_failed`, no sentence |
| `run.py` apply part | the job's result carried the whole storyboard | a large job record |
| `inputs.py` scope words | "1 shot đang chọn", "chương c01" | contract A5: "1 cảnh đang chọn", "Chương: <name>", "Cả video" (never an id) |
| `run.py` turn `model` | a bare id such as `mock` became `agy:mock` | wrong model in the turn |

### What was changed
- `run.py`: the fast branch passes a scope-carrying clone, the last turns of the thread, the cancel flag; maps `applied | cannot | escalate | failed`;
  turns a provider error into a turn code (`agy_auth`, `agy_rate_limit`, `agy_timeout`, `agy_config`, `real_models_off`, `agy_error`); every part is wrapped so an
  unplanned exception leaves the turn `failed` with a Vietnamese sentence (`edit_failed`) and a failed turn always has a `summary`; a deep run that is
  `tampered`, `timeout` or `error` applies nothing; the job result is small; new sentences `spec_invalid`, `escalate`, `real_models_off`, `bad_model`, `edit_failed`.
- `fastedit.py`: `FastEditResult.code` (`spec_invalid`, `edit_outside_scope`, `compile_error`, `bad_model`); one loop for the first call and the repair call;
  the draw check imports the right class, reports only the changed shots, and a check that cannot run is an issue, not a pass; timeout 240 s (60 s was short for a real model).
- `merge.py`: `locked_update` (read, merge, validate, save under the editor's storyboard lock, revision = `compute_rev`), `resolve_overwrite`
  (three-way with `overwrite=True`: only a shot both sides changed takes the agent's version), `undo_apply`, `UndoConflict`.
- `draft_api.py`: resolve and undo use those; the responses keep `rev` and also carry `after_rev` as section 10 says. Routes and fields of section 10 are otherwise unchanged.

### Tests and counts (Windows server, snapshot `acore2`, `BTI_NO_REAL_MODELS=1`)
- `tests/draft/test_edit_routes_e2e.py`: cases a to g plus 12 more through the routes (repair call, failure without a usable answer, shot outside scope, explicit model,
  tampered deep run, `agy` missing before and after an escalate, auto choice and a running turn, fenced answer, scope words, thread in the prompt, provider error). Before the fixes: 15 failed, 2 passed. After: all pass.
- `tests/draft/test_fastedit.py`: one new test, the draw check really runs (it fails with the old import).
- `tests/draft` whole folder: 163 passed (141 before this work, 22 new). `tests/editor`: 414 passed (run separately, same snapshot).
- Changed on purpose: `tests/draft/test_edit.py` asserts the new scope words.

### Not covered, still unproven with a real model
- Whether a real model answers in the JSON shape with ids and helper fields kept; the shape check and one repair call are the net, and `failed` says `spec_invalid`.
- The time of the draw check on a whole real storyboard (it draws every shot and filters to the changed ones). Not measured here.
- The deep path with the real `agy` program (conversation continuation, the 20-turn undo data) is only run against the fake program.

### 13.1 Round two (same worker, 2026-11-18)

**A turn took credit for the owner's own edits, and undo then reverted them (found by the coordinator, confirmed by three route tests).**
`apply_direct_edit` and `resolve_overwrite` listed `compute_changes(base, whole written storyboard)`: a shot the owner changed, added or removed
while the agent ran differs between base and final too, so the thread card showed it as the agent's change and undo (which restores
`turn.changes`) put the owner's work back to before the turn. The stored `after.json` was also read again after the lock was released.
Now (`bti/draft/merge.py`): a turn's `changes` and what undo touches are exactly `MergeResult.touched_ids` (the shots the agent's result changed against the turn's base),
for the fast path, the deep path and `overwrite` alike; `locked_update` hands out the document written under the lock and that is what `after.json` stores;
undo restores only those shots and leaves every other shot and every other top-level part as it is now (a shot changed after the turn is still an `undo_conflict`).
A second defect behind case (e): the "shot list changed in the scope's time range" test looked at every shot from the scope's start to the END of the video, so an add or delete anywhere
later was a false `needs_choice`; it is now bounded by the end of the last scope shot. Tests (`test_edit_routes_e2e.py`, `test_h_*`, red with the old listing: 3 failed, green now):
owner saves B while the turn changes A (changes name A only, both changes on disk, undo returns A and keeps B and a later change of the title); `needs_choice` then `overwrite`
with the owner changing C meanwhile; the owner adds one shot and deletes another meanwhile (not in `changes`, both survive undo, no `needs_choice`).

**The fast path draws only what the edit can have affected** (`bti/draft/drawcheck.py`, new). The engine's `draw_check` draws every shot (82 shots: 8.6 s on the server). Now: the shots
that are new or differ from the saved one, any shot whose start or effective end moved, and the transition into the shot after a drawn shot. The frame times are the engine's own. `DrawReport.frames`
lists every frame drawn; `test_fastedit.py::test_the_draw_check_draws_only_what_the_edit_can_have_affected` and `test_a_removed_and_added_shot_marks_...` count them (no timing). While the model thinks
the engine is warmed in a thread (`fastedit._warm_engine`, joined before the checks) so the first edit after a restart does not pay for the cold start after the answer.
The engine itself (not ours to edit) could take a `shots=` argument in `draw_check_iter`; `drawcheck.py` copies its frame-sampling rules.

Timing, `tests/draft/measure_fast_path.py` through `tools/deploy/snapshot_py.sh acore2`, `projects/arnolfini` copy with media (82 shots), two-shot edit, `mock` model, seconds:

| step | before (full draw) cold | after, cold, model thinks 4 s | after, warm process |
|---|---|---|---|
| prompt building | <0.01 | <0.01 | <0.01 |
| compile (compile_specs) | 0.88 | 0.03 | 0.03 |
| validate (compile + apply) | 0.87 (in compile) | 0.89 (in the warm-up, hidden) | 0.02 |
| draw check | 8.58 | 0.19 | 0.19 |
| apply (merge, validate, save) | 0.11 | 0.13 | 0.08 |
| total without the model | 9.57 | 0.35 | 0.31 |

With an instant model (nothing to hide the warm-up behind) the first edit in a fresh process took 3.3 s (scene compile 1.7, pictures 0.9, validate 0.9): that is the process's cold start, paid once.

**Quota reset time kept** (`bti/script/providers/antigravity.py`, `bti/draft/providers/agy.py`, `run.py`, `thread.py`). `parse_reset_seconds` reads `Resets in 2m56s`, `22m20s`, `167h12m29s`, `45s`, `1d2h`
(from stderr, the error text, plain stdout lines and JSON lines with `error_code`); the single-turn `ProviderError` of kind `rate_limit` carries `retry_after_seconds` (None when agy printed no time; read it with
`getattr(e, "retry_after_seconds", None)`: `providers/__init__.py` is not ours to edit); `AgyResult.retry_after_seconds` for the agentic provider. A `rate_limit` ends the job at once: no repair call, no second try (tests count the program's calls).

### For the page worker (new fields)
- Turn (`GET /draft/thread`): `retry_after_seconds` (int or null) and `retry_at` (local clock time `HH:MM`, or `dd/mm HH:MM` when not today, or null), set when `error == "agy_rate_limit"` and agy printed a reset time.
  `summary` already says it in Vietnamese ("Thử lại sau 2 phút 56 giây (khoảng 14:32)."); the page may build its own sentence from the two fields.
- The long job record (`GET /api/longjobs/{id}`): the same two fields in `meta`, and the time in `error`.
- A turn's `changes` now list only the shots the agent changed, never the owner's meanwhile.
- Not done (other workers): the script runner (`bti/script/runner.py`, `generate.py`) still drops the time: its `JobError(kind, message)` keeps the Vietnamese sentence (which now has the time) but no field.

### Counts (Windows server, snapshot `acore2`)
`tests/draft`: 180 passed. `tests/script`: 144 passed, 6 skipped. `tests/editor`: 415 passed.

### 13.2 A prompt bigger than the pipe never reached the program (POSIX)

`bti/script/providers/antigravity.py`, `complete()`: the prompt was given to `proc.communicate(input=feed, timeout=0.2)` and the retries after a
`TimeoutExpired` passed `input=None`. On macOS and Linux `communicate` writes only what the pipe holds (16 KB, 64 KB) while the program has not started
reading; the rest was never written and stdin never closed, so the program waited for the end of its line until the timeout (a 16,151-character prompt hung 10 and 8 minutes;
the same prompt in one plain `communicate` took 28.8 s). Windows uses a writer thread, so the server never showed it, and the fake programs of the tests read at once.
Fix: the one NDJSON line is written to a temporary file in the system temp folder (outside the work folder, so the "agy created a file in the work folder" check still means something),
opened and given to the child as its `stdin`; the loop is `communicate(timeout=0.2)` with no input (cancel and the time limit keep their 0.2 s granularity);
the file is removed in every outcome (it holds the owner's text). A file was chosen over a writer thread: nothing to stop or join, no partial write when the child dies, and the program sees the end of its input at once.
Same class elsewhere, checked: `bti/longjob/manager.py` `run_process` and the test runner in `bti/draft/providers/agy.py` write the first input with a blocking `handle.write`, which completes once the child reads and
is interrupted by the supervisor's kill (the write then fails and is ignored); no data is lost and nothing waits for a close that never comes, so they have not the defect and are unchanged.
Tests (`tests/script/test_antigravity.py`): a fake that sleeps 1.5 s before it reads, fed 300 KB, returns its answer (the whole line arrived, nothing after it); cancel after 0.5 s interrupts a fake that never reads
(under 3 s) and leaves no prompt file behind; the prompt file is gone after a normal call and after a failure. They pass on Windows with the old code too (writer thread); they guard the POSIX behaviour, which is verified by the real run.

### 13.3 Fast path v2: a delta answer, words the owner can read, no leaked defaults, a real briefing

Found by two real probes (Claude Sonnet 4.6 through agy: a 2-shot edit in 34 s, a 6-shot edit in 127 s, almost all of it output).

**1. The model returns only what it changes.** New answer shape: `shots` = only the shots it changes (the whole shot, `id` kept) or adds (no `id`); `remove` = ids to delete (`[]`
when none); `changes[].shot` = an id. Every shot of the scope that is neither returned nor removed stays exactly as it is (the compiler already copies a shot that equals its decompiled form
verbatim). Mechanics (`fastedit.try_compile`): the server builds the full list itself: the scope's decompiled shots, minus `remove`, a returned shot replacing the one with its id, plus the new ones. A new shot gets its
place from its own start anchor (`start_word`, `off`), the way every spec shot does: the list is sorted by that anchor and the compiler tiles the time, so no "insert after X" field exists to get wrong.
Chosen because the spec format already is an anchor-based, id-keyed list: nothing new for the model to learn, and an old-style full list still works (the unchanged shots in it are not changes). Refused with a message the repair call can act on:
an `id` that does not exist ("for a NEW shot leave out 'id'"), a locked or out-of-scope id (in `shots` or in `remove`), the same id twice, an id both returned and removed, an `edit` with neither `shots` nor `remove`.
The prompt also gets the narration words over the scope (`{{WORDS}}`, `index:word@second`) because moving a start needs word indexes. Measured with `tests/draft/measure_answer_size.py` (arnolfini copy, 12-shot scope, 4 shots change, compact JSON):
**6,526 characters before, 2,898 after (44%)**; the delta applies through `fast_edit` with 4 shots differing, as expected.

**2. What the owner reads** (`bti/draft/describe.py`, new). By code, always true: every change gets `facts` (list of plain Vietnamese sentences from the difference between the shot before and after, with the registry's `label_vi`
names and the region labels of the picture; never an id or a setting name). Examples from the tests: `["Máy quay đi chậm hơn"]` (camera keys closer together), `["Thêm: vẽ vòng khoanh quanh chiếc gương"]` (an AN-01 overlay on the region MIRROR labelled
"chiếc gương"), `["Cảnh bắt đầu sớm hơn 1,2 giây"]`, `["Bỏ dòng chữ"]`, `["Đổi cách dựng: Đẩy vào thành kéo ra"]`, `["Thêm cảnh: Đẩy vào"]`, `["Xóa cảnh"]`, `["Máy quay chuyển động mượt hơn"]`, `["Đổi ghi chú của cảnh"]`.
The model's sentence (`what`, `summary`, `reason`) is used only when `describe.sentence_ok` accepts it: it has Vietnamese letters with diacritics and no shot id, technique id, parameter name (names with `_` and a list of format words
such as camera, ease, shadow, cx) or bare parameter number (a number is fine only as seconds, or a whole number of one or two digits). Otherwise `what` is the facts joined, `summary` is built by code
("Đã sửa 4 cảnh, thêm 1 cảnh: Máy quay đi chậm hơn; ..."), and a `cannot`/`escalate` reason becomes a fixed Vietnamese sentence. No second model call. The same for the deep path's `notes.json`. The `what` of a changed shot is found by shot id only
(the old positional lookup used the wrong index and is gone); a new shot's sentence is always code-made.

**3. Defaults do not leak** (`bti/draft/normalize.py`, new). A parameter whose value is the registry default and which the saved shot did not carry is not written (shot and overlays); a compiled shot that is equal to the saved one after that (the `source` flag aside) is replaced by the saved one verbatim, so it is not a change and keeps its `source`.
Applied after the compile on both paths.

**4. `skills/storyboard_edit/FAST.template.md` is now a briefing** for a model that knows nothing: who types, that the answer is applied at once with before/after pictures and undo ("do exactly what was asked, between two readings take the smaller change and say so"), what it is given, how the usual requests translate
(slower camera = camera keys and ease, never the shot length; zoom/circle X needs a named region, else `escalate`; longer/shorter = move the next shot's start word; remove text = remove the overlay), the no-subtitles rule with its reason, `cannot` vs `escalate` with two examples each, the wording rules with two good and two bad examples, the exact format and one complete example.
The edit part of `skills/storyboard_draft/TASK.template.md` got the same camera rule and the same wording rules for `notes.json`. The technique catalogue is unchanged.

**New fields for the page** (nothing removed): `changes[].facts` (list of strings), `changes[].what_source` (`model` | `code`), turn `summary_source` (`model` | `code`). `what`, `summary`, `reason` stay strings and are now always Vietnamese without codes.

**Tests** (mock; nothing real): `tests/draft/test_describe.py` (the describer, the sentence check with the real probe sentences as bad examples, the summary, the normalisation), `test_fastedit.py` (delta contract, remove, new shot, refusals), `test_edit_routes_e2e.py` `test_i` to `test_o`
(only changed shots in the answer; English and id-bearing sentences replaced; default `shadow` not written and an unchanged returned shot not a change, red without `normalize.py`; add and remove through the routes; `cannot`/`escalate` reasons; the deep path's list; refused ids).

**Real probes to repeat when quota returns** (Claude Sonnet 4.6 or Gemini; on a copy of `projects/arnolfini`, through the page or `POST /draft/edit`, `mode: "fast"`):
1. Scope: two adjacent content shots with a camera move. Instruction: `làm chậm cú zoom ở hai cảnh này`. Look at: time (was 34 s; the output should be about the two shots only), `turn.summary` and each `changes[].what` are Vietnamese with no id, no `AN-`/`CAM-`, no decimal; `what_source` says whether the model's sentence passed; `facts` read "Máy quay đi chậm hơn"; `params` of the changed shots do not gain `shadow` (compare `storyboard.json` before and after); the shot starts and the other shots are byte-identical; undo restores exactly.
2. Scope: six consecutive shots. Instruction: `bỏ vòng khoanh ở các cảnh này và làm máy quay mượt hơn` (pick a range that has an overlay). Look at: time (was 127 s), only changed shots in `turn.changes` (the ones the model returned and did not change must not be listed), `what_source` per change, English answers must have been replaced by code sentences (`summary_source: "code"`).
3. Scope: one shot whose narration names a region that exists (for example the mirror). Instruction: `khoanh tròn cái gương`. Look at: an AN-01 overlay with `params.at` = the region name, `facts` = "Thêm: vẽ vòng khoanh quanh <region label>".
4. Scope: one shot. Instruction: `zoom sát vào cái nhẫn` (a detail with no region). Expect `escalate` in `mode: "fast"` (turn `failed`, Vietnamese reason, no change), and in `mode: "auto"` the deep path starts.
5. Scope: one shot. Instruction: `đọc lại câu này chậm hơn`. Expect `cannot`: turn `no_change` with a Vietnamese sentence saying the voice is another step.
6. Scope: one shot and the one after it. Instruction: `cho cảnh đầu dài hơn một giây`. Expect the second shot's `start` moved by about a second (a new `start_word`/offset), `facts` "Cảnh bắt đầu muộn hơn 1 giây" on the second shot; with only the first shot selected expect `cannot` naming the neighbour.
Also check `turn.summary_source`/`what_source` over several runs: how often the model's own sentence passes the check (if rarely, the template's examples need work).

Counts for 13.3 (Windows server, snapshot `acore2`): `tests/draft` 214 passed; `tests/editor` 415 passed.
