# Place music for this video

Read `inputs/context.json`. It contains the painting's identity, narration by
chapter and aligned word times, pauses, the storyboard's ident and chapter
landmarks, the video end, and the local recording catalogue. Use only recordings
in that catalogue. Never invent painting facts or recording metadata.

Choose classical music by what the video needs: the mood of the story, its
pace and where it turns. Do not tie the choice to the painting's date or
country; any recording of the catalogue may serve any painting. Use a main
recording and one or two contrasts, not a new piece for every chapter. Keep the
cold open quiet and sparse, rise at the ident, make a low bed under speech that
breathes in pauses, change colour when the story turns, and let the ending close
on the last shot. Silence is allowed.

Write `out/music.json` as `{ "cues": [...] }`. Each cue has:
`recording` (catalogue id), `start` and `end` anchors, `offset` (seconds into
the recording), `role` (`bed`, `swell`, `ident`, `ending`), `level_db` (gain
from -60 to -6 dB), `fade_in` and `fade_out` (seconds), and `why` (one sentence).
Anchors: `{ "t": 12.5 }`, `{ "w": 12, "text": "word", "off": 0 }`,
`{ "chapter": 0 }`, `{ "ident": true }`, or `{ "end": true }`. Chapter
indices are zero-based. A recording excerpt must be long enough; cues may
only overlap within both fades and three cues may never overlap. Fades must fit
within a cue. Keep every cue within the video. Run the provided check command
(`./check` on Unix, `check.cmd` on Windows) and fix every error before finishing. Do not modify the input files.
