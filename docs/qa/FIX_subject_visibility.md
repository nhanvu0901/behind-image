# Subject visibility and borrowed captions

A subject's `where` may contain one place or a list of painting regions and borrowed assets. Picks validation, typed operations, automatic picks and draft compilation preserve both forms. The picks instructions ask for all regions that can introduce a subject, including its head, bust, carving or scene, and for its borrowed picture. Existing single-place documents remain valid.

The visibility check evaluates the sentence containing each `about` entry across every overlapping shot. It samples camera motion at 0.25-second intervals, shot boundaries and camera keyframes; a completely framed region counts regardless of its size, as does an on-screen region explicitly used by the shot. For large ordinary objects, at least 40% of the subject region also counts in a wider frame. A map naming a place counts for the place. The pointer uses an actually visible place, preferring the shot's own region.

For a person whose only place is a tall whole-figure box, an explicitly identified head, face or bust region takes precedence. When no such region is recorded, the upper third of a tall figure box is the head-end approximation. For other orientations the checker does not infer a head end. A shot focused on a separately identified hand or foot does not introduce the person unless the identified head is also visible. This is a geometric fallback, not a claim about pose; picks should explicitly record the head or bust whenever it can.

The compiler adds an X-ANN-02 caption to a borrowed picture without an X-ANN-01 or X-ANN-02, through the end of its shot. For an X-CMP-01 swap sequence, each caption follows its picture until the next swap. A missing or placeholder title or bare domain yields no caption and the `borrowed_without_caption` warning. Maker and year are included only for Met collection records: the Met adapter maps `artistDisplayName` and `objectDate` from the collection object. Other sources, including Commons, generic web, OpenStreetMap and stock photographs, receive title-only captions because their creator or date may refer to a photograph. No model-written strips were removed by this change.

## The 17 original warnings

The real project and its original picks were read without modification. These classifications come from replaying the original storyboard and timing with the updated checker; the shot and time in parentheses are one sampled moment during the sentence. Sixteen were false; one remains true.

1. **False** — b0130, Giovanni Arnolfini, s0105: the head-end of the figure is visible in s0105 (7.48 s).
2. **False** — b0131, Costanza Trenta, s0106: the head-end is visible in s0106 (15.56 s).
3. **False** — b0133, two visitors, s0309: the shot's own doorway-figures region is in the frame (35.82 s).
4. **False** — b0136, Bruges, s0405: the borrowed map of the place appears later in the same sentence, in s0417 (78.85 s).
5. **False** — b0136, Lucca to Bruges, s0418: MAP-01 names the places (80.65 s).
6. **False** — b0138, Giovanni Arnolfini, s0320: the head-end is visible in s0320 (103.72 s).
7. **False** — b0139, Costanza Trenta, s0322: the head is visible in s0322 (117.77 s).
8. **True** — b0144, Virgin Mary, s0440: the old picks name a borrowed picture of Mary, but that picture is not shown during the sentence.
9. **False** — b0152, Saint Margaret, s0342: the old picks list only the borrowed picture; it appears later in the same sentence in s0421 (262.79 s). A new picks run can also record the carved region.
10. **False** — b0154, window glass, s0348: a substantial part of the window region is visible in the wider view (280.49 s).
11. **False** — b0159, two visitors, s0422: the shot's doorway-figures region is visible (332.22 s).
12. **False** — b0160, two visitors, s0163: the region is visible within the sentence, including in s0163 (349.08 s).
13. **False** — b0161, two visitors, s0442: the doorway-figures region is visible in s0442 (360.55 s).
14. **False** — b0175, Costanza Trenta, s0185: the head-end is visible in s0185 (505.18 s).
15. **False** — b0177, red bed, s0436: a substantial part of the bed region is visible in the wider view (529.50 s).
16. **False** — b0184, Costanza Trenta, s0444: the head-end is visible in s0444 (617.24 s).
17. **False** — b0187, two visitors, s0210: the shot's doorway-figures region is visible (660.61 s).

## Verification
- `tests/draft`: 623 passed, 1 warning in 206.28s (0:03:26).
- `tests/picks`: 488 passed, 1 warning in 143.76s (0:02:23).
- `tests/engine -m "not slow"`: 836 passed, 14 skipped, 166 deselected in 385.79s (0:06:25).
- `tests/auto`: 264 passed, 1 warning in 108.19s (0:01:48).
- `tests/ops`: 556 passed, 1 warning in 145.78s (0:02:25).
- `tests/cli`: 132 passed, 1 warning in 50.25s.
- Node: 490 passed, 1 skipped; `node --check` passed for both JavaScript files.
- Focused LAY-01 borrowed-caption regression: 1 passed, 34 deselected in 1.07s.
- Generator checks: `bti.cli.docgen --check`, `bti.ops.doc --check`, and `bti.editor.hints --check` passed.
- The Python suites emitted the existing Starlette/httpx deprecation warning where shown.
