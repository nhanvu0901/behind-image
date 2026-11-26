# Music step

The optional music document is available after the storyboard and timing exist.
Its validator resolves word, absolute-time, chapter, ident and end anchors and
checks recording duration, bounds, levels, fades and cross-fade overlap. Music
storage uses an atomic write and an optimistic revision check. The model chooses
recordings and placements, and the export page offers playback, reselection and
removal. The automatic run attempts selection once and reports `music_none` if
music cannot be selected; it can still export the voice.

## Library and export mix

The fetch tool accepts only file metadata that explicitly marks the recording CC0
or public domain and rejects contradictory attribution or share-alike terms.
It keeps Commons file-page URLs and performer credits, converts to Opus, and
measures integrated loudness. The 60 seed searches span six periods; an accepted
search result must identify the composer and work in its filename. An explicit
sample run inside the Windows snapshot downloaded one small public-domain audio
file. Commons subsequently returned HTTP 429; the tool now stops on that reply.
The seed dates are broad period ranges rather than researched composition dates.
Forces are broad seed descriptions rather than a verified instrument-by-instrument
list, and Commons’ Artist metadata is used for the performer credit.

The mix trims each cue, applies gain, fades and delay, combines music cues, ducks
the music with a compressor keyed from the voice, and applies FFmpeg loudnorm to
the combined programme. An eight-second synthetic test measured -13.4 LUFS and
-8.5 dBTP (AAC). The test's 200 Hz music component measured 72.1 during speech and
971.7 in the pause (arbitrary linear units). Video part keys do not include music;
export tracks a separate signature of the document, library entries and files.

The music session receives the painting metadata, aligned chapter/beat text,
word timings, measured speech gaps, landmarks and catalogue. It validates its
output in a confined workspace before committing against the original document
revision. If the storyboard, timing, painting metadata or library changes while
the model works, the result is refused. The job shares the existing `title` long-job family so the existing
one-agent-run checks also serialize it with title, draft and picks work without
changing those workers' files; its metadata identifies the action as music.
Workspaces are retained under `run/music-work` for inspection.

The optional `music_dir` setting in `run/settings.json` selects another library
directory; absent that setting, `music/` at the repository root is used and is
ignored by git. `python -m bti.music.fetch` adds to its `library.json`; use
`--limit`, `--max-downloads`, and `--max-mb` to bound a run. The fetcher does
not infer a more precise date or instrumentation than the seed supplies, and
searches can return no accepted recording. It does not verify a Commons licence
independently of Commons' file metadata or automatically decide whether a music
placement is aesthetically right. A library still needs to be populated after
deployment; the sample belonged only to the temporary snapshot.

## Verification

The Windows snapshot passed `tests/music` (34), `tests/export` (86, two
skipped), `tests/auto` (266), `tests/cli` (132), `tests/settings` (44),
`tests/editor` (534), and `tests/title` (198). A focused export regression
passed two tests after the final mix changes. All three document generators
passed `--check`. The Mac frontend and output suite passed 475 tests with one
skip; changed JavaScript files passed `node --check`. The skipped export tests
require a real render and were not run; no real model call was made. The
fixture-based Commons licence tests use local API-shaped answers, without
network access.
