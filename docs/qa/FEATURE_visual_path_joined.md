# Visual path joined

Visual edit and review routes are mounted. The state exposes `visual.edit` and dispatches the single `storyboard.review` action to the visual or legacy worker by pipeline. Visual edit discloses web-search cost. Automatic visual review disables paid search for repair. Edits compose once. Agent jobs reserve a shared slot atomically; synchronous composition reserves that slot and checks the deploy lock.

Approval metadata no longer invalidates a viewer review, while changes to the picks content still do. This fixes the real-data loop in which review edits changed picks, the picks gate was reapproved, and the same review was requested again. A visual `--until edit` run also waits for the visual plan and current composition rather than accepting an inherited storyboard.

## Real-data acceptance

`arnolfini-v3` was copied into the Windows snapshot; the source project, live application and music library were read-only. All model sessions and picture searches were fakes. One recording was copied into the snapshot. No final video was rendered, no paid API or real model was called, and the run stopped before export.

The supplied golden document had 137 mechanical errors: V3 74, V8 35, V5 4, V1 1, V7 22 and V6 1. Its old storyboard contains region names absent from current picks. Through typed operations on the copy, seven unused regions were removed and 19 recorded regions restored, removing 29 V3 and one V8 findings. The 60-region cap left nine names unavailable. Five moments fell back to whole-painting views and four missing-region points were dropped. The repair script in `.scratch/agy_tasks/wireup/repair.py` then removed 22 V7 subtitles, one V6 and one V5 by dropping ordinary-object strips, 30 V8 person points, one V1 by splitting at a line boundary, five V3 and four V8 by recording the unavailable-region fallbacks, three V5 introductions, and 40 V3 by marking the old picture as not showing its subject. Final validator errors: zero. These fallbacks reduce fidelity and are not proof that the converted script makes a good video.

The first fake plan job failed because the fake omitted a result field; the next status correctly offered `visual.plan` again. The original review report was then invalidated by reapproving picks, exposing the signature bug above. After fixing it, a fresh review ran and reapproval advanced to the storyboard gate. Three shot findings were simulated; repairs changed their moments, and a deliberately unavailable picture was recorded. The final review warnings visible to the owner included “Không tìm thấy hình cho Unavailable test picture.” for two shots. These were simulated findings, not factual judgments by a model.

The real automatic runner on a separate copied project, using fake sessions and `until=edit`, completed these eight actual actions: `visual.plan`, `picks.approve`, `storyboard.compose`, `storyboard.review`, `picks.approve`, `scorecard.make`, `music.auto`, `storyboard.approve`. It ended `until_reached` and the next command was `export.start`; export was not started. Before the fix the same `until=edit` stopped after the first two actions because the old storyboard made the step appear done. A separate run with `max_steps=8` also stopped before export.

After review the scorecard measured 110 shots over 672.73 s: small whole-painting share 8.23% (target 6%), 0.27 marks/min, biggest mark 22.5% of frame height, zero marks on people, four name strips with zero repeated subtitles or ordinary-thing strips, five borrowed pictures for 20.62 s, longest gap 554.2 s, zero borrowed pictures under three seconds, zero short non-program shots, five maximum repeated-region uses, and 38 subjects not shown. There were zero hard-line failures and four other failing metrics. Loudness and pause-vs-speech were not measured because there was no export.

I inspected all 19 initial six-shot review sheets and the one sheet of changed shots. The opening shows the full portrait small between broad dark side bars twice, then the couple, gown and dog; Lucca and two portraits appear early. The first introduction of Giovanni has no visible name strip in these sampled frames. Long middle stretches repeatedly show crops of the same painting and mirror. Dürer and Velázquez appear near the end. These stills do not establish motion, pacing or whether every sentence matches its picture; the 554.2-second gap and 38 unshown subjects remain material problems.

## State answers

The table lists every action offered at each observed checkpoint. `*` means not ready; the next command is the actual text from the state renderer. These are snapshots of the copied project, not claims about the live server.

