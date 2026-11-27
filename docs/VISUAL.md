# The visual script

`visual.json` describes what the viewer sees alongside the narration. It is the
input intended for a later composer, not a storyboard or a video. Its schema
is `bti.visual/1`. Word indices are zero-based, and all ranges are half-open:
`w0` is included and `w1` is excluded. Words and their speech times come from
`timing.json`.

- `made_from.narration` and `made_from.timing` identify the source versions.
- `cast` lists subjects: a stable `id`, `kind` (person, place, work, thing,
  idea, or text), `name`, alternate names in `also`, whether the subject needs
  a name `strip`, a short explanatory `sub`, and `shown_by`, its main-painting
  regions or borrowed pictures. A subtitle may not repeat the name, exceed six
  words, or be more certain than the narration.
- `wanted` describes a missing or sought picture. Each item has an `id`, one
  cast `subject`, `kind`, search wording and `alt` wordings, `period`, `status`,
  selected `picture` or null, and search wordings already `tried`.
- `moments` are in spoken order. Each has an `id`, narration `line`, `w0` and
  `w1`, `about` (a cast id or null), `show`, camera `move`, starting frame
  `from`, `say`, and a one-sentence Vietnamese explanation `why` for the owner.
  When a concrete subject cannot be shown, `about_not_shown` gives the reason.

`show` is exactly one of a whole painting, a main-painting region, a borrowed
picture, a wanted picture with a whole-or-region fallback, a pair of pictures,
 or a map with named places. `move` is `hold`, `push`, `travel` or `pull`;
`from` names `previous`, `whole`, or a region. A `say` entry is an `intro` at a
spoken word, `point` entries at named regions and words, `read` with region and
text, `labels` with at least three named regions and texts, or a `number` with
its text and what it counts. Maps and pairs are show forms, not listed intent
forms in the contract.

For example, if words 10–14 say “The river curves around the village”, a
moment can say:

```json
{
  "id": "m0003", "line": "b0002", "w0": 10, "w1": 15,
  "about": "river", "show": {"region": "RIVER"},
  "move": "travel", "from": "previous", "say": [],
  "why": "Theo dòng sông qua ngôi làng."
}
```

The cast must contain `river` and list `{"region": "RIVER"}` under its
`shown_by`. A borrowed picture belongs in `picks.json` under `assets`; its
`caption`, `shows` (cast ids), and `period` (`then`, `later`, `today`, or null)
are properties of that picture, not of one moment.

## Checks and current limits

`bti.visual.validate.validate(document, timing, picks)` returns issues without
mutating its arguments. Shape errors and determinable violations have rule,
moment, and a corrective message. V1 covers word coverage and line boundaries;
V2 the 1.5-second minimum; V3–V5 subject depictions, wanted pictures and
introductions; V6–V8 strips, subtitles and points; V9–V11 whole views,
repeated regions, maps and pairs; and V12 the provenance of on-screen text.

The current checks are **not a complete semantic validator**. Timing and picks
alone cannot establish a term's familiarity, whether a description overstates
certainty, whether a scene is the end of a cold open, what a comparison means,
or every frame's geometry. Some checks return `level: "review"` when the evidence cannot decide a semantic
question; these are returned on save and do not block it. Do not treat a clean
result as proof of semantic claims that the data cannot encode. When a shape error affects fields needed by a rule, the checker reports what it
can independently establish, but cannot safely run every rule until the shape is fixed. Real-data converter
output reports these limitations and any interpretation it could not recover.

## Legacy conversion

`python -m bti.visual.from_project PROJECT --out visual.json --pool-out picks-copy.json`
reads legacy storyboard, timing, narration and picks. It writes the visual file
and, when requested, a separate picks copy whose `shows` values are inferred
from subject picture references. It does not edit the source picks. Counts and
examples of validator findings and conversion notes go to standard output.
A shot whose camera has no named region does not contain enough information to
recover its intended region reliably; the converter records a whole-painting
fallback and reports it. Legacy shots can cross line boundaries, so the output
can require editing before it meets V1.

## Reading and saving

`GET /api/projects/{pid}/visual` returns `visual` and its `rev`; both are null
when there is no saved document. `PUT /api/projects/{pid}/visual` accepts
`{"visual": {...}, "base_rev": "...", "actor": "agent:model"}`. On the first
save use a null `base_rev`. The server refuses a stale revision with 409 and
invalid input with 422 and its `issues`. A successful write preserves the
previous document in project history, records the actor, and returns review
issues in `issues`. The validity
limitations above apply to the server checks as well.

## Composer pointers

The composer draws a white ring at a small `point` target or a shown thing or inscription up to 45% of frame height. It excludes named people and targets mostly overlapping a person’s head, face or bust. A larger eligible shown region gets a maximum-size ring at its centre. The ring starts at the named word (or the moment's first word when no cast name or alias is spoken), lasts at most three seconds and no longer than the sentence, and is used at most twice per region per video. The scorecard judges the overall marks-per-minute target; size limits are in the style's compose table. Spotlights remain available for manual edits.
