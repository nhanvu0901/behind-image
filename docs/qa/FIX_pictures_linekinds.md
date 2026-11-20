# Pictures: the plan says what each line does, and nothing gets lost (worker linekinds)

Brief: `.scratch/agy_tasks/pictures/TASK.md` (section "Worker linekinds" and the "Contract"). Branch `wt/linekinds`. No model, no paid request, no real request left a test; the proof of
section 4 reads copies of the saved files of the first test video (project `eligius`) and writes nothing on the server outside the snapshot.

## 1. What was built

| Brief point | Where | Main functions |
|---|---|---|
| 1. `kinds` required on every plan line, its checks, cap 30 -> 60, session limits | `bti/picks/auto/shapes.py`, `bti/picks/auto/job.py` | `kinds_problem`, `kind_problems` (one sentence and one code per rule), `_fallback`, `_item` (context `entity`/`period`, kinds `object`/`event`, map `places`), `check_plan`, `KIND_TABLE`, `MAX_WANTS = 60`; `PLAN_LIMITS` / `CHOOSE_LIMITS` of `job.py` |
| 2. The rewritten template | `skills/picks_auto/PLAN.template.md` | new first rule of section 5 ("Say what each line does") with the table and the nine worked examples, rules 2, 4, 6, 7 rewritten, section 4 (format) and the check paragraph updated |
| 3. Writing the picks | `bti/picks/auto/write.py`, `bti/ops/picks_ops.py`, `bti/picks/doc.py`, `bti/picks/service.py` | `build_lines` (the fallback, `kinds`, `missing`), `_ops_for`, `set_picks` / `skip_beat` take `kinds` and `missing` (`_keep_what_is_known`), `normalize` / `doc_problem` keep them, `put` keeps them for a beat that does not send them |
| 4. The warning and the gate | `bti/picks/doc.py`, `bti/picks/service.py`, `bti/auto_run/checks.py`, `loop.py`, `reasons.py`, `bti/editor/hints.py` | `issues` (`outside_no_picture`), `outside_without_picture`, `outside_summary`, `payload` (`outside`), `OUTSIDE_NO_PICTURE_LIMIT = 0.34`, `SHARE_OF`, `share_base`, `judge(.., outside)`, `_outside_of`, the sentence of the run |
| 5. The storyboard's input | `bti/draft/inputs.py`, `bti/draft/workspace.py` | `beat_kinds`, `beat_missing`, `_beats_doc` (`kinds` and `missing` per beat, `[]` when there are none) |
| 6. Tests, docs | `tests/picks`, `tests/auto`, `tests/ops`, `tests/draft`, `docs/AGENT_API.md`, `docs/OPS.md` (generated), `skills/picks/SKILL.md`, `labels.js` (own block at the end) | see section 5 |

### The rules of the check (`bti.picks.auto.shapes.kind_problems`), one code each

| code | refuses |
|---|---|
| `kinds_missing` | lines without `kinds`, in ONE sentence listing the first 20 lines and "and N more" |
| `kinds_shape`, `kinds_unknown`, `kinds_too_many`, `kinds_repeated` | not a list / empty, a word outside the eleven, more than two, the same word twice |
| `outside_only_painting` | `outside` with no `context` or `clip` item (says what it shows: only the painting, only a map, nothing new) |
| `outside_no_fallback`, `fallback_bad` | `outside` without a line-level `fallback`; a fallback that is not `{"type":"whole"}` or a detail of a known region |
| `map_without_journey` | a map on a line whose kinds lack `journey` (says: "born at Limoges" wants a view of the place) |
| `journey_no_map`, `journey_one_place` | `journey` without a map, or a map with fewer than two places |
| `compare_no_work`, `compare_no_painting` | `compare` without a `context` of kind `work`, or without a `detail`/`whole` of this painting |
| `kind_needs_painting` | `detail`, `whole`, `dates`, `inscription`, `construction`, `idea`, `relations` whose pictures are not the ones of the table (a non-empty `show` only) |
| `figure_no_picture` | `figure` with no `context`/`clip` and no `detail` |
| `context_without_kind` | a `context` or `clip` item on a line whose kinds hold none of `outside`, `compare`, `figure`, `relations` |

