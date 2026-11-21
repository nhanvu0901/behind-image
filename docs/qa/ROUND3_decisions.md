# Round 3: decisions for the fixes

Written by the analyst on 2026-11-16. Testers are still working, so this file grows as findings arrive. It is the contract for the round 3 fix agents; the rules in `ROUND2_decisions.md` still hold. As before: **fix the class, not the reported input.**

## Who owns what

| Agent | Owns (may edit) |
|---|---|
| Backend fixer | `bti/editor/*.py`, `bti/engine/**`, `bti/script/**`, `bti/library/**`, `bti/media/**`, `style/gae/**`, and the tests under `tests/editor`, `tests/engine`, `tests/script`, `tests/library`, `tests/media` |
| UI fixer | `bti/editor/static/**`, `tests/editor_frontend/**`, `tests/e2e/**`, `docs/APP_GUIDE.md` |

## Interface fixed now, so both agents can work at once

Narration operations, on the existing route `POST /api/projects/{pid}/narration/ops`, same request and answer shape as the other operations:

- `{"op": "drop_chapter", "chapter": "c06"}` removes that chapter and its beats from the narration. For locked beats it follows the rule the existing `drop` operation uses for one locked beat. An unknown chapter id is 422.
- `{"op": "add_chapter", "chapter": "c04"}` adds a chapter that is in the current outline and missing from the narration, at the outline's position, with the outline's title and no beats. Any other id is 422.

Validation of the narration gains one issue: `empty_chapter` (`args.chapter`), for an outline chapter whose narration chapter has no beat with text. It is an error for approval and is listed with the chapter differences; saving stays allowed.

Storyboard issues, additions to `args` (the page may rely on them):

- Issues about an asset or its file carry `args.asset` (the asset key).
- Issues about one key of a camera or of a list carry `args.index` (0-based) so the sentence can name the key.

## Decisions

**R3B-001. The draw check never holds the process-wide engine lock for a whole pass.** One sample per hold. Done by the backend fixer on 2026-11-16. Still open from its report: compiling the scene (about 0.9 s) is one step under the lock; acceptable.

**R3U-002. The owner can always resolve a chapter difference from the page.**
- Backend: the two operations and the `empty_chapter` issue above.
- Page: in the refusal dialog and in the chapter header, each difference has its own action. A narration chapter the outline does not have: "Xóa chương này khỏi lời dẫn" (asks once; it can be undone the same way dropping a beat can). An outline chapter with no narration: "Viết chương này" (the existing job, for that chapter only, with the model the owner has chosen) and "Thêm chương trống". An empty chapter: the same two choices.
- "Xóa chương" is offered only on chapters the outline does not have, so a chapter cannot be removed by accident while the outline still asks for it.
- Acceptance: the tester's steps end in an approved narration without rewriting the whole script.

**R3U-001. A dropdown always shows the real value.** When the stored value is not in the list, the dropdown shows it as its own entry marked "(không có trong danh sách)"; an empty value shows "— chưa chọn —". Nothing is written until the owner changes the field. One shared helper for every dropdown built from a list (intent, technique, ease, enum params, source, model), and a unit test.

**R3U-003. Clicking an issue never lands on an unrelated shot.** An issue with a shot goes to that shot and field. An issue about an asset (`args.asset`) goes to the first shot that uses the asset and says how many shots use it; if none does, it opens the assets tab on that asset. An issue with no place stays where the owner is and only shows its detail. The fallback to the first shot is removed.

**R3U-004. A frame that cannot be drawn leaves no stale picture.** The preview clears to a neutral placeholder with the Vietnamese sentence, hides camera and region handles that belong to another picture, and the Shot tab shows the same explanation. It recovers by itself when the frame can be drawn again.

**From the tester's observations.**
- After a two-tab merge, undo cannot go back past the merge: the history starts fresh at the merged document, and the merge notice says so. Otherwise an undo followed by a save silently removes the other tab's edit.
- The same issue sentence repeated for several keys of one camera is shown once per key with the key's number (`args.index`), or once with a count when the keys cannot be told apart.
- Two tabs changing different fields of the same shot still get the conflict dialog. That is the rule as designed; no change.

## Backend findings R3B-002 to R3B-013 (added 2026-11-16, evening)

Interface addition for the page: narration operation `{"op": "order_like_outline"}` puts the narration's chapters in the outline's order (chapters the outline does not have keep their relative place at the end). The chapter differences gain `order: true` when the two orders differ.

**R3B-002 (major). The depth check is linear and bounded.** One pass over the bytes, counting brackets outside strings; no rescans. A body over 8 MB is 413 before it is parsed. Acceptance: a legitimate 2 MB body is checked in under 50 ms, and no body of any shape holds the event loop for more than about 100 ms. Look for the same quadratic pattern in every other hand-written scanner or parser (`parse_outline`, `parse_script`, text folding, the path helpers).

**R3B-003 to R3B-006. One loader for every project file.** Each JSON or text file of a project is read through one helper that takes the expected shape and turns "missing", "unreadable", "a directory", "wrong encoding", "wrong shape" (including wrong types inside `shots` and `overlays`, or `sources` that is not a list) into `DataError`, which every route answers as 409 `data_error` naming the file. Search `bti/editor`, `bti/script`, `bti/library`, `bti/media` and `bti/engine` for every `json.load`, `json.loads(...read_text`, `read_text` and `open(` on project data and route them through it. After the file is repaired the project works again without a restart.

**R3B-007 (major). Chapter order is part of the comparison.** A narration whose chapters are in a different order from the outline's is not approvable: `order: true` in the chapter differences, an error for approval, saving allowed. The operation above fixes it in one step.

**R3B-008. "Validate accepts, so it draws" holds at the bounds.** For every numeric param, `min`, `max` and the default must each draw (with the other params at their defaults). Where a bound does not draw, either the technique is made to cope or the bound is tightened to the largest value that draws and still makes sense. The permanent sweep now includes both bounds of every numeric param.

**R3B-009. A damaged media file is found by validation, not by luck.** An image that does not decode completely (truncated, zero bytes, not an image) and a video that cannot be opened give an error issue with `args.asset`, so approval is refused. The check is cached by file size and modification time so that validation stays fast.

**R3B-010. Messages for the owner carry no exception text and no server paths.** `detail` is a short sentence with paths relative to the project; the raw exception goes to the server log only.

**R3B-011.** An upload that loses a race with a delete answers 404.

**R3B-012 (major), R3B-013. The model list can never break or delay a job.** The CLI's output is decoded leniently; any failure of the list (bad bytes, garbage, missing program, time-out) takes the failure path and is cached for one minute. Starting a job with the `mock` model, or any model that is not an Antigravity one, never calls the CLI. For an Antigravity model the slug is checked against the cached list when one is fresh; otherwise the job starts and a wrong slug fails with a clear message. No lock is held while the CLI runs.
