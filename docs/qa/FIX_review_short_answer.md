# Viewer review: short answers

The reviewer previously rejected an otherwise usable answer if even one requested shot was missing. The model is now called once more with only the missing shots, their original words and the same contact sheets, using the same model. A malformed or unreadable first answer is retried once for the original scope; a second malformed answer still fails the job. A valid second answer that remains short supplies empty findings for the remaining shots and records one `review_incomplete` warning with their count.

The existing two-round limit for storyboard repairs is unchanged. The saved warning is shown in Vietnamese and is tolerated at the automatic storyboard gate, so the run can continue; it does not claim that the missing shots were reviewed. Other review findings retain their existing gate behavior.

Tests use fake providers; no model calls were made. The focused regression suite covers the retry scope, merged findings, incomplete count, malformed replies, saved warning and automatic-run decision. Server and frontend suite results are recorded in `.scratch/agy_tasks/reviewfix/STATUS.md`.

## Verification

- Focused viewer-review suite: 32 passed on Windows. The first focused run inadvertently used pytest's default temporary directory outside the snapshot; subsequent suites used a temporary directory inside the snapshot.
- Draft: 636 passed, one failed. `test_workspace_holds_copies_only` requires its temporary workspace to be outside the repository, which conflicts with the instruction to write on the server only inside the snapshot. An earlier attempt also produced setup errors because the requested temporary parent did not exist; the suite was rerun with a valid parent.
- Editor: 534 passed; auto: 270 passed; CLI: 132 passed; engine excluding slow: 854 passed, 14 skipped, 168 deselected.
- JavaScript syntax checks passed; Node tests: 504 passed, one skipped. The skipped test requires a local `.venv`; its code-list addition was checked manually, and the new warning also has a direct Node test.
- All three generator checks passed after regenerating `docs/AGENT_API.md` using `bti.editor.hints` in the snapshot and copying it back with LF line endings.
- Coordinator clarification: pytest's default temporary directory is permitted. The draft suite was rerun with that default: 637 passed, including `test_workspace_holds_copies_only`, with one existing Starlette deprecation warning.