Every sentence names the place (`lines[7] (b0008).show[1]`), ends with its code in brackets and says exactly what to add (the JSON of the item). All the errors of a plan are given in one round. After the
clip rule has cut a clip, the lines it changed are checked again (a line whose only picture was a second clip of the chapter is refused, with the note of the cut beside it).

## 2. Decisions where the brief was silent

1. **`fallback` is one item** (`whole`, or `detail` of a declared or existing region); a list of one item is read as the item. It is allowed on any line, required on `outside`. It is not one of the three
   pictures of `show`, and a region used only by a fallback is made (it counts as used).
2. **`"show": []` stays allowed**, but only for the kinds that point at the painting (`detail`, `whole`, `dates`, `inscription`, `construction`, `relations`, `idea`): the picture before stays. `outside`, `compare`,
   `journey` and `figure` always ask for a picture.
3. **A picture from elsewhere needs a kind that says so** (`context_without_kind`): otherwise the line escapes the fallback and the gate.
4. **`figure`**: a `context`/`clip` item or a `detail`. A figure about something outside the painting is `["outside", "figure"]` (b0028 in the template), so that it has a fallback and counts for the gate.
5. **Maps keep `place`.** A normalised map item carries `places` (all) AND `place` (the first), because `search.py` (not mine) still reads `want["place"]`; an old plan's single `place` is read as one place.
6. **The writer uses the fallback only when the line ends with no item at all** (nothing found, nothing painted). A line that keeps a `detail` of the painting or one found picture is written with those and `missing`;
   the warning `outside_no_picture` still fires for an `outside`/`compare` line whose items are all of the main painting. A line of a plan saved before `kinds` (no fallback) with nothing found is left as it was and listed in `lines_without`, as before.
