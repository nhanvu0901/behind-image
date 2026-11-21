# Pointing at small things, readable text, speed 1.1 for new projects, the voice mix's true peak

Worker `pointfix` (Codex, 2026-11-20/21). The worker ran out of usage after the code and its test runs were finished
and before it rewrote this report; the coordinator wrote this version from the code, the worker's logs and a
verification of its own (last section).

## Why
The owner's review of the Arnolfini video (2026-11-20): small things the narration points at had only the label strip
("ribbon text"), the darkening round the thing was used three times in the whole video; the label "Green dress" was
readable for a tenth of a second; "lets decrease [the speed] by 10%". And on the real project a voice at tempo 1.1 was
refused for a true peak 0.24 dB over the limit.

## What changed
**A. A small thing the narration points at is lit.**
- `style/gae/techniques.json`: `HI-01` is the standard pointer, used every time a `detail` sentence names a thing that
  is small on the screen, also in shots that follow each other and on a near frame; the limits "a close-up", "two shots
  in a row", "the first minute", "more than one in two minutes" are gone. `X-ANN-01` comes with `HI-01` for a small
  thing and never alone. `AN-01` is narrowed to one thing among several of the same kind that a pool of light would
  hold together. Rule 14 and the `detail` row of `skills/storyboard_draft/TASK.template.md` say the same
  (`skills/storyboard_edit/FAST.template.md`, `skills/storyboard/SKILL.md` follow).
- `bti/draft/compile.py`, `bti/draft/defaults.py` (`overlay_default_window`): an `HI-01` without an end runs to the end
  of its shot less its fade and is never under 2.5 s (its start moves earlier, not before the shot's start); a shot too
  short for that is the compile problem `highlight_short_shot`; `floor` is at least 0.6; an overlay whose start word is
  outside its shot is the problem `overlay_outside_shot`.
- `bti/engine/viewchecks.py`: `small_detail_not_lit` (a `detail` line whose region is inside the frame and under
  `SMALL_ON_SCREEN` = 0.40 of its width and height through the line's shots, with no `HI-01`, `X-HI-01`, `AN-01` or
  `KEY-01` label on the region or inside its box) and `highlight_nothing_to_dim` (the lit ellipse, clipped to the frame,
  covers more than `MAX_LIT_AREA` = 0.45 of it).

**B. Text stays long enough to read.**
- `bti/engine/techniques/explain_over.py`: `MIN_READ_S` = 1.5 s for up to three words, 0.3 s more for each further
  word, 4.0 s at most (`min_read_seconds`). `plan_label_times`: a `KEY-01` label still appears on its word, but a label
  that could not be fully visible that long before the overlay leaves is shown earlier, the earlier ones only as far as
  the spoken order with 0.25 s between two labels needs. It runs where the technique plans its labels, so a stored
  storyboard, a retimed one and a typed operation all get it. The compiler's default end of a `KEY-01` is the end of
  its shot.
- The compiler's default start of every other overlay that writes text moves earlier when the end of the shot would
  cut the text short. `text_too_brief` in `viewchecks.py` flags any text that still gets less than it needs.

**C. Speed.** `config/voice.json` / `bti/voice/config.py`: `new_project_tempo` 1.1, written into a project's own voice
settings at creation (`bti/library/projects.py`, beside the opening silences). The fallback `tempo` stays 1.0: a
project made before keeps its speed.

**D. The voice mix.** `bti/voice/assemble.py` `normalise`: up to five encodes; after each one that measures above the
target the limiter's margin grows by the overshoot plus 0.3 dB; only the fifth failure raises, with every measurement.
`bti/voice/run.py`: the job's error carries the detail of a `voice_assemble_failed`; the Vietnamese sentence no longer
says "ffmpeg lỗi" for every cause; the command prints advice that fits a timeout (`bti/cli/main.py`).

**The automatic run** (`bti/auto_run/checks.py`): `small_detail_not_lit`, `highlight_nothing_to_dim` and
`text_too_brief` stop it at the storyboard gate like `outside_on_painting`; the draft's own check lists them first, so
the model repairs them in its session.

## On the real Arnolfini documents (`.scratch/agy_tasks/pointfix/data/arnolfini/`)
- Shot `s0078`, the overlay runs 472.61 to 475.67 s as stored: labels at 473.11 / 473.85 / 474.77 s before, at 472.87 /
  473.12 / 473.37 s now; each is fully visible 1.5 s or more.
- `text_too_brief` flags six texts of the stored storyboard: three words of the figure in `s0024` (0.78, 0.53 and
  0.38 s of 1.5), its caption (2.13 of 2.7), the caption of `s0095` (2.01 of 2.1), the quotation of `s0098` (1.59 of
  2.4).
- `small_detail_not_lit` flags NO line of the stored storyboard, and that is a limit to know: the settle, the gargoyle
  and the carved woman sit inside loose regions (`JOINED_HANDS` 768 x 736 px, `CHAIR_SAINT` 538 x 736 px) that fill the
  frame, so the check takes them for large things. It bites once regions are tight boxes of one thing (worker
  `tightbox`) and the camera is computed from them (worker `boxcam`).
- `highlight_nothing_to_dim`: none; the three stored spotlights cover 1 to 12 % of the frame.
- Real speech (the project's 1.1 voice, pre-mix rebuilt on the snapshot): the old `normalise` fails after two encodes
  at -1.44 dBTP; the new one passes at the second encode with -1.71 dBTP and -15.11 LUFS (target -15).

## Verification by the coordinator (2026-11-21)
On the worker's final tree, snapshot `pointfix`: `tests/engine -m "not slow"` 775 passed, 14 skipped; `tests/draft` 518
passed; `tests/voice` 106 passed, 1 skipped; `tests/auto` 239 passed; the Node command 495 passed, 1 skipped; the three
generator checks exit 0. The worker's own last runs of the other folders: `tests/editor` 530, `tests/ops` 530,
`tests/state` 320, `tests/output` 78, `tests/cli` 132, all passed.
Stills rendered by the coordinator with this code from the worker's three fixture projects (the Arnolfini storyboard
with a tight gargoyle region): the gargoyle under `HI-01` at floor 0.6 stands out from a darker frame, with and without
the strip; shot `s0078` shows its three labels together at 474.0 s and still at 475.0 s.

## Not done, or to know
- The worker's four stills were never written by the worker; the coordinator's are not in the repository.
- The time each technique's text is visible is worked out in `viewchecks.py` and `defaults.py` technique by technique,
  beside the engine's own drawing code: a technique whose timing changes must be changed in both places.
- Three helper scripts of the proof (`tests/engine/pointfix_report.py`, `tests/voice/pointfix_old_assemble.py`,
  `tests/voice/pointfix_speech_proof.py`) were left out of the commit.
