# Picture-step captions

A borrowed picture's optional `caption` is stored on its picks asset, once per picture. The choice agent writes it in its choice entry; the typed `set_caption` operation writes or clears it and the owner can edit it in the picture rows. Existing picks without a caption remain valid. The compiler uses this caption, or the record title when the same checks accept it, and otherwise emits `borrowed_without_caption`. A name strip takes precedence. App-drawn maps have no caption.

A caption is at most 60 characters, without line breaks, a file extension, camera or numbered image/view pattern, a bare domain, or the asset's own ID. The agent instructions ask for a concise English museum label grounded in the picture record, with work maker and year only when the record establishes them.

## Verification

- JavaScript: 504 passed, 1 skipped; syntax checks passed for the four changed JavaScript files.
- tests/draft: 633 passed, 1 warning in 171.64s (0:02:51).
- Focused picks: 127 passed in 18.50s.
- tests/picks: 506 passed, 1 warning in 152.71s (0:02:32) (exit 0).
- tests/editor: 534 passed, 1 warning in 312.91s (0:05:12) (exit 0).
- tests/auto: 269 passed, 1 warning in 99.44s (0:01:39) (exit 0).
- tests/ops: 561 passed, 1 warning in 185.34s (0:03:05) (exit 0).
- tests/cli: 2 failed, 130 passed, 1 warning in 57.93s (exit 1).
- tests/export: 87 passed, 2 skipped, 1 warning in 54.98s (exit 0).
- tests/identity: 106 passed in 4.99s (exit 0).
- tests/engine: 6 failed, 848 passed, 14 skipped, 168 deselected in 431.41s (0:07:11) (exit 1).
- tests/cli after regenerating picks documentation: 132 passed, 1 warning in 57.83s.
- Earlier engine failures reflected newly required warnings for unclean fixture titles; expectations were updated without changing fixtures.
- tests/engine -m "not slow" after updating warning expectations: 854 passed, 14 skipped, 168 deselected in 412.90s (0:06:52).
- bti.cli.docgen --check, bti.ops.doc --check, bti.editor.hints --check: passed.
