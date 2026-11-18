# Fix B-follow: safety switch in the media package, free-service licences, Pexels video titles

Worker `bfollow`. Tests ran on the Windows server from the private snapshot `bfollow`: `tests/media` 222 passed,
`tests/picks` 65 passed (baseline before this task: 142 and 60). No real request, no key read or printed.

## 1. `BTI_NO_REAL_MODELS=1` refuses with `real_models_off`

`bti/media/errors.py` `RealModelsOff(MediaError, ValueError)`, `code = kind = "real_models_off"`. A ValueError with a `code`, so
`bti.picks.service._translate` and `bti.editor.media_adapter._translate` already turn it into an error that keeps the code.
`bti/media/safety.py` `refuse_if_real_models_off(what)`: same test as the model providers (value exactly "1").

Where each check sits (always behind the injection point, so a fake opener, runner or client still works under the switch):

| Entry point | Check |
|---|---|
| every picture source (Commons, Met, Pexels, Pixabay, OSM: search, fetch_meta, download, map tiles, geocoding) | `bti/media/http.py:79` `open_url` and `:139` `download_file`, only when no `opener` is injected |
| You.com client: `research`, `search` | `bti/media/youcom.py:107` `YouComClient._call`, only when no `opener` is injected and the client has a key (no key: the old "YDC_API_KEY is not set" answer, no request) |
| `yt-dlp` (search metadata, subtitles, section download, import_clip) | `bti/media/clips.py:115` `_run_capture`, the only place that starts it (default of every `runner`) |
| research calls (`visual_research`, `confirm_claim`, `resolve_suggestion`) | they go through the client and the sources above; `bti/media/research.py:305` makes sure `resolve_suggestion` does not swallow the refusal as "one failing source" |
| refusal must not be hidden | `clips.py:200` (subtitle fetch), `:292` (`gather_candidates`), `:467` (`moment_search` row); `sources/osm.py:128` (a refused tile must not become a cached grey map) |
| the real suggestion provider | `bti/picks/suggest.py:98` and `:110`: the refusal from the client or the sources becomes `PicksError(409, ..., "real_models_off")`, so the job fails with that code and a sentence (`PART_ERRORS`). The config refusal `suggest_off` still comes first |

Local-only programs are not refused: `ffmpeg`/`ffprobe` (`clips.py` `subprocess.run`) read and write local files, and the book
source reads the project's own files.

Tests: `tests/media/test_safety_switch.py` (28 test functions, some parametrized: the helper, the code through both HTTP layers,
one test per You.com call, per research call, per clip function, per source and method, the facade, a tripwire on
`urlopen`/`Popen`/`run`, fake transports still working, a key never in a message) and `tests/picks/test_safety_switch.py` (5).
I also fixed `tests/picks/test_api.py`: its `sources` fixture left the keyless `osm` source with no fake transport, so the default
search would have made a real request (it now injects a fake transport and no keys).

## 2. Licences of the free services

`bti/media/licence.py`: `check_text` now accepts "Pexels License", "Pixabay Content License" (also "Pixabay License" and a bare
"Content License") and "ODbL" (also "ODbL 1.0", "Open Database License"), with those canonical names, so `flag` is `None`.
`licence_url(name)` gives the link of each (pexels.com/license, pixabay.com/service/license-summary, openstreetmap.org/copyright).
Look-alikes (a bare "Pexels", "Open Database", NC variants such as "Pexels License non-commercial") are still not allowed.
The gate stays advisory. Tests: `tests/media/test_licence.py` (names, links, look-alikes, candidates of all four sources carry
`flag: null`).

## 3. Pexels video titles

`bti/media/sources/pexels.py` `title_from_page_url` / `video_title`: "Aerial View of Oslo Fjord" from
`.../video/aerial-view-of-oslo-fjord-12345/` (trailing id removed, short words kept lower case, percent-encoding and a language
prefix handled, max 100 characters). No words in the URL (`.../video/857251/`) or not a video page: "Video của <author>"; with
no author either, "Video Pexels <id>". Tests: `tests/media/test_pexels.py`.

## Needs another worker

- `bti/editor/static/js/errmsg.js`: no Vietnamese sentence for the code `real_models_off` yet (the suggestion job already carries one
  from `PART_ERRORS`; a direct `/search` or `/import` error with that code has none). Only appears when the switch is on, so on a
  test rig, not in the owner's app.
- Test folders I did not run (not mine): any `tests/editor` or other test that searches with the default sources and no fake
  transport would now get `real_models_off` instead of a real request.

## Follow-up: `tests/editor` after the switch

**Cause.** `tests/editor/test_round2_fixes.py::test_upload_and_import_racing_a_delete_answer_404_and_leave_nothing` (10 cases) slows
`media.import_candidate` and then lets the real function run on `{"source": "commons", "source_id": "File:x.jpg"}`. Its media
facade had no fake for `commons`, so `CommonsSource` made a real request through `bti.media.http.open_url`. The check sits at the
right place (behind the injection point, only when no opener is given); the test was simply reaching the network, and it answered 404
only because the real fetch failed there (so it never tested the race on the registration step). With the switch the answer was
422 `real_models_off`. It was not an interaction with another agent's change (read from the traceback: the refusal message names
`network request to common...`).

**Change** (only this test, assertions untouched): inside the test, a local `FakeCommons` is put into `media.module._SOURCES["commons"]`
with `monkeypatch.setitem`: `fetch_meta` returns a small CC0 image record, `download` writes a tiny PNG, `credit` returns a credit.
Now the real import runs to the point where it registers the asset into a project that was deleted meanwhile, and answers 404 with
no folder left, which is what the test is for. The test is neither skipped nor weakened.

**Same problem elsewhere** (snapshot `bfollow`, one folder per run):

| Folder | Result |
|---|---|
| `tests/editor` | 414 passed |
| `tests/deep -m "not timing"` | 214 passed, 4 skipped, 1 deselected, 1 failed |
| `tests/script` | 135 passed, 6 skipped |

No test in these folders meets `real_models_off`. The one failure, `tests/deep/test_sound.py::test_failed_write_leaves_the_file_intact`
(PUT of a storyboard answers 200, expected >= 400), is not about the switch and not mine: the test patches `os.replace`, but
`bti/fsio.py` (commit 94c5c89, "Retry file renames on Windows") keeps its own reference to `os.replace` taken at import, so the patch no
longer reaches the write. Left as is; it needs the owner of `bti/fsio.py` or of that test (patch `bti.fsio._replace` instead).

## Follow-up 2: `atomic_replace` looks up `os.replace` at call time

`bti/fsio.py`: the hook `_replace` is now `None` by default and `_do_replace` calls `(_replace or os.replace)(src, dst)`, so a caller
that patches `os.replace` (the deep test `test_failed_write_leaves_the_file_intact`) reaches the final rename again. A test that
sets `fsio._replace` still works, so the Windows retry behaviour and its tests are unchanged. The deep test is untouched. New test:
`tests/fsio/test_fsio.py::test_a_patched_os_replace_is_reached` (both Windows and other settings). Snapshot `bfollow`: `tests/fsio` 9 passed,
`tests/deep -m "not timing"` 215 passed, 4 skipped, 1 deselected, `tests/editor` 415 passed.
