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
