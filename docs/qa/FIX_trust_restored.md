# FIX: a third trust level, `restored` (worker `grovint`, 2026-11-19)

Branch `wt/grovint`, worktree `.worktrees/grovint`. Nothing was committed, nothing was copied to or rebuilt on the server.

## 1. What was built

A source now has one of three trust levels, `normal`, `restored`, `low`, decided per **work**. A work is `restored` when its book has
`library/restored/<book>/` with a readable `review.json`, the work's verdict is `usable` or `usable_after_fixes`, and every fix the
review lists for it is in `review_fixes.applied.json` (plus: every page of the work has a restored file; when `report.json` is there it
lists the work as not failed with the same pages as the catalogue). Every doubt is a no and the work keeps its book's level. On the
real data (read-only, from the Mac) 55 works are `restored` and works 2 and 54 stay `low`.

| Part | Where |
|---|---|
| the gate, the page files, the `[…]` mark, the word count | new `bti/library/restored.py` |
| the level of a work, the override rules | `catalogue.work_trust`, `work_trust_why`, `book_forced`, `book_trust` |
| the text built for a restored work | `clean.entry(work, restored=True)` |
| dossier numbers and flags, rebuild of one book | `dossiers.build_one`, `build_book`, `keys_of_book`, `live_trust`, `summary` |
| project default sources | `projects.create_project` (`_work_level`) |
| the note, the flag, the included default | `bti/script/brief.py` |
| API fields | `bti/editor/library_api.py` (`words_restored`, `no_normal_source`, `restored_books`, live level per source) |
| page | `labels.js` (block "grovint"), new `trust.js`, `views/library.js`, `views/script.js`, `views/artwork.js` |
| commands | `python -m bti.library dossiers --book BOOK_ID`, `python -m bti.library trust BOOK_ID` (read-only) |
| docs | `docs/design/2026-11-16-library-design.md` (section Trust), `docs/APP_GUIDE.md` |
| tests | `tests/library/test_restored.py`, `tests/script/test_brief_trust.py`, `tests/editor_frontend/trust.test.mjs`, one real-data assertion widened in `tests/library/test_dossiers.py` |

## 2. Decisions the coordinator should know (each can be reversed in one place)

1. **The override file.** The real `library/overrides/books.json` has `grovier_nws: {"trust": "low", "trust_note": ...}` written by
   `build()`. If an explicit `low` forced the level, the restoration would never take effect. So an entry **forces** a level only when it has
   `"force": true` or names a level other than the built-in one of the book (`low` for Grovier, `normal` for the rest). The existing file
   therefore leaves the review in charge. To switch the restoration off: `{"grovier_nws": {"trust": "low", "force": true}}`. `normal`
   forces every work normal. `restored` forces every work that has its restored page files to `restored` **without asking the review** (the
   owner vouches for it; a work without those pages becomes `low`). `book_trust()` still returns the level of the book (`low`) with the same
   two keys as before.
2. **Restored sources are included by default** (project creation, the brief, the create dialog); only `low` needs the owner's tick. This
   is the point of the restoration; if you want restored to need a tick too, change `low = trust == "low"` in `brief.py` and `_work_level(...) == "low"` in `projects.py`.
3. **The catalogue's own names** (title, artist, year of an artwork, `catalogue.source_rank`) still rank a `restored` book like `low`. Restored
   text does not make the TOC names more trusted. Named constant `MACHINE_TEXT`.
4. **Labels are live, text is not.** The dossier page shows an edit of `books.json` at once, but a source is never shown as `restored` unless the
   text in its dossier was built from the restored pages (`dossiers.live_trust`). A project keeps the dossier it was made with, so existing
   projects keep their `low` Grovier text.
5. The brief believes `restored` only from the project's own dossier; from the book table (older project shape) it counts as `low`. A trust
   value that is none of the three counts as `low` (before, anything not `low` counted as normal); a missing value is still `normal`.

## 3. Every place that reads trust, and what it does with each level

