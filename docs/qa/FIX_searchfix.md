# FIX searchfix: Four faults of the picture search

Brief: `/Users/nhanvu/Documents/code/behind-the-image/.scratch/agy_tasks/searchfix/TASK.md`. Branch `wt/searchfix`, snapshot `searchfix`. Written 2026-11-20.

---

## 1. What was changed

| Piece / File | Functions / Classes | Description |
|---|---|---|
| **Stock photo period filtering**<br>`bti/picks/auto/search.py` | `sources_for(want: dict) -> list[str]` | Pexels and Pixabay are excluded when `want.get("period") == "then"`. For wants with `period: "now"`, Pexels and Pixabay remain available when API keys are configured. |
| **Round one web search for context wants**<br>`bti/picks/auto/search.py` | `search_want(...)` | When the owner's web switch is on, every context want of a line with kind `outside` or `compare` (`bool(kinds & {"outside", "compare"})`) receives one web search with its `search` query in round one, regardless of how many candidates the free sources returned, while budget lasts (`auto_web_search_max`, 80). Other context wants continue to query the web if free sources bring fewer than `ENOUGH` (3) candidates. |
| **Round two web search of thing itself & wider steps**<br>`bti/picks/auto/webround.py` | `search_round_two(...)` | In round two, for wants that answered null or had no candidates: (1) The thing itself queries the web with its first `alt` (its `search` query was executed in round one); (2) Each wider step (step 2 and step 3) receives one web search without requiring candidate count `< ENOUGH`. Budget priority is maintained: round one wants are served first, then round two; a want that could not be searched keeps the code `web_budget`. |
| **Museum object photograph rule**<br>`skills/picks_auto/CHOOSE.template.md` | Section 3 (Rule 11 and Rule 3) | Clarified that a photograph taken in a museum of a real object made in the period (coin, cup, jewel, scales, tapestry, manuscript page) is NOT a modern photograph in the sense of the rule; for a step-3 want it is the right answer. |
| **Short search name rule**<br>`skills/picks_auto/PLAN.template.md` | Section 5 (Rule 6) | Mandated that the short name under which the thing is known (title of work, name of object) comes first and stands alone as `search` when the thing has a name ("Moneylender and his Wife", "Royal Gold Cup", "Codex Behem"); descriptive words go to `alt` and wider steps. |
| **Unit tests**<br>`tests/picks/test_auto_search.py` | `test_outside_or_compare_context_want_searches_web_in_round_one_even_with_three_or_more_free_candidates`, `test_stock_sources_are_not_asked_for_then_want_and_still_are_for_now_want` | Verifies web search triggers in round 1 for `outside`/`compare` despite 4 free candidates; verifies Pexels and Pixabay are omitted for `then` wants and retained for `now` wants. |
| **Web round & budget tests**<br>`tests/picks/test_auto_web.py` | `test_a_want_the_first_session_answered_null_is_searched_on_the_web_and_a_second_session_sees_only_that`, `test_a_want_that_could_not_be_searched_because_the_budget_was_spent_says_web_budget`, `test_the_owners_switch_in_the_settings_turns_it_on_and_the_real_source_works_from_the_real_answer`, `test_the_merge_maps_the_second_sessions_numbers_to_the_wants_own_and_drops_the_budget_wants`, `test_a_new_run_does_not_inherit_the_second_session_of_an_earlier_one` | Updated expectations for round 1 web searching of `outside` lines and round 2 web searching of first `alt`. Verifies budget allocation order (round 1 first, then round 2; exhausted want receives `web_budget`). |
| **Widenet step tests**<br>`tests/picks/test_auto_widenet.py` | `test_round_two_web_search_of_thing_itself_runs_first_with_wider` | Verifies round 2 searches the thing itself with its first `alt` and queries the web for wider steps. |
| **Template verification tests**<br>`tests/picks/test_auto_kinds.py` | `test_the_template_says_the_rules_the_brief_asks_for` | Verifies the presence of the two exact rule sentences and real examples across `CHOOSE.template.md` and `PLAN.template.md`. |