7. **`missing` is `[{what, code}]` and nothing else** (at most 10, `code` lower-case words); the writer always sends it (`[]` clears the entry of an earlier run), `kinds` only when the plan has them.
   An edit of the pictures (`set_picks`, `add_pick`, `remove_pick`, `skip_beat`, the page's `PUT`) keeps both unless it sends new ones; `[]` takes them away; undo restores them (the whole beat is the unit of undo).
8. **The summary `outside`** counts the beats whose kinds hold `outside` or `compare`, without those settled with `skip` (the owner or the agent chose the painting on purpose: no warning, not counted). `with_picture = lines - len(without)`.
   A beat with such kinds and no item and status `todo` counts as without (it also raises `beat_no_pick`).
9. **The share of the gate is of the outside lines**, with the number from `outside.lines` of `GET .../picks` (not from the narration); an answer without the number stops the run, the safe side (as for `beat_no_pick`).
   The tolerated entry is `{gate, code, count, lines}` with `lines` = the outside lines; the end of the run adds one Vietnamese sentence and the result gets `lines_outside_without_picture`.
10. **Limits** (`job.py`, `PLAN_LIMITS`, `CHOOSE_LIMITS`): plan 30 min / 120 steps (was 20 / 80), choosing 40 min / 220 steps (was 20 / 80). The real 61-line run took 36 steps / 210 s for the plan and 51 steps / 120 s for 21 pictures and 20 boxes (a little more
    than one step per sheet or crop); the new cap is 60 pictures and 20 boxes, and websearch's second choosing session follows. `session.PLAN_LIMITS` / `CHOOSE_LIMITS` are untouched (not mine; tests of the other worker read them for the `**80 steps**` of the briefing),
    so the briefing of a real run shows the job's 120 steps and 30 minutes.
11. **Two edits outside the list**: `bti/picks/service.py` (one key `outside` in `payload`, the merge of `kinds`/`missing` in `put`), because the document's answer and the page's save live there; the hunks are far from the source lists websearch edits.
12. **`PLAN.template.md` keeps the old key phrases** that `tests/picks/test_auto_workspace.py` (websearch's file) asserts ("A line about something outside the painting shows something other than the main painting", "A map only when the line is about *where*", "Nothing invented"), and
    contains no `{{` or `}}` except the placeholders (that test refuses them).
13. `inputs/beats.json`: `kinds` and `missing` are always present (`[]` for a beat of a document made before), so the storyboard reads one shape.
14. `labels.js`: the sentence of the new warning for the list "Cảnh báo" (`PICKS_LABELS.issue.outside_no_picture`) and for the simple page (`PICKS_PAGE_LABELS.issue.outsideNoPicture`); `errmsg.js` needed nothing (no new error code).

## 3. Settings and calls for a real run (the coordinator)

- No new setting. The agent is the project's `picks` role (Opus 5.5 High on `eligius`). The picks of `eligius` are approved and every line has pictures, so: `bti do eligius picks.auto --yes-cost --wait --set redo=true`
  (the approval is dropped when it writes), or the whole run `bti run eligius --yes-cost --wait` when the owner allowed it. Lines can be named: `--set beats='["b0007","b0008"]'`.
- Limits of the sessions: plan 30 min / 120 steps, choosing 40 min / 220 steps (`GET .../picks/auto` says them in `limits`).
- At the gate the automatic run stops when more than 34% of the lines about something outside the painting still show only the main painting (`outside_no_picture`, listed in the stop), and goes on and says how many otherwise (also more than a quarter of all
  lines without a picture still stops it, as before).
- Afterwards: `GET /api/projects/eligius/picks` (`outside: {lines, with_picture, without}`, the warnings), `GET .../picks/auto` (`last.result.missing`, `outside_without`).

## 4. Proof on real data (read-only)

Copies of `projects\eligius\cache\picks_auto\plan.json`, `search.json`, `choice.json`, `last.json` and `projects\eligius\script\narration.json` (the brief says `projects\eligius\narration.json`, which does not exist: the file is in `script\`) were put in
`D:\code\behind-the-image\run\snap-linekinds\scratch\real\` and `.scratch/linekinds/proof_kinds.py` ran in the snapshot (`snapshot_py.sh`). The full output is `.scratch/linekinds/proof_output.txt` in the worktree.

### 4.1 The old plan as it is (61 lines, no `kinds`): what the model reads

The check refuses it, with ONE sentence (not 61) that lists the first 20 lines and says how many more, names the eleven words, and shows what to write. Printed output:

```text
ERROR 61 line(s) have no `kinds`: b0001, b0002, b0003, b0004, b0005, b0006, b0007, b0008, b0009, b0010, b0011, b0012, b0013, b0014, b0015, b0016, b0017, b0018, b0019, b0020 and 41 more. Every line says what it does with one or two words of: detail, whole, outside, compare, journey, dates, figure, inscription, construction, relations, idea (see the table in TASK.md); for example `"kinds": ["detail"]`, and a line about something outside the painting `"kinds": ["outside"]` with a `context` picture and a `fallback` [kinds_missing]
1 error(s), 0 note(s), 0 warning(s)

-- old plan: 1 error(s) on 0 line(s); by rule: {}
```

Is it clear? Yes: it says which lines, what is missing, which words are allowed, and gives an example for the two common cases. Printing 61 identical sentences was the alternative; the single sentence is shorter and the model repairs all lines at once.

### 4.2 The same plan with the hand-made `kinds` (items kept as they were, no fallback)

57 error(s), 0 note(s), 0 warning(s)

By rule: `outside_no_fallback` 31, `outside_only_painting` 17, `journey_one_place` 3, `kind_needs_painting` 3, `map_without_journey` 2, `context_without_kind` 1. Printed sentences, one of each rule (the whole output, 57 sentences, is in `.scratch/linekinds/proof_output.txt`):

```text
ERROR lines[6] (b0007): kinds says "outside", so the line must ask for a picture of the thing itself, but it shows only the painting. Add {"type": "context", "search": "<the thing and what sort of picture>", "entity": "<its name>", "period": "then", "kind": "<portrait|place|object|event|work|document|photo>", "what": "<Vietnamese>"} to `show` (or a clip of the thing); if the line is really about something in the painting, change kinds to "detail" or "whole" [outside_only_painting]
ERROR lines[6] (b0007): an "outside" line needs a line-level `fallback`, the picture of the painting that is shown when nothing is found for the line. Add "fallback": {"type": "whole"} (or {"type": "detail", "region": "<NAME>"} for the part of the painting nearest to what the line says) [outside_no_fallback]
ERROR lines[7] (b0008).show[1]: the map of a "journey" needs two or more names in `places` and this one has 1 (Lübeck, Germany). Give the places the line moves between or ties together, each with its country ("Lübeck, Germany", "Bruges, Belgium"); one place is not a journey [journey_one_place]
ERROR lines[10] (b0011).show[1]: a map belongs only to a line about a journey or a tie between two or more places, and kinds says 'detail', 'outside', not "journey". For a place that is merely mentioned ("born at Limoges", "Bruges was the commercial capital") ask for a view of the place instead: {"type": "context", "search": "<the thing and what sort of picture>", "entity": "<its name>", "period": "then", "kind": "<place>", "what": "<Vietnamese>"} with kinds "outside". If the line does move between places, put "journey" in kinds and give the map two or more `places` [map_without_journey]
ERROR lines[32] (b0033): kinds says "detail" (the line points at a thing that is in the painting) but its pictures do not match: add {"type": "detail", "region": "<NAME>"} (declare its box in `regions`) to `show`, or change kinds to what the line really does [kind_needs_painting]
ERROR lines[48] (b0049): the line asks for a picture from elsewhere (a context picture) but kinds says 'dates'. Put "outside" in kinds (and name a `fallback`), or "compare" when it is another work set beside this one, or take the picture out of `show` [context_without_kind]
```

Refusals per line (the second column is after a `fallback` of `whole` was added to every `outside` line, section 4.3):

| line | refused for | still refused with a fallback |
|---|---|---|
| b0007 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0008 | outside_only_painting, outside_no_fallback, journey_one_place | outside_only_painting, journey_one_place |
| b0011 | outside_only_painting, outside_no_fallback, map_without_journey | outside_only_painting, map_without_journey |
| b0012 | outside_no_fallback | (nothing) |
| b0013 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0014 | outside_only_painting, outside_no_fallback, journey_one_place | outside_only_painting, journey_one_place |
| b0015 | outside_no_fallback | (nothing) |
| b0016 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0017 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0018 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0020 | outside_no_fallback | (nothing) |
| b0021 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0026 | outside_no_fallback | (nothing) |
| b0027 | outside_only_painting, outside_no_fallback, map_without_journey | outside_only_painting, map_without_journey |
| b0028 | outside_no_fallback | (nothing) |
| b0029 | outside_no_fallback | (nothing) |
| b0030 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0031 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0033 | outside_no_fallback, kind_needs_painting | kind_needs_painting |
| b0035 | outside_no_fallback | (nothing) |
| b0036 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0039 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0042 | outside_no_fallback | (nothing) |
| b0046 | outside_no_fallback | (nothing) |
| b0049 | kind_needs_painting, context_without_kind | kind_needs_painting, context_without_kind |
| b0051 | outside_no_fallback, kind_needs_painting | kind_needs_painting |
| b0054 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0055 | outside_no_fallback | (nothing) |
| b0056 | outside_only_painting, outside_no_fallback | outside_only_painting |
| b0057 | outside_only_painting, outside_no_fallback, journey_one_place | outside_only_painting, journey_one_place |
| b0058 | outside_no_fallback | (nothing) |
| b0061 | outside_no_fallback | (nothing) |

### 4.3 Reading it

- 26 error(s), 0 note(s), 0 warning(s) These 20 lines are the ones the old plan served badly: 17 lines that are about something outside the painting and that the old plan left on the painting or on a map (b0007 b0008 b0011 b0013 b0014 b0016 b0017 b0018 b0021 b0027 b0030 b0031 b0036 b0039 b0054 b0056 b0057), plus b0033 and b0051 (a picture from elsewhere where the line also points at the painting or states a reading), b0049 (a dates line that showed a work of another painter).
- The 5 maps of the old plan: 3 were on a line that moves between places but named ONE place (`journey_one_place`: b0008, b0014, b0057), 2 were maps of a place merely mentioned (`map_without_journey`: b0011 "born at Limoges", b0027 "Bruges was the commercial capital"): exactly the owner's complaint.
- 14 of the 31 outside lines already asked for a picture from elsewhere (they need only a fallback), 17 did not. The old plan asked 16 contexts and 5 maps; the new rule asks for a picture on all 31 outside lines and on the one `compare`.
- b0045 (`compare`: Arnolfini Portrait beside the mirror) passes as it was.

### 4.4 The hand-made `kinds` of the 61 lines

Written by reading the narration of each line (second column: what the old plan showed):

```text
b0001  detail                old plan: detail:SCALES + detail:COUPLE  Look first at the goldsmith's hands. He holds a small pair of scales, 
b0002  detail                old plan: detail:SAINT_FACE             But now look at his eyes. They are not on the scales at all. They have
b0003  whole, detail         old plan: whole + detail:MIRROR         The room is a narrow workshop with three figures in it. In a round mir
b0004  detail                old plan: detail:SAINT                  This man is no ordinary craftsman. He is Saint Eligius, patron saint o
b0005  idea                  old plan: whole                         The panel is usually taken as a devotional picture that also served as
b0006  detail                old plan: detail:COUNTER                Why can we see into this shop at all? Look at the counter along the fr
b0007  outside               old plan: whole                         These rules came from the guilds of 14th-century Netherlandish towns, 
b0008  outside, journey      old plan: detail:SCALES + map           Behind all this lay a fear of fraud. Countries used different units of
b0009  idea                  old plan: detail:SCALES                 So it is probably no accident that the saint is shown weighing. Of all
b0010  detail                old plan: detail:WEIGHT_BOX + detail:SAINT_FACE  Now look at the round box on the counter, its lid lying open. The weig
b0011  detail, outside       old plan: detail:SAINT + map            Look again at the man behind the counter, at his citizen's clothes and
b0012  outside               old plan: ctx[portrait]                 He became personal adviser to the Merovingian King Dagobert. A French 
b0013  outside               old plan: detail:COINS                  Legend has it the court gave him gold and jewels for one throne, and h
b0014  outside, journey      old plan: map                           Dagobert made him Bishop of Noyon, a diocese that included Bruges, whe
b0015  outside               old plan: ctx[work]                     Some say he began as a goldsmith's apprentice, others as a blacksmith.
b0016  outside               old plan: detail:SCALES                 He became patron of blacksmiths, goldsmiths and money changers, who sh
b0017  outside, detail       old plan: detail:SAINT + detail:COUPLE  Every guild had a patron saint, and a wealthy one had its own chapel. 
b0018  outside               old plan: whole                         In 1449, the year of this panel, the Chapel of Smiths was dedicated in
b0019  detail                old plan: detail:SCALES                 Look back at the scales. The ring in the pan is small, but it has been
b0020  outside               old plan: ctx[place]                    The first reading starts with an old legend. A ring said to have been 
b0021  outside               old plan: detail:SCALES                 In the story, rich suitors wanted to marry Godeberta, and the king had
b0022  idea                  old plan: detail:SAINT_FACE             So one reading sees the saint as a man who turns a girl away from worl
b0023  detail                old plan: detail:GIRDLE + detail:SHELF_BEADS  That second reading has objects on its side. A traditional wedding gir
b0024  detail                old plan: detail:WOMAN + detail:MAN_CHAIN  Now look at the couple themselves. She wears gold brocade with a pomeg
b0025  detail, idea          old plan: detail:COUPLE                 Only the Burgundian court or the richest burghers could dress like thi
b0026  detail, outside       old plan: detail:COINS + ctx[photo]     Now look at the coins lying on the counter beside the scales. There ar
b0027  outside               old plan: map                           So how did so much foreign gold reach one counter? Bruges, then part o
b0028  outside, figure       old plan: ctx[other]                    On one day in 1457 its harbour held 42 British caravels and three Vene
b0029  outside               old plan: ctx[portrait] + detail:PITCHERS  But the jewellers' best customer was the duke himself. Even his toothp
b0030  outside, figure       old plan: detail:PITCHERS               One salt cellar decorated with sirens was valued at about 900 ducats, 
b0031  outside, detail       old plan: detail:SHELVES + detail:MAN_CHAIN  The dukes travelled constantly with their treasure, and often paid for
b0032  detail                old plan: detail:TONGUES                Look at the wall behind the saint. Small dark shapes like little trowe
b0033  detail, outside       old plan: ctx[photo]                    They are probably adder's tongues, fossilized shark teeth believed to 
b0034  detail                old plan: detail:COCONUT                Half hidden behind a curtain stands a goblet of coconut shell, a fruit
b0035  outside               old plan: ctx[portrait]                 Princes feared poison with good reason. Philip the Good's father and u
b0036  outside               old plan: detail:SHELVES                Rulers kept food tasters, and only ruling princes enjoyed the privileg
b0037  detail                old plan: detail:CORAL_VESSEL           Most things here were meant to protect as well as adorn. Branching cor
b0038  detail                old plan: detail:SHELF_BEADS + detail:CORAL_VESSEL  There is a rosary of coral and amber. The gold and glass vessel by the
b0039  outside, idea         old plan: detail:SHELVES                In the early Middle Ages goldsmiths worked only for church and rulers.
b0040  detail                old plan: detail:MIRROR                 Now move your eye past the coins to the small round mirror. Its curved
b0041  detail, whole         old plan: detail:MIRROR_MEN + whole     They stand about where you stand now. So we see the shop from inside a
b0042  outside               old plan: ctx[photo]                    Mirrors like this were common in Netherlandish homes, where one hung o
b0043  construction          old plan: detail:SHELVES                Look at the shelves behind the saint. Their angles suggest the painter
b0044  detail                old plan: detail:MIRROR_MEN             In the mirror, one of the two men holds a falcon. His head tilts in a 
b0045  compare               old plan: ctx[work] + detail:MIRROR_MEN  Jan van Eyck painted such a mirror in his Arnolfini portrait, and it i
b0046  outside               old plan: ctx[work]                     Falconry was a favourite pastime of the Burgundian court, with falcons
b0047  detail, inscription   old plan: detail:MIRROR + detail:INSCRIPTION  The falconer's face stays uncertain, but the painter's name is easier 
b0048  inscription           old plan: detail:INSCRIPTION            Drop your eye to the bottom edge of the panel, where a line of Latin r
b0049  dates                 old plan: ctx[work]                     He was born at Baerle, probably in 1415. He became a citizen of Bruges
b0050  detail                old plan: detail:HEART_SIGN             Beside the signature sits a small heart-shaped sign. It may be a maste
b0051  idea, outside         old plan: ctx[portrait]                 So his training has been read in two ways. Some historians think he wa
b0052  idea                  old plan: detail:CORAL_VESSEL           The second reading would explain his bond with Eligius, and how exactl
b0053  detail                old plan: detail:SHELVES                Look again at the shelf of silver pitchers, chains and brooches. Many 
b0054  outside               old plan: detail:PITCHERS               After serving as payment, they were taken apart or recast. One goldsmi
b0055  outside               old plan: ctx[portrait] + detail:SHELF_BEADS  In 1476 Charles the Bold, the last duke, was defeated in Switzerland. 
b0056  outside               old plan: detail:COUNTER                The guilds that kept this shop front open had helped Bruges rise. Then
b0057  outside, journey      old plan: detail:MIRROR + map           By 1494 trade in Bruges had stopped, and 4000 to 5000 houses stood emp
b0058  outside, whole        old plan: ctx[place] + whole            The panel may have followed the money. A 19th-century German collector
b0059  detail                old plan: detail:SCALES + detail:SAINT_FACE  Come back, then, to the hands and the scales. The ring still sits in t
b0060  idea                  old plan: whole                         So, a prayer or a shop sign? As far as the evidence goes, it is both. 
b0061  outside, detail       old plan: ctx[portrait] + detail:SCALES + whole  In a play published in 1960 by Karol Wojtyla, later Pope John Paul II,
```

```text
kinds count (a line with two words counts for both): {'compare': 1, 'construction': 1, 'dates': 1, 'detail': 27, 'figure': 2, 'idea': 8, 'inscription': 2, 'journey': 3, 'outside': 31, 'whole': 3}
lines whose kinds hold `outside`: 31; `compare`: 1; together 32 of 61
their narration: about 392 s of 720 s (54%)
what the old plan asked from elsewhere on these lines: context 16, map 5, on lines whose kinds hold outside: 14 of 31
outside lines the old plan left on the painting or on a map: 17: b0007 b0008 b0011 b0013 b0014 b0016 b0017 b0018 b0021 b0027 b0030 b0031 b0036 b0039 b0054 b0056 b0057
```

The coordinator's count was 30 outside lines and 386 s; this list has **31 lines whose kinds hold `outside`** (b0007, b0008, b0011 to b0018, b0020, b0021, b0026 to b0031, b0033, b0035, b0036, b0039, b0042, b0046, b0051, b0054 to b0058, b0061) plus one `compare` (b0045): 392 s of 720 s.
Lines I counted that you may not: b0011 (born at Limoges, with the painting first), b0017 (every guild had a patron saint and a chapel), b0026 (the real coins, after the coins on the counter), b0033 (fossil shark teeth), b0051 (Jan van Eyck as master), b0058 (the museum and the collector), b0061 (Karol Wojtyla).
Doubtful calls, all marked `outside` with something of the painting beside it: b0014 and b0057 are `["outside", "journey"]` (a diocese tying Noyon and Bruges; merchants moving to Antwerp); b0058 is `["outside", "whole"]`; b0009 is `idea`, not `detail`.


## 5. Tests

New or changed tests (Python, on the server snapshot `snap-linekinds`; one folder per run, no `-m slow`):

- `tests/picks/test_auto_kinds.py` (new): the eleven words and the table (the template's table is the check's table, word for word), every kind accepted with the pictures its row asks for, `show: []`, every rule and every code one by one (`CODES_OF_KINDS` is exactly
  the set the tests produce), the single sentence for a plan without `kinds`, fallbacks, the clip rule followed by the kinds check, maps (`places`, the old `place`), compare, figure, context without kind, entity and period, what the wants carry, and the template itself:
  each worked example of the template (b0006, b0007, b0008, b0022, b0028, b0043, b0045, b0048, b0049) is parsed out of the file and passes the check, the JSON example is a valid plan, and the rules the brief asks for are there.
- `tests/picks/test_auto_shapes.py`, `auto_helpers.py` (`PLAN` with `kinds`, `fallback`, `entity`, `places`; `infer_kinds`, used by `FakeAgent.fit` for a prepared plan that leaves `kinds` out), `test_auto_job.py` (the fallback written when nothing is found, with `agent_none`, `no_candidates`,
  `no_thumbs`, `source_limited`; `kinds` on every line, skip lines included; a found picture leaves no `missing`; an older plan: nothing written, no kinds; the limits), `test_auto_api.py`, `test_doc.py` (normalise, revision of an old document unchanged, `doc_problem`, the warning, the summary, skip and unknown lines).
- `tests/ops/test_picks_ops.py`: `kinds`/`missing` written, kept by every later edit and by the page's `PUT`, `[]` takes them away, every wrong field with its path, the schema, undo.
- `tests/auto/test_run_joined.py`: the 34% share of the outside lines (7 passing and 7 stopping sizes, with the list in the stop), the two shares judged apart, unknown number stops, the run log and the sentence, the lists and the documents.
- `tests/draft/test_workspace.py`: `inputs/beats.json` carries `kinds` and `missing` and nothing else changes.

Summary lines exactly as printed (the last run of each folder on the final code; docs checks after the last edit of a document):

```text
tests/picks   319 passed, 1 warning in 70.02s (0:01:10)
tests/auto    225 passed, 1 warning in 74.83s (0:01:14)
tests/draft   439 passed, 1 warning in 178.35s (0:02:58)
tests/ops     488 passed, 1 warning in 130.65s (0:02:10)
tests/media   363 passed in 6.27s
tests/editor  491 passed, 1 warning in 246.32s (0:04:06)
tests/state   295 passed, 1 warning in 187.98s (0:03:07)
tests/cli     127 passed, 1 warning in 46.15s
python -m bti.cli.docgen --check        exit 0
python -m bti.editor.hints --check      exit 0
python -m bti.ops.doc --check           exit 0
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs
    tests 460, pass 459, fail 0, skipped 1
node --check bti/editor/static/js/labels.js    ok
```

Failures met on the way, all mine and fixed: `tests/picks/test_auto_workspace.py` (websearch's file) refuses `}}` and wants three old phrases of the template (kept, see decision 12); `tests/cli/test_cli_docs.py` wanted `with_picture` as a word of its own in `docs/AGENT_API.md`.
`docs/AGENT_API.md` and `docs/OPS.md` were regenerated in the snapshot (`bti.editor.hints`, `bti.ops.doc`) and copied back; the generator writes CRLF on Windows, so the copy was normalised to LF (the diff of `AGENT_API.md` is only the hand-written text and the table row).


## 6. Needs another worker

- **websearch** (`search.py`, `workspace.py`): (a) `_new_want` of `search.py` and the rows of `inputs/wants.json` in `build_choose` must copy `entity`, `period`, `kinds` (and `places` of a map) from the want: `shapes.wants_of` gives them, the two files drop them today;
  (b) `SOURCES_BY_KIND` has no `object` or `event` (they fall back to `other`: Commons, the Met, Pexels, Pixabay); the Met only for `work`, `document`, `object` is their rule; (c) a map want has `place` (the first of `places`) and `places`; the OSM search reads `place` only, so the map of a `journey` shows the first place unless they use `places`;
  (d) the codes of `missing` they add (`web_budget`) are accepted as they are (lower-case words with `_`); `texts.why` falls back to a generic sentence for a code it does not know; (e) the second choosing session runs under `job.CHOOSE_LIMITS` (40 min / 220 steps) unless they pass their own.
- **picks page** (`bti/editor/static/js/views/picks_rows_logic.js`, not on my list): the simple page's `issueSentence` needs `case 'outside_no_picture': return W.issue.outsideNoPicture(line);` (the label is in `labels.js`); until then it says the generic "Có một điều cần xem trong chọn hình." The list "Cảnh báo" already has the sentence.
- **`tests/e2e/picks_auto/launch_picks_auto.py`** (`make_plan`) writes a plan with no `kinds`: a real e2e run would fail the new check; it needs `kinds` (and a `fallback` on its context lines) like `tests/picks/auto_helpers.PLAN`.
- **storyboard worker**: `inputs/beats.json` has, for every beat, `kinds` (`[]` for a beat of an older picks document) and `missing` (`[{what, code}]`). `kinds` is in the order the line speaks. Codes of `missing` today: `no_candidates`, `agent_none`, `source_limited`, `search_failed`, `no_thumbs`, `import_failed`, `import_limited`, `time_up`, `write_refused`.
  A line with `outside`/`compare` whose items are all of the main painting is a line whose picture was not found (the `fallback` is on screen).
- **`session.py`**: `PLAN_LIMITS` / `CHOOSE_LIMITS` there are now the old defaults (20 min / 80 steps) and are used only by the tests that build a briefing by hand; the job uses `job.PLAN_LIMITS` / `job.CHOOSE_LIMITS`. Whoever owns `session.py` may want to make one the other.
- `docs/APP_GUIDE.md` (the owner's Vietnamese guide) does not mention the 34% rule of the outside lines.

## 7. What could not be verified

- No real agent read the new template: it is checked by tests that parse its examples and tables, not by a model. Whether Opus High keeps to 120 steps and 30 minutes when it must write `entity`, `period`, `alt` and a fallback for about 30 lines is for the real run; the limit grew because the old run used 36 of 80 steps.
- Nothing of the search was run: with `kinds` and fallbacks the plan can now ask for 60 pictures, and the quality of what is found is websearch's part.
- The hand-made `kinds` are my reading of the narration; borderline lines are listed in section 4.4. They were checked against the new rules but not against the owner's taste.
- The page was not opened (no browser): the new sentence is in `labels.js` and syntax-checked.