| Place | normal | restored | low |
|---|---|---|---|
| `catalogue.book_trust` (level of a BOOK; `book.json`, `load_books`, shelf) | default for all books but Grovier | only if `books.json` says so (note = restored note) | default for Grovier; `books.json` |
| `catalogue.book_forced` (does `books.json` force the book's level?) | forced when it names `normal` for a book that is not normal by default | forced: every work with its restored pages | forced only with `"force": true` (or for a book that is not low by default) |
| `catalogue.work_trust` / `work_trust_why` (a WORK) | book `normal`, or forced | review gate says yes (or forced `restored` with pages) | gate says no (verdict, fixes, pages, report), or forced |
| `catalogue.source_rank` (regroup, identity fields) | by clean/outline | rank 4, like low | rank 4 |
| `dossiers.build_one` | plain clean text | restored text (marks, no captions), `words_restored` | plain clean text |
| `dossiers` totals and flags | `words_normal` | `words_restored` | `words_low`; `only_low_trust` = all low; `no_normal_source` = none normal |
| `dossiers.live_trust` | live | live, never above the text of the dossier | live |
| `projects.create_project` default `exclude` | kept | kept | left out unless nothing else would remain |
| `library_api.art_row` (artwork list) | | `restored_books`, `words_restored` | `low_trust_books`, `only_low_trust`; `no_normal_source` for all |
| `library_api.artwork` (dossier view) | live level | live level | live level |
| `brief._level` | missing = normal | believed only from the dossier | a word that is none of the three = low; book table `restored` = low |
| `brief.save_options` (at least one source stays) | counts as in | counts as in | counts only if ticked |
| `brief._build_brief` (`included`, `low_trust`, `restored`, `no_normal_source`) | in | in | out until ticked |
| `brief.render_brief` | plain | `[RESTORED: note]`, `[RESTORED]` header | `[LOW TRUST: note]`, `[LOW TRUST]` header (as before) |
| `views/library.js` (list badge and words, dossier tab, tags, create dialog) | no tag | "Bản khôi phục" badge, tag and note, `+ N (bản khôi phục)`, ticked by default in the create dialog | "dịch máy" (as before), unticked unless alone |
| `views/script.js` (source column) | tick box | tag and visible note, plain tick box | tag, tick box "đã đọc và chấp nhận rủi ro" (as before) |
| `views/artwork.js` (artwork step) | | tag | tag (as before) |

Not changed: the library's view of a book's own page text (`/works/<book>/<n>`, it shows the book as it is), the shelf, `prompts/*`.

## 4. The note to the model (English, exactly as the brief prints it)

On the source's line in the SOURCES list, `[RESTORED: ...]` (the name comes from `book.json`, "the author" if it is missing):

> restored and reviewed rendering of a machine-translated book: its unmarked prose says what the book says, names corrected. Its ideas and readings of the picture may be used as Kelly Grovier's own: say "Kelly Grovier argues" or the like once, never as established fact. NO number, date or quotation may be taken from it unless another source of this dossier confirms it. […] marks a passage that could not be restored: never guess what it said.

The source's text block header carries `[RESTORED]`. It is 443 characters against 54 for the English `low` note, because it has to carry five statements
(what it is, what it says, how to use ideas, what is restricted, what `[…]` means). The Vietnamese note on the page is
"Bản khôi phục từ bản dịch máy, đã rà soát: dùng được cho ý và mô tả; số liệu, năm và trích dẫn phải có nguồn khác xác nhận."

When no source the model is given is `normal` the brief also prints this paragraph under the source list:

> NO FULLY TRUSTED SOURCE: none of the sources given below is a normal source (they are restored or low trust), so every fact of this painting needs care. Call a fact "established" only when it is a plain description of what the picture shows; any other fact is "likely" at most, and the narration says whose claim it is.

## 5. What the script step does when no source is `normal`

Today the script step never read the dossier's `only_low_trust`. What it does with low sources is in the brief: a low source is `[NOT INCLUDED, text withheld]`
until ticked, and when no source is included at all (`totals.included == 0`) the page shows "Chưa có nguồn nào được dùng..." and refuses to start the outline.
The server-side generation does not refuse.

The new flag does **not** refuse (a restored source is usable). It is computed over the sources the model is actually given (`brief.no_normal_source`;
so excluding the one normal source of a project turns it on, and a low source that is not ticked does not count), and then: the brief adds the NO FULLY TRUSTED SOURCE paragraph
above, and the page says "Chưa có nguồn tin cậy đầy đủ cho tác phẩm này." in the artwork list, the dossier, the artwork step and the script step's source column. For a dossier
the flag `no_normal_source` is stored beside `only_low_trust`; `only_low_trust` keeps its meaning (every source `low`).

## 6. Sample: the first 20 lines of the text built for real work 39 (The Scream)

Built by `dossiers.build_one` into a scratch folder from the owner's library (read-only), 736 words, `trust: restored`, meta `(1893)`, no captions:

```
# 39 Edvard Munch, The Scream

Munch's The Scream has become an icon of existential anxiety. More than a century after it was completed, its elongated face remains mesmerizing, like a luminous light bulb that shakes cultural consciousness.

In 1893, the Norwegian Expressionist painter Edvard Munch painted "The Scream": beneath a dark sky, an obscure figure screams endlessly on a high bridge. At that time, electricity had begun to rise. That same year, the famous Serbian-American engineer and inventor Nikola Tesla predicted that one day "electricity" would move like an invisible wave through nature, "transmitting to any distance without wires." Tesla declared: "I firmly believe that it is feasible to interfere with the static environment of the Earth through powerful machines."

However, many generations stand in awe of this possibility for the future, while others are deeply concerned about the uncertain prospect of disrupting the Earth's delicate balance. Munch is one of them. He was often troubled by the impact that the unbridled acceleration of science and technology could have on the structure of nature. In his private diary, the artist acknowledges that he is beset by a mysterious form of "everyone fears" — a gloomy, […] presence:

Who directs the wire?

And the machine.

Hold it in your hand.

Munch briefly studied engineering at a technical school, and he was very familiar with how technology connects to the world through wires. He was keenly interested in the scientific progress of his time. He lived in Paris in 1889, when Paris was hosting a World Exposition at which various inventions of the American inventor Thomas Edison were presented. In addition to displaying the vast number of patented products known as Edison's (almost 500 items), there was a huge and imposing wonder on display, made up of 20,000 incandescent lamps arranged into a shining light.

Large light-bulb shape. It was like a swelling glass skull, with the spherical crown narrowing down to form a thin jaw, raised above the gallery visitors as if heralding a new idolatry — a bright face of a future God.

Edison's light bulb, as a revered shape, gradually became a symbol of the age of power in cultural consciousness. Over time, its distinctive form became the universal emblem for this unexpected invention, like the cartoon light bulbs that suddenly appear above the head of any character with ideas in comic books. At the same time, the symbolic light-bulb shape seems to have pervaded Munch's imagination. A few years later, Munch himself created an iconic shape: the howling head — […]. It echoes with remarkable precision the proportions of the incandescent lamp that Edison made famous.
```

## 7. Server commands (not run; the coordinator runs them)

```
export BTI_SSH_HOST=winbox-cmd
cd /Users/nhanvu/Documents/code/behind-the-image/.worktrees/grovint   # after the branch is merged: the main checkout
# 1. the code (push + fast-forward on the server; --restart so the app loads brief.py and library_api.py)
tools/deploy/git_deploy.sh --check        # dry run first
tools/deploy/git_deploy.sh --restart
# 2. copy the restoration folder: adds library/restored/grovier_nws (pages, report, review files; the backup folders stay on the Mac)
cd /Users/nhanvu/Documents/code/behind-the-image
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -czf /tmp/restored_grovier_nws.tgz --exclude='_before_*' --exclude='_failed' \
  --exclude='report.before_merge_*' --exclude='._*' -C library restored/grovier_nws
scp -q /tmp/restored_grovier_nws.tgz winbox-cmd:D:/code/behind-the-image/run/restored_grovier_nws.tgz
ssh winbox-cmd "tar -xzf D:\code\behind-the-image\run\restored_grovier_nws.tgz -C D:\code\behind-the-image\library && del /q D:\code\behind-the-image\run\restored_grovier_nws.tgz"
# 3. read-only check: 57 lines and {"works_by_trust": {"restored": 55, "low": 2}}
tools/deploy/remote_py.sh -m bti.library trust grovier_nws
# 4. rebuild only the dossiers that hold a Grovier work
tools/deploy/remote_py.sh -m bti.library dossiers --book grovier_nws
```

What they change. Step 1: the new code; with no `library/restored` folder on the server it changes nothing (every Grovier work stays `low`). Step 2: adds the
folder `library/restored/grovier_nws/` (364 page files and 5 json files, 250 KB packed); nothing existing is overwritten. Step 3: nothing (reads only). Step 4: rewrites
`library/dossiers/<key>/dossier.json` and `sources/*.txt` of the 57 artworks that have a Grovier work (the sources of the other books in those artworks are rewritten
with the same text); 55 Grovier sources become `restored` with the restored text; works 2 and 54 stay `low`; nothing else in `library` (not `artworks.json`, not `overrides`, not `books`) and nothing
in `projects` changes. The other dossiers do not get the new keys `words_restored`/`no_normal_source` until a full rebuild; the API and the page do not need them. Existing projects keep their old copy.
Undo: delete `library/restored` (or put `"force": true` on the `grovier_nws` entry of `overrides/books.json`) and run step 4 again.
Take the tar of step 2 at the moment you copy: the folder is still being changed by another worker (see section 9).

## 8. Tests

Python tests ran only through `snapshot_test.sh grovint`, one folder per run (the snapshot's `library` is the server's real library, which has no `library/restored` yet, so the real-data tests see no restoration). Summary lines exactly as printed:

| Run | Last line |
|---|---|
| `tests/library` | `1 failed, 159 passed, 1 warning in 13.24s` |
| `tests/script` | `249 passed, 7 skipped in 36.30s` |
| `tests/editor` | `478 passed, 1 warning in 309.40s (0:05:09)` |
| `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` | `ℹ tests 316` `ℹ pass 315` `ℹ fail 0` `ℹ skipped 1` |

The one failure in `tests/library` is `test_library.py::test_works_json_shape` (missing `artist` key in the real `works.json`), the known failure another worker is fixing; it is the only failure.
New tests: `tests/library/test_restored.py` (20 tests: every level and verdict case, the applied-fixes record present and absent, a fix listed only in `review_fixes.json`, damaged files, report.json disagreeing, a missing page,
a book without a restoration folder, the override rules, the text built (marks, captions, plate pages, words, BOM), the numbers and both flags for normal+restored / restored / restored+low / low / normal+low / nothing,
rebuild of one book and the CLI, `live_trust`, project defaults, the API rows and dossier), `tests/script/test_brief_trust.py` (6 tests: wording per level with the restricted things named, included by default,
the flag for seven mixes, words without marks, unknown or missing levels), `tests/editor_frontend/trust.test.mjs` (6 tests: labels, notes, level reading, the flag). The existing tests pass unchanged except one assertion
of `tests/library/test_dossiers.py::test_overrides_books_file_exists_and_dossier_trust` (real library): it now accepts `restored` as well as `low` for Grovier's source and adds `words_restored` to the sum, so that it is true before and after the server rebuild.

## 9. What I could not verify, and risks

- **No browser.** The page was checked by `node --check`, by the Node unit test, and by running `views/library.js` (list and dossier) and `views/artwork.js` against a small fake DOM with
  canned API answers (scratch, not in the suite). `views/script.js` was only read and syntax-checked: its source column (new line, tag, note) was not run.
- **The data moves.** While I worked, `library/restored/grovier_nws/` changed: `names_pass2.json` (worker `grovier-c`, 00:10) corrected or marked names in 40 pages
  written after `review_fixes.applied.json` (23:58), and work 2 was restored again. The review verdicts are for the text as it was reviewed; the gate cannot see a page edited after the review (the
  review records no hash of the pages). Work 2 stays `low` because `review.json` still says `not_usable`; when the review says otherwise the gate follows without a code change. Decide whether the 40 edited pages need a new review before the copy.
- The gate trusts `review.json`, `review_fixes*.json`, `report.json`; it did not re-judge the text. The review's own limits (original English not available; 1,092 marked passages not judged; "faithful" means faithful to the machine text) stand.
- Nothing enforces the restrictions on the narration (no number, date or quotation from a restored source): they are in the brief for the model. The validator does not check them. `prompts/outline.md` item 5 still speaks only of LOW TRUST sources.
- The explicit `restored` in `books.json` bypasses the review (decision 1).
- Real-data tests outside my files will change once the restored folder is on the server and the dossiers are rebuilt (section 10).

## 10. Needs another worker

- `tests/editor/test_library_api.py::test_low_trust_fields_and_default_exclusion` reads the real library: after the copy and the rebuild `garden of earthly` has `low_trust_books == []`, `words_low == 0`,
  its Grovier source is `restored`, a project from it gets 4 sources by default (it asserts 3 and that `grovier_nws/018` is out), and only 2 artworks (works 2 and 54) have `only_low_trust` (it asserts more than 10).
- `tests/deep/test_sound.py::test_slugs_and_sources` asserts that no `grovier_nws` source is in a project made from the first artwork with 3 or more sources; with restored sources included by default that may fail.
- `prompts/outline.md` item 5 could name RESTORED sources next to LOW TRUST (the brief already carries the rules).

## 11. Follow-up (2026-11-19): the real-data tests and the prompts

The three items of section 10 were taken over. Nothing under `bti/` changed in this follow-up; only tests and prompts.

### 11.1 `tests/editor/test_library_api.py`

`test_low_trust_fields_and_default_exclusion` (same name) no longer hard-codes that Grovier is `low`. It reads the trust values the dossier itself holds
(`dossiers.load`) and checks that everything else agrees with them. It now asserts:
- Garden of Earthly Delights: Grovier's source is `low` or `restored` and the three other books are `normal`; the artwork endpoint shows the same level for Grovier as the dossier (a label never promises more than the text is).
- The artwork row has every field (`low_trust_books`, `restored_books`, `words_normal`, `words_restored`, `words_low`, `only_low_trust`, `no_normal_source`), the three word counts equal the dossier's totals (`words` is their sum),
  `words_low > 0` exactly when Grovier is `low`, `words_restored > 0` exactly when it is `restored`, `low_trust_books` / `restored_books` name Grovier according to that level, `only_low_trust` and `no_normal_source` are false (three normal books).
- Every artwork that only Grovier covers (more than 10 of them): `only_low_trust` is true exactly when the dossier's own level is `low`, and `no_normal_source` is true; every `only_low_trust` row is Grovier-only.
- A default project from Garden: judged by the project's own copy of the dossier, it has no `low` source, Grovier is in exactly when its level there is `restored`, and the other three are always in; `exclude: []` keeps all four with Grovier `low` or `restored`; a Grovier-only artwork keeps its one source.

New `test_a_low_source_is_left_out_by_default_in_any_state_of_the_library` exercises the exclusion rule itself on the real artwork whatever the state of the library: in a temporary copy of the library the owner's file forces
Grovier to `low` (`{"trust": "low", "force": true}`). Then a default project has 3 sources (no Grovier, all `normal` in its own dossier), `exclude: []` has 4 with Grovier `low` and its plain text (`text_source: clean`), the
row shows `low_trust_books == ["grovier_nws"]` and no `restored_books`, and a Grovier-only artwork keeps its one source.

### 11.2 `tests/deep/test_sound.py`

`test_slugs_and_sources` keeps all its slug and 409/422 checks. The last line (no `grovier_nws` source in the default project) is now judged by the project's own dossier: its sources are the ones the response lists, every trust is one of the three levels, none is `low`,
and any Grovier source in it is `restored`. New `test_a_low_source_is_left_out_by_default_when_grovier_is_forced_low` does what the old assertion did in any state: `catalogue.books_overrides_path` is pointed (monkeypatch) at a file that forces Grovier to `low`; the first artwork with 3 or more sources
and a Grovier work gets a default project without Grovier and with only `normal` sources, and with `exclude: []` Grovier is kept and still `low`. Both clean up their projects.

### 11.3 How the two were checked in both states

The snapshot's library is the server's real one, which has no `library/restored`, so the plain runs are state A. To see states B (the folder is installed, dossiers not rebuilt) and C (installed and `python -m bti.library dossiers --book grovier_nws` run) I used a throwaway pytest plugin, `-p statec`, working on a temporary copy of the library
(tests/editor: copied; tests/deep: its own clone), with the current restored folder shipped inside the snapshot. The plugin and its data are not part of the change; both files were removed. Results: `tests/editor/test_library_api.py` 15 passed in B and in C; `tests/deep/test_sound.py -m "not timing"` 23 passed in A, B and C.
State C did a real rebuild of 57 dossiers on the server with the PDFs: `{'normal': 37, 'restored': 56, 'low': 1}` (the review now says `usable_after_fixes` for work 2, so 56 works are restored and only 54 stays low; the gate followed the new review without a code change).
Mutations (temporary, undone, files compared byte for byte with the saved copies): making `_work_level` always `normal` (a low source in by default) fails all four tests above; removing `restored_books`/`no_normal_source` from the row fails both library API tests.

### 11.4 The prompts

Only two prompt files of the script step speak of LOW TRUST sources: `prompts/outline.md` (section 5) and `prompts/script.md` ("HOW TO FOLLOW THE OUTLINE"). The step has no other prompt (`rules_voice.md` and `rules_format.md` do not mention sources' trust; `ops.py` builds none; there is no review or fact-check prompt; the storyboard skills do not read the brief).
- `prompts/outline.md`, item 5, now continues: "Sources marked RESTORED (if any) are a reviewed rendering of a machine-translated book: use their ideas and readings of the picture as the author's own, named once and never stated as established fact; take no number, date or quotation from them unless another source confirms it; never guess what a […] mark hides."
- `prompts/script.md` has a new bullet after the LOW TRUST one: "Sources marked RESTORED give the author's ideas and readings, never established facts: say whose they are. Take no number, date or quotation from them unless the fact table also cites another source for it, and never guess what a […] mark hides."

Both agree with the note of the brief (section 4). Tests (`tests/script/test_prompts.py`): `test_every_prompt_that_speaks_of_low_trust_also_gives_the_restored_rule` builds both prompts and checks that the LOW TRUST rule is still there, that the RESTORED rule is there once, and that the words author's, established fact, number, date, quotation, another source, `[…]`, guess
appear both in it and in the brief's note (so the two cannot drift apart); `test_a_restored_source_reaches_the_prompt_with_its_note_and_its_text` checks that a prompt for a project with a restored and an unticked low source carries `[RESTORED: ...]`, the `[RESTORED]` header, the restored text with its `[…]`, the NO FULLY TRUSTED SOURCE paragraph, the `[LOW TRUST:` mark, and not the low text.
No existing assertion about the prompts needed to change.

### 11.5 Test lines of the follow-up

Run through `snapshot_test.sh grovint`, one folder per run (state A: the server's library without `library/restored`). Summary lines exactly as printed:

| Run | Last line |
|---|---|
| `tests/library` | `1 failed, 159 passed, 1 warning in 8.86s` (the failure is the known `test_library.py::test_works_json_shape`, the only one) |
| `tests/script` | `251 passed, 7 skipped in 40.12s` |
| `tests/editor` | `479 passed, 1 warning in 316.54s (0:05:16)` |
| `tests/deep -m "not timing"` | `225 passed, 4 skipped, 1 deselected, 1 warning in 295.65s (0:04:55)` |
| `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` | `ℹ tests 316` `ℹ pass 315` `ℹ fail 0` `ℹ skipped 1` |

Not verified: the rest of `tests/editor` and `tests/deep` in states B and C (only the two changed files were run there; the two files `tests/library/test_dossiers.py` and `tests/library/test_restored.py` are state-independent by construction);
the whole of `tests/script` and `tests/library` in state C; a model reading the new prompt sentences (no model call allowed): what they do to the wording of an outline or narration is untested.