| Checkpoint | Offered action IDs | Next |
|---|---|---|
| initial | `visual.plan`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `picks.ops`, `changes.list`, `changes.undo`, `auto.run`, `storyboard.validate`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `music.auto`, `music.set`, `music.clear`, `picks.approve*`, `export.start*`, `scorecard.make*` | next: bti do arnolfini-v3 visual.plan --yes-cost --wait   (Viết kịch bản hình) |
| plan before | `visual.plan`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `picks.ops`, `changes.list`, `changes.undo`, `auto.run`, `storyboard.validate`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `music.auto`, `music.set`, `music.clear`, `picks.approve*`, `export.start*`, `scorecard.make*` | next: bti do arnolfini-v3 visual.plan --yes-cost --wait   (Viết kịch bản hình) |
| plan after | `picks.approve`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `auto.run`, `storyboard.validate`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `storyboard.compose*`, `export.start*`, `scorecard.make*` | next: bti approve arnolfini-v3 picks   (Duyệt chọn hình) |
| picks gate after | `storyboard.compose`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `storyboard.validate`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `auto.run`, `export.start*`, `scorecard.make*` | next: bti do arnolfini-v3 storyboard.compose   (Dựng storyboard) |
| compose after | `storyboard.review`, `storyboard.approve`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `storyboard.compose`, `storyboard.validate`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `auto.run`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `scorecard.make`, `export.start*` | next: bti do arnolfini-v3 storyboard.review --yes-cost --wait   (Xem lại storyboard) |
| review after | `picks.approve`, `storyboard.approve`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `auto.run`, `storyboard.validate`, `storyboard.review`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `scorecard.make`, `storyboard.compose*`, `export.start*` | next: bti approve arnolfini-v3 picks   (Duyệt chọn hình) |
| picks gate after | `storyboard.approve`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `storyboard.compose`, `storyboard.validate`, `storyboard.review`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `auto.run`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `scorecard.make`, `export.start*` | next: bti approve arnolfini-v3 storyboard   (Duyệt storyboard) |
| scorecard after | `storyboard.approve`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `storyboard.compose`, `storyboard.validate`, `storyboard.review`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `auto.run`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `scorecard.make`, `export.start*` | next: bti approve arnolfini-v3 storyboard   (Duyệt storyboard) |
| music after | `storyboard.approve`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `storyboard.compose`, `storyboard.validate`, `storyboard.review`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `auto.run`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `scorecard.make`, `export.start*` | next: bti approve arnolfini-v3 storyboard   (Duyệt storyboard) |
| storyboard gate after | `export.start`, `pipeline.set`, `outline.generate`, `outline.import`, `narration.generate`, `narration.import`, `narration.ops`, `title.generate`, `title.set`, `voice.generate`, `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.put`, `visual.plan`, `picks.ops`, `changes.list`, `changes.undo`, `storyboard.compose`, `storyboard.validate`, `storyboard.preview`, `storyboard.put`, `storyboard.ops`, `identity.set`, `visual.edit`, `music.auto`, `music.set`, `music.clear`, `auto.run`, `scorecard.make` | next: bti do arnolfini-v3 export.start --yes-cost --wait   (Xuất video) |

## Verification

One Windows snapshot folder per invocation. The initial state run reported `6 failed, 369 passed, 1 skipped, 1 warning in 228.33s (0:03:48)` from five stale action-list expectations and one mock that no longer replaced the imported worker; the expectations and mock were corrected. The final folder summaries are reproduced below:

```text
tests/state: 375 passed, 1 skipped, 1 warning in 226.51s (0:03:46)
tests/auto: 280 passed, 1 warning in 108.40s (0:01:48)
tests/editor: 534 passed, 1 warning in 244.81s (0:04:04)
tests/cli: 133 passed, 1 warning in 53.81s
tests/ops: 565 passed, 1 warning in 160.40s (0:02:40)
tests/picks: 506 passed, 1 warning in 141.14s (0:02:21)
tests/draft: 650 passed, 1 warning in 172.92s (0:02:52)
tests/visual: 141 passed, 1 warning in 7.11s
tests/compose: 42 passed, 1 warning in 2.98s
tests/scorecard: 12 passed, 1 warning in 3.60s
tests/music: 56 passed, 1 warning in 11.53s
tests/export: 89 passed, 2 skipped, 1 warning in 67.94s (0:01:07)
tests/identity: 108 passed in 3.76s
tests/output: 81 passed, 1 warning in 20.31s
tests/settings: 44 passed, 1 warning in 4.29s
tests/media: 460 passed in 9.19s
tests/fsio: 9 passed in 0.44s
tests/script: 384 passed, 7 skipped, 1 warning in 33.90s
tests/voice: 108 passed, 1 skipped, 1 warning in 73.82s (0:01:13)
tests/title: 198 passed, 1 warning in 42.69s
tests/library: 163 passed, 1 warning in 5.29s
tests/longjob: 72 passed, 1 skipped, 1 warning in 6.96s
tests/clean_text: 62 passed in 4.39s
tests/engine -m "not slow": 859 passed, 14 skipped, 168 deselected in 367.99s (0:06:07)
```

The three Windows generator checks `bti.cli.docgen --check`, `bti.ops.doc --check` and `bti.editor.hints --check` returned 0. On the Mac the requested Node suites printed:

```text
ℹ tests 514
ℹ suites 0
ℹ pass 513
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
ℹ duration_ms 1107.861292
```

The skipped code-list test was read: it needs `.venv/bin/python`, which this worktree does not have. No JavaScript or new issue code was introduced, so no `node --check` target or new Vietnamese code template was required.
