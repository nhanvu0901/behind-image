# FIX pictures, worker `websearch`: find the right picture

Brief: `.scratch/agy_tasks/pictures/TASK.md`, section "Worker websearch". Branch `wt/websearch`, snapshot `websearch`. Written 2026-11-20.

## 1. What was built

| piece | files and main functions |
|---|---|
| **Source `wikipedia`** (free, no key) | `bti/media/sources/wikipedia.py`: `WikipediaSource.search(query)` (one MediaWiki call finds the best 3 pages with lead image, file list and a few words; one Commons call gives the data of up to 48 files), `page_pictures(title, lang)` (one named article), `junk_name`, `usable`, `real_open`. Every candidate is a Commons card (`source` "commons", so the download, rendition rule, licence and credit are Commons' own) with four extra fields `page_title`, `site`, `snippet`, `via`. Generic User-Agent, one request a second across calls (own pacing), 429 through `bti.media.http` (short wait once, else a refusal with the wait and a host pause). |
| **Source `web`** (paid, You.com) | `bti/media/sources/web.py`: `WebSource.search` (the client is `YouComClient.search` as it is, key through `bti.script.env.get_key`), `candidates_from(payload, report=)` (best five pages; Wikipedia / Commons / Met pages resolved by the source that knows them; other pages give the lead picture and up to four markdown pictures), `make_id` / `parse_id` (the picture's address and the page's, at most 300 characters), `fetch_image` / `download` (image content type only, not SVG, magic bytes checked, 25 MB, generic User-Agent, time-outs, public addresses only also after a redirect, WebP stored as JPEG), `blocked_hosts` (built-in list + `config/picks.json` `web_blocked_hosts`), `ticket()`. |
| **Registration** | `bti/media/api.py` (`wikipedia`, `web` factories; a card carries `page_title`, `site`, `snippet`, `via`); `bti/picks/service.py` (`web` is an import source; `SEARCH_ONLY = ("wikipedia",)`; `PAID_SOURCES = ("web",)` left out of every default search; `search(..., allow_paid=False)`). |
| **The switch and its budget** | `bti/picks/websettings.py` (`settings`, `for_run`, `save`: code default off / 80, `config/picks.json`, the owner's choice in `run/settings.json` block `picks`, which wins); `bti/settings.py` (`get_picks_block`, `set_picks_block`); route `GET/PUT /api/settings/web-search` in `bti/editor/settings_api.py` (a PUT whose `actor` is not `human` is 403 `spend_needs_human`); page: `static/js/websearchswitch.js`, two marked lines in `settings.js`, `WEBSEARCH_LABELS` at the end of `labels.js`, a block at the end of `errmsg.js`; `config/picks.json` (new, tracked: `suggest: youcom`, `auto_web_search: off`, `auto_web_search_max: 80`, `web_blocked_hosts: []`); cost line of `picks.auto` in `bti/editor/state_api.py` (`cost_about`: `about 20 minutes, up to 80 web searches (You.com)` only while the switch is on; the kind stays `model`). |
| **Round one** | `bti/picks/auto/search.py`: Wikipedia is asked FIRST for every context want (`wiki_queries`: the `entity`, else the `search` words; the plan's words as a second ask only when the first found nothing); then the free sources as before; a want with fewer than three candidates gets ONE web search with its `search` (`web_ask`, `Web` with `on`, `max`, `spent`, `stopped`, `search` seam); candidates ordered Wikipedia, web, others; up to 8 per want when Wikipedia or the web gave some (6 otherwise), spare Wikipedia/web candidates take the place of those whose thumbnail cannot be had; a web picture whose real size is under 600 px on its long side after the thumbnail download is dropped. `default_fetch_thumb` has a web branch (generic client, public addresses, 8 MB). |
| **Round two** | `bti/picks/auto/webround.py` (new): `search_round_two` (every want the first session answered null and every want without a candidate: its `search`, then its first alternative when nothing new came, queries never repeated, budget counted, saved after every want, resumable), `second_search_view`, `merge_choice`, `part_titles`, `web_sentence`, `cost_line`. |
| **The choosing session** | `bti/picks/auto/workspace.py` (`build_choose(..., second=False)`: candidates show `page_title`, `site`, `snippet`, at most 8 per want, `entity` / `period` of the want, `first_look` and no boxes in the second look); `skills/picks_auto/CHOOSE.template.md` (new rules: the period first, a photograph of today when `period: "now"`, a surviving building or object, or nothing else; never a watermarked picture; the reason says what the picture is and from when; a block for the second look). |
| **The job** | `bti/picks/auto/job.py` (see section 3). |
| **Docs** | `docs/AGENT_API.md` (section 7, a sub-section), `docs/APP_GUIDE.md` (a Vietnamese paragraph, and the sentence that said the search "never" calls You.com now says "by default"), `skills/picks/SKILL.md` (one paragraph), `docs/OPS.md` regenerated (the `import` operation's `source` enum has `web`). |
| **Tests** | `tests/media/test_wikipedia.py`, `tests/media/test_web.py` (the REAL sample `tests/media/fixtures/ydc_search_sample.json`), `tests/picks/test_auto_search.py`, `tests/picks/test_auto_workspace.py`, `tests/picks/test_auto_web.py` (new), `tests/editor/test_settings_web_search.py` (new), `tests/editor_frontend/websearchswitch.test.mjs` (4), `tests/picks/auto_fixtures.py` (the `env` fixture: a fake Wikipedia, the switch off, one more trap). Proof script: `tests/e2e/picks_auto/websearch_proof.py`. |

## 2. Decisions where the brief was silent

1. **Where the switch is kept.** The brief says `config/picks.json`; the page route has to write somewhere, and a tracked file edited on the server blocks the next `git pull`. So three layers, the last that says something wins: code (off, 80), `config/picks.json` (a machine's default; the file did not exist before, it now carries `suggest: youcom` so that button behaves as before), the owner's `run/settings.json` block `picks` (git-ignored, kept by a deploy; what the page's switch writes). The route is `/api/settings/web-search`; the actor rule is the one of `PUT .../auto` (`human` only), with the code `spend_needs_human` that already means "an agent never spends".
2. **The one door to the paid search.** `WebSource.search` refuses (`web_off`) outside `web.ticket()`, which only `bti.picks.auto.search.default_web_search` takes; `service.search` leaves `web` out unless `allow_paid`; `GET /api/media/search?source=web` and `POST .../picks/search` with `sources:["web"]` therefore cost nothing. With the switch off the job builds no `Web` at all.
3. **The import id of a web picture.** `<picture address> <page address>`, at most 300 characters (the `import` operation's limit): the page address is shortened (query, then all but the host) before the picture's address is touched; a picture whose own address is longer is not offered. The asset title comes from the picture's file name (else the page's), the credit is `{source: "web", source_url: <page>, author: <site>, licence: "", flag: "unknown"}`.
4. **Wikipedia has its own seam** (`wiki_search`, default `service.search`) so that the existing test that counts the calls of the `search` seam (`test_resume_after_a_cancel_in_the_search`) passes unchanged. A Wikipedia failure never turns a want into `search_failed` (it is an addition); a wait it asks for is kept like any source's.
5. **Candidate caps.** `PER_WANT` stays 6, and is 8 only when Wikipedia or the web gave a candidate (the existing test pins 6); spares (4) are tried only for Wikipedia and web candidates. The Met stays in the lists of `portrait` and `other` as today (existing tests pin it); on the coordinator's word after `linekinds` finished: `object` is searched like `work` (Wikipedia first, Commons, the Met) and `event` like `other` without the Met (Commons, Pexels and Pixabay when their keys are set).
6. **"Nothing new" in round two** is judged after the thumbnails and the 600 px rule, not before. A want that ran out of budget has its null answer taken out of the merged choice, so the write part says `web_budget` instead of `agent_none`.
7. **Six parts only with the switch on** (`plan`, `search`, `choose`, `web`, `choose2`, `write`, titles `(x/6)`); with it off the four parts and their titles are exactly as before. The switch is read when the run starts.
8. **Small pictures**: a web picture under 600 px on its long side after the thumbnail download is dropped (no `small` flag; the existing import rule still flags under 1200 px short side). A Wikipedia picture is offered only at 600 px or more on its long side and not more than 4:1.
9. **Tests must never reach Wikipedia.** `WikipediaSource.real_open` and the web download transport also refuse while pytest runs (`PYTEST_CURRENT_TEST`) unless the proof script sets `BTI_REAL_NETWORK_PROOF=1`: a test of the existing suite takes the A7 switch down (`delenv("BTI_NO_REAL_MODELS")`) for a fake program and would otherwise have reached the real service.
10. **User-Agent.** My new requests send `ImageResearch/1.0 (art documentary research; generic client)`; I also made the You.com client's header generic (it named the project). `bti.media.http.USER_AGENT` (the older sources, thumbnails of Commons files) still names the project: `tests/media/test_http.py:228` pins it, so it is not changed (see section 6).
11. `import` of a `web` candidate takes any PUBLIC http(s) picture address (that is what the candidate is); a private, local or non-http address is refused as `unsafe_url`, a response that is not a JPEG, PNG, WebP or TIFF picture as `not_an_image`. Downloads of thumbnails from a Wikimedia host are paced one a second (`search.pace_wikimedia`): Wikipedia's candidates are many pictures at once, and Wikimedia answered "too many requests" to my proof after about 35 requests (the search part takes a few seconds longer per want, inside its 10 minutes).
12. A new run removes `choice2.json` (`store.reset` knows only the first four files); the picks lists of blocked hosts are my own list (only one real answer exists beside the brief, none of its 8 hosts is a stock agency).

**The contract fields.** `_new_want` (`search.py`) and the rows of `inputs/wants.json` (`build_choose`) copy `entity`, `period` (default `then`), `kinds` (default none) and `places` (default none) from a want, reading each with a default, so a plan without them (today's) behaves as before; the wants of the new plan (`kinds`, `entity`, `period`, `places`) are read the same way. A `map` want that names `places` is searched by the first one (`place_of`: its `place`, else the first of `places`; one map is enough, the storyboard draws its own); it never fails for lack of `place`.

**Limits of the second session.** My second choosing session reads `lim["choose"]` from `_limits(seams)` in `job.py`, which today reads `session.CHOOSE_LIMITS`; after `linekinds` is merged it gets whatever that function gives (their 40 minutes and 220 steps are more than a short second look needs). My code reads no limit from `session.py` by itself.

## 3. What I changed in files the brief marks "do not edit beyond what the second round needs"

Only `bti/picks/auto/job.py`, nothing in `shapes.py`, `write.py`, `doc.py`, `PLAN.template.md`, `bti/auto_run/**`:

- imports `websettings`, `webround`; `EST_SECONDS` has `web` and `choose2`;
- `_Run`: `choice2`, `web_on` / `web_max` / `web_search` (a seam `web={"on","max","search"}`, else `websettings.for_run()`), `web(st)`, `load_choice2()`, and `begin()` removes a stale `choice2.json` on a new run;
- `run_search`: passes `web=` and `wiki_search=`; `shown_of` counts only round-one candidates (so a resumed run does not run the first session again);
- new parts `web` (`run_web`, `web_done`) and `choose2` (`run_choose2`, `choose2_done`), added only with the switch on; the part titles through `webround.part_titles`;
- `run_write`: the merged choice (`webround.merge_choice`) and, with the switch on, `result.web` and the sentence ` Đã tìm trên web 3/80 lần.`; `start()` puts `web` in the job's `meta`; `overview()` answers `web`.

Files outside my list that I touched, each small: `bti/settings.py` (an append-only block marked `websearch`: `get_picks_block`, `set_picks_block`, the same manner as the output switch), `bti/media/youcom.py` (the request header is generic), `docs/OPS.md` (regenerated), and one more because the feature cannot work without it: **`bti/ops/picks_ops.py`**, one key in `SOURCE_VI` (`"web": "trang web"`). The `import` operation's sentence reads `SOURCE_VI[o["source"]]`, so importing the first web picture raised `KeyError: 'web'` in the write part (found by my end-to-end test). It belongs to the `linekinds` worker's area: please keep the line when merging.

## 4. Proof on real data

### 4a. The free Wikipedia source on the eleven wants of the real run (project `eligius`)

Run: `tools/deploy/snapshot_py.sh websearch tests/e2e/picks_auto/websearch_proof.py` (two runs: Wikimedia answered "too many requests" after the fifth want, the script left that want and the ones after it as `limited` as the job does; I waited about ten minutes and ran the other six with `--used=34`). The proof runs the job's own `search_want` with the Wikipedia step only (the other sources are not asked), with the `entity` a new plan would give each want (my guesses, listed below), and builds the contact sheet the choosing session would see, at most 6 candidates (to stay inside the request limit). **Requests: 74 in all (24 API + 50 thumbnails), one a second, generic client, limit 80.** In addition about 4 requests (two test cases, one Wikipedia ask of two requests each) reached the real API by accident in `tests/picks/test_auto_runners.py::test_the_whole_job_runs_through_each_runner` before I added the guard of decision 9: about 78 in all. Nothing was written outside my snapshot. Output: `.scratch/websearch/proof_a_output.txt`, `proof_a_output2.txt`; sheets (opened with the Read tool): `.scratch/websearch/sheets/sheet_<want>.jpg`.

| want | entity given | is the right picture among the candidates on the sheet? | what the sheet shows |
|---|---|---|---|
| b0015.1 Saint Eligius shoeing a horse | Eligius | **No for the scene, yes for the saint.** | 1 is Petrus Christus' goldsmith (Eligius), which here is the project's own main painting (the job drops it); 3 an icon of the saint, 5 a statue "St Eloi", 4 his signature in a charter; 2 is St Peter's dome (an unrelated file the article carries). No picture of him shoeing a horse. |
| b0020.1 Noyon Cathedral | Noyon Cathedral | **Yes** | 1 and 2 are the west front of Noyon Cathedral, 5 a 1914-18 photograph of the ruined cathedral; 3 (St Peter's dome), 4 (a vault at Saint-Denis) and 6 (the town hall) are wrong. The old run offered cathedrals of Quimper, Caen, Rouen, Berlin. |
| b0026.2 gold rider coin of Philip the Good | Philip the Good | **No** | the article of the duke has his portrait (1), a miniature (3) and the arms (5), but no coin. |
| b0028.1 a 15th-century caravel | Caravel | **Yes** | 1, 3 and 6 are replicas and a model of a caravel, 2 a 1924 drawing, 4 a 1572 view of Lisbon full of caravels; 5 is a Byzantine ship fresco (not a caravel). |
| b0029.1 Philip the Good | Philip the Good | **Yes** | 1 is the portrait after Rogier van der Weyden (same sheet as b0026.2). |
| b0035.1 Charles the Bold | Charles the Bold | **Yes** | 1 is Van der Weyden's portrait of Charles the Bold; 3 and 5 are period engravings of his meetings; 2 and 6 are maps. The old run offered other men called Charles and a tree. |
| b0045.1 the Arnolfini Portrait | Arnolfini Portrait | **Yes** | 1 and 6 are the painting itself (3840 x 5253), 3 a detail of the mirror; 2 and 5 are other portraits; 4 is the Arnolfini arts centre in Bristol. |
| b0046.1 medieval falconry | Falconry | **Partly** (a period picture is there) | 3 is a Codex Manesse miniature with a hawk (medieval, German); 1 and 4 are Mughal miniatures, 5 and 6 modern photographs, 2 a falconry centre. |
| b0051.1 Jan van Eyck | Jan van Eyck | **Yes** | 1 is "Portrait of a Man (Self Portrait?)", the red turban; 2 an engraving of Hubert van Eyck, 3 and 5 his paintings, 4 a miniature, 6 a tomb slab. |
| b0055.1 Charles the Bold (second line) | Charles the Bold | **Yes** | the same sheet as b0035.1. |
| b0061.1 Karol Wojtyla | Pope John Paul II | **Yes** | 1 is a photograph of the pope, 5 a 1940s photograph captioned "Baudienst, Kraków, Karol Wojtyła"; 3 is St Peter's dome again (the same unrelated file in three articles). |

So the right picture is among the offered candidates for **9 of the 11 wants** (falconry only as a period miniature of another kind); the old run found it for none. The two misses (the horse-shoeing scene and the coin) are exactly the cases where the thing is a detail of a work or an object that no encyclopedia article pictures: the web search of round one and two (and the Commons search that runs after Wikipedia) are what is left for them, and I could not try the web without a paid call. The `entity` of each want was my guess of what a plan written under the new rules says: with a worse entity the result would be worse (`Philip the Good` for the coin is a person, not the coin).

### 4b. The real You.com answer through the `web` source (no request)

`.scratch/websearch/proof_b.txt` (run offline with a fake client and a stand-in for the Wikipedia source). The answer has 8 pages; the best five are used (the Commons page, the Arnolfini mystery site and Britannica are pages 6 to 8 and are not). Candidates yielded (8):

- page 1 `nationalgallery.org.uk` (4 candidates): the page's markdown has 11 pictures; two thumbnails of 80 x 50 px (IIIF `!80,50`) and an SVG icon are dropped; the four kept are the site's promotional picture "imaginarium" and three pictures of OTHER paintings of the "related works" row (their alt text names them: "Portrait of a Man (Self Portrait?)" ...), which the snippet now shows so that the choosing session can tell;
- page 2 `en.wikipedia.org/wiki/Arnolfini_Portrait`: handed to the Wikipedia source (article "Arnolfini Portrait", language `en`, up to 8 pictures), which is then Commons files with a known licence;
- page 3 `smarthistory.org`: its lead picture `ArnolfiniPortraitThumb.jpg`; page 4 `canon.codart.nl`: `Eyck-Arnolfini-Portrait-657x900.jpg`; page 5 `thecollector.com`: its lead picture `featured-1.jpg`.
- Dropped (14): 1 not a bitmap (`.svg`), 13 addresses that name a small thumbnail (`-300x300.jpg`, `!80,50`). Nothing was dropped for a stock agency in this answer (none of its hosts is one); the unit tests cover blocked hosts, data addresses, GIF, private addresses and over-long ids with synthetic answers.

## 5. The exact switches and calls for a real run (coordinator)

1. A key: `YDC_API_KEY` in the server's environment or `.env` (read by `bti.script.env.get_key`; I never looked at it). The app process must not have `BTI_NO_REAL_MODELS=1`.
2. The switch, as the owner (no `actor`): `PUT /api/settings/web-search` with `{"auto_web_search": "on", "auto_web_search_max": 80}` (or the box in Cài đặt, or `{"picks": {"auto_web_search": "on", "auto_web_search_max": 80}}` in `run/settings.json`; it is read when a run starts, no restart). `GET /api/settings/web-search` says what the next run uses. An agent cannot do it (403, exit 3).
3. The run: `bti status <project>` shows `picks.auto` with `cost: model: about 20 minutes, up to 80 web searches (You.com)`; then `bti do <project> picks.auto --yes-cost --wait` (add `--set redo=true` to choose lines again) or `bti run <project> --yes-cost --wait`. The job has six parts; the closing sentence ends with `Đã tìm trên web N/80 lần.`
4. Afterwards: `projects/<p>/cache/picks_auto/search.json` (`web`, per want `web.queries`, `round2`), `last.json` (`result.web`), `choice2.json`, and `result.missing` / `lines_without` with the code `web_budget` where the budget ran out.
5. With the switch off (the default in code and in `config/picks.json`) nothing paid is called; Wikipedia, which is free, is asked first in every run.

## 6. Needs another worker

- **`linekinds`**: (a) keep `"web": "trang web"` in `SOURCE_VI` of `bti/ops/picks_ops.py` (section 3); (b) regenerate `docs/OPS.md` after merging (`python -m bti.ops.doc`; I regenerated it for the new enum value and you will too); (c) nothing more for the plan fields: `wants_of` now gives `kinds`, `entity`, `period`, `places` and my code reads them (section 2); (d) `write.py` already carries my `web_budget` through `resolve_picks` (the want has no entry in the merged choice, so its code is the search state's); put it into the `missing` list as any other code; (e) optional: `tests/picks/auto_helpers.py` `install_sources` could install a fake `wikipedia` source like my `env` fixture does (the tests that do not use that fixture rely on the pytest guard of decision 9 instead).
- **`bti/picks/auto/texts.py`** (nobody's file in the brief): `why("web_budget")` and `why("web_no_key")` have no sentence, so the line shows the generic "Chưa có hình cho ...". Suggested: `web_budget` "Đã hết lượt tìm trên web của lần chạy này nên chưa tìm lại được %s." `PART_TITLES` is untouched: the six titles with `(x/6)` are in `webround.PART_TITLES_WEB`.
- **page** (`views/picks_logic.js`, not mine): `result.web` = `{on, max, searches, stopped}` could appear in the second line of a result (`autoDetailText`); today the count is in the closing sentence only.
- **storyboard worker / export**: a web picture has `credit.source == "web"`, `flag: "unknown"`, `credit.source_url` = the page, `credit.author` = the site's name; the video's description lists credits from `source_url` (`bti/export/describe.py`), so these pages will appear there.
- **coordinator**: `bti.media.http.USER_AGENT` (used by the Commons, Met, Pexels, Pixabay and OSM sources and by the thumbnails of Commons files) still carries the project's name; a test pins it. Decide whether to change both.

## 7. What I could not verify

- Nothing paid ran: the real shape of an answer is the one sample; the real download of an arbitrary web picture (DNS check, redirects, content types in the wild) was tested only with fake transports and static checks.
- The choosing sessions are fake agents: the new template rules were read, not run with a model; the second look was tested for what it is given and what is written, not for how a model answers it.
- The switch in the settings dialog was checked with `node --check` and the unit tests, not in a browser.
- The proof used the Wikipedia part only (not the Commons or Met search that run after it, not the web), with 6 candidates a sheet (the job shows up to 8).
- Wikimedia answered "too many requests" once, after about 35 requests in 70 seconds; I did not see the `Retry-After` it gave (the job's handling, a `limited` want with the wait, worked as designed).

## 8. Test results (snapshot `websearch`, server, `BTI_NO_REAL_MODELS=1`)

One folder per run, never `-m slow`; summary lines exactly as printed. `tests/auto`, `tests/draft`, `tests/ops`, `tests/state`, `tests/cli` and `tests/editor` ran on the snapshot taken before my last three small edits (the contract fields, the pacing of Wikimedia thumbnails, one line of the choose template), which touch only `bti/picks/auto/search.py`, `workspace.py` and the template; `tests/picks` and `tests/media` ran again after them, and so did `tests/editor/test_settings_web_search.py` with `tests/ops/test_registry.py`.

| run | summary line |
|---|---|
| `tests/picks` (final) | `271 passed, 1 warning in 74.96s (0:01:14)` |
| `tests/media` (final) | `395 passed in 5.32s` |
| `tests/auto` | `207 passed, 1 warning in 77.50s (0:01:17)` |
| `tests/draft` | `438 passed, 1 warning in 202.15s (0:03:22)` |
| `tests/ops` | `473 passed, 1 warning in 118.37s (0:01:58)` |
| `tests/state` | `295 passed, 1 warning in 183.93s (0:03:03)` |
| `tests/cli` | `127 passed, 1 warning in 41.75s` |
| `tests/editor` | `508 passed, 1 warning in 274.26s (0:04:34)` |
| `tests/editor/test_settings_web_search.py` + `tests/ops/test_registry.py` (final) | `104 passed, 1 warning in 7.48s` |
| `python -m bti.cli.docgen --check` | exit 0 |
| `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs` (Mac) | `tests 464`, `pass 463`, `fail 0`, `skipped 1` (the skip was there before) |
| `node --check` of `labels.js`, `errmsg.js`, `settings.js`, `websearchswitch.js` | all ok |

New tests: `tests/media/test_wikipedia.py` and `tests/media/test_web.py` (the real sample through a fake client), `tests/picks/test_auto_search.py` (+17), `test_auto_workspace.py` (+4), `tests/picks/test_auto_web.py` (new, the job with the switch on and off, round two, budget, resume, merge), `tests/editor/test_settings_web_search.py`, `tests/editor_frontend/websearchswitch.test.mjs`. The `env` fixture of `tests/picks/auto_fixtures.py` keeps the trap of the paid service (`YouComClient.__init__` and now `.search`); with the switch off every test proves nothing paid was called.

