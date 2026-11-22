# Viewer review of a storyboard

After a draft is applied, `storyboard.review` is a model-cost draft-family long job. The automatic run takes it before the storyboard gate; it stops if a required review cannot run. A whole-storyboard `draft.edit` that changes the document appends the same review to its existing job. A no-change edit skips it. The owner can still approve directly.

For each shot the job draws one or two 640-pixel stills in process, at occurrences of curated names or asset/region labels, otherwise at the midpoint. The contact sheets include shot IDs and times; timed speech and on-screen text accompany the images. The project’s storyboard agent reviews the sheets using `skills/storyboard_review/TASK.template.md`. Its JSON must cover every shot and uses four codes: `picture_mismatch`, `text_wrong`, `context_missing`, and `picture_repeated`. The job asks the existing request-box editor to repair flagged shots, at most twice, then stores the final report by storyboard revision and input signatures. Remaining findings appear as `review_<code>` issues in the storyboard GET and as warnings that stop automatic approval; the current report is also in the draft-thread GET. Stale input or concurrent storyboard edits prevent the report from being accepted.

The estimate is 10–15 minutes of model time for a 120-shot review, plus repairs. It has not been measured with a real model. Subject timing currently matches curated names and picture/region labels, so an unlabelled subject can fall back to the midpoint. Review rounds have separate long-job parts; a repair round containing many edit batches can still reach the per-part time limit.

## Verification

No real model was called. The new review code is tested with fake frame sources and providers; other draft tests replace follow-up review with a fake, and the editor/state/auto/CLI fixtures reject unexpected real viewer rounds. Before these safeguards were installed, a draft test run was stopped because it could have generated real stills; whether it had already done so was not established.

The full Node run reported `ℹ tests 500`, `ℹ pass 498`, `ℹ fail 1`, `ℹ skipped 1`. The failure is the pre-existing `tests/editor_frontend/idfix.test.mjs:17`: it expects `Settle`, while another worker's current `strip_without_light` message omits it. The dedicated review-issue frontend test passed.

The full Python suites were rerun on the Windows snapshot with fake or blocked viewer execution:

```text
575 passed, 1 warning in 197.06s (0:03:17)
533 passed, 1 warning in 271.35s (0:04:31)
327 passed, 1 warning in 210.22s (0:03:30)
260 passed, 1 warning in 99.08s (0:01:39)
132 passed, 1 warning in 49.23s
```

These lines correspond respectively to `tests/draft`, `tests/editor`, `tests/state`, `tests/auto`, and `tests/cli`. After the full draft run, the review-specific tests were extended and provider error handling was changed; the latest targeted run reported `25 passed, 1 warning in 1.62s`. The additional storyboard and thread GET test reported `1 passed, 1 warning in 0.87s`. The three generated-document checks (`bti.cli.docgen`, `bti.ops.doc`, and `bti.editor.hints`) each exited 0 after regeneration.