---

## 2. New Count of Web Searches for a 61-Line Plan

For a standard 61-line documentary plan containing 35 context wants (such as project `eligius`):

1. **Round One**:
   - Each of the 35 context wants belonging to lines of kind `outside` or `compare` receives 1 web search of its `search` query.
   - Round One consumption: **35 web searches**.
   - Remaining budget for Round Two: $80 - 35 =$ **45 web searches**.

2. **Round Two**:
   - Only wants that were answered `null` or had no candidates in round one enter round two.
   - For each such want:
     - The thing itself receives 1 web search of its first `alt` (1 search).
     - Step 2 receives 1 web search (1 search).
     - Step 3 receives 1 web search (1 search).
     - Total per want in round two: up to **3 web searches**.
   - In a realistic scenario where 8 to 10 difficult narrative lines require round two (e.g. the 9 hard lines of `eligius`):
     - Round Two consumption: $9 \times 3 =$ **27 web searches**.
     - Total searches across the entire job: $35 + 27 =$ **62 web searches** (well within the default 80 budget cap, leaving 18 spare searches).
   - In the extreme case of widespread misses: up to $45 / 3 = 15$ wants can be fully searched in round two before the 80 budget limit is reached ($35 + 45 = 80$). Any subsequent want that cannot be searched due to budget exhaustion cleanly records code `web_budget`.
   - Contrast with previous behavior: Previously, because free sources almost always returned 3+ irrelevant candidates, web search was bypassed and only executed **7 times out of 80**. Now, all 35 outside/compare wants and all difficult round two lines actively leverage web search within budget.

---

## 3. The Two Template Sentences as Written

### Sentence 1: `skills/picks_auto/CHOOSE.template.md` (Section 3, Rule 11 & Rule 3)
> "A photograph, taken in a museum, of a real object made in the period (a coin, a cup, a jewel, scales, a tapestry, a manuscript page) is NOT a modern photograph in the sense of the rule: for a step-3 want it is the right answer; what stays refused is a photograph of people, places or reconstructions of today, a film still, a stock picture."

### Sentence 2: `skills/picks_auto/PLAN.template.md` (Section 5, Rule 6)
> "The short name under which the thing is known (the title of the work, the name of the object) comes first and stands alone as the `search` when the thing has a name (\"Moneylender and his Wife\", \"Royal Gold Cup\", \"Codex Behem\"); descriptive words go to `alt` and to the wider steps."

---

## 4. Test Summary Lines (Exact Verbatim Output)

### 1. `tests/picks` (Windows Server snapshot `snap-searchfix`):
```
================= 417 passed, 1 warning in 115.48s (0:01:55) ==================
```

### 2. `tests/media` (Windows Server snapshot `snap-searchfix`):
```
============================= 460 passed in 7.88s =============================
```

### 3. `tests/auto` (Windows Server snapshot `snap-searchfix`):
```
================== 236 passed, 1 warning in 84.43s (0:01:24) ==================
```

### 4. CLI Documentation Check (`bti.cli.docgen --check`):
```
tools/deploy/snapshot_py.sh searchfix -m bti.cli.docgen --check
(exited with code 0, no errors)
```

### 5. Frontend & Node Unit Tests (Mac):
```
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs
ℹ tests 495
ℹ suites 0
ℹ pass 494
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
ℹ duration_ms 960.814833
```

---

## 5. What Could Not Be Verified

- **Live Paid Network Calls**: In accordance with standing safety rules (`BTI_NO_REAL_MODELS=1`, no unmetered outside network requests), live paid calls to You.com were not executed. All tests ran against offline fixtures and mock seams.
- **Full Video & TTS Synthesis**: End-to-end documentary video rendering and voice generation were not triggered, adhering to standing server lock rules (`D:\bench\_heavy.lock`).
- **Browser UI Automation**: Editor frontend templates and JavaScript switches were verified via Node unit tests rather than interactive browser drivers.
