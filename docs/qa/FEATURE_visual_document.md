# Visual document: implementation and QA

The visual module now has a strict document shape, mechanical validity checks,
revision-checked atomic storage and history, GET/PUT routes, helpers, a legacy
converter, two invented fixture projects with small illustrated PNG paintings and a fixture for each V rule. The two fixture paintings were visually inspected. Picture
pool fields and their typed operation were added to picks. The editor mounts the
router. The checks are incomplete for semantic requirements and must not yet
be treated as proof that a script is safe to compose: V6, V7, V8, V9, V11 and
V12 depend partly on facts that the contract does not encode. The issue list
can contain heuristic false positives. The converter loses detail when a shot
has no region slot, or when an overlay cannot be expressed in the contract.

Verified so far: `tests/visual` 46 passed; `tests/ops` 565 passed; after the
router was mounted, `tests/editor` 534 passed. The JavaScript suite ran before
the subsequent Python changes: 505 passed, 1 skipped. The final test sweep and
generated-document checks are recorded below once complete.

## Real-data conversion (snapshot copies)

The converter ran on copies of `arnolfini-v3` and `eligius` inside the Windows
snapshot. The source projects were not modified. Both resulting visual files
were copied under `.scratch/agy_tasks/visualdoc/golden/`. These are research
outputs, not approved scripts: the partial validator and missing camera-region
information mean that they must not yet drive the composer without review.

Counts below include errors and review requests, and are distinct moments associated with those findings, not proven violations.
For a cast-level issue, moments whose `about` or introduction names that cast member
are associated with it; a cast issue may therefore have no associated moments. A
moment can have more than one issue. Counts of zero do not prove compliance.

| project | moments | distinct words covered | cast | V1 | V2 | V3 | V4 | V5 | V6 | V7 | V8 | V9 | V10 | V11 | V12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| arnolfini-v3 | 108 | 1730/1730 (100%) | 64 | 1 | 0 | 40 | 0 | 4 | 56 | 51 | 41 | 10 | 10 | 0 | 38 |
| eligius | 100 | 1737/1737 (100%) | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 64 | 0 | 3 | 1 |

Representative findings (where there is only one finding, only one example is
available; rules with zero reports have no examples):

- Arnolfini V1: m0064 crosses line b0166. V3: m0001's painting and m0002's
  Giovanni are not matched to `shown_by`. V5: m0002 Giovanni and m0003
  Costanza introductions likewise do not match the exact listed regions.
- Arnolfini V6: `lucca_to_bruges` and `silks` need review for proper-name and
  unfamiliar-term strip requirements; a route does not necessarily need one. V7:
  `lucca_to_bruges` and `earliest_inventory` have subtitles over the checked
  limit or containing a name. V8: m0001 names BAND_TOP, which is absent from the picks record, and
  needs review for person and frame geometry; the storyboard may have additional regions.
- Arnolfini V9: m0010 and m0012 were flagged as whole views after the converter
  fell back because the shot lacked a named region; this does not establish
  that the original footage was whole. V10: m0008 and m0020 use WOMAN_HEAD,
  which the script uses five times. V12: m0062's “Garden prayer” and
  “Crucifixion” did not match the literal evidence used by the checker; that is
  not proof that the source record lacks support.
- Eligius V1: m0034 crosses b0019 and m0068 crosses b0040. V8: m0018 WEIGHT_BOX and m0059 COCONUT require person and frame review. V11: m0016 map and m0073 pair need
  semantic review. V9: m0002 and m0003 were flagged after
  whole-view fallbacks. V12: m0079's inscription translation was not found by
  the literal evidence check. The cast is empty because this legacy project
  has no `subjects` table; missing introductions are not evidence of their
  absence from the video.

The first 20 non-program Arnolfini moments were compared in order with
`.scratch/coord/shots.json`. Seventeen have the same named region or borrowed
picture as the shot table (including MAN_WINDOW, WOMAN_UPPER, DOG, MIRROR,
02_lucca_seen, jan_van_eyck and WOMAN_HEAD). Three shots have no named slot:
m0001/s0489, m0010/s0490 and m0012/s0495. The converter labels those `whole`
without enough evidence; m0010's shot-table narration says to start close on
faces and joined hands, so that fallback is demonstrably unsuitable. Eligius
produced 82 conversion notes, largely because its camera shots lack region
slots. These losses and unresolved overlay mappings need correction before
using these files as composer goldens.

## Verification

On the Windows snapshot: `tests/visual` 46 passed; `tests/draft` 643 passed;
`tests/picks` 506 passed; `tests/editor` 534 passed; `tests/auto` 270 passed;
`tests/ops` 565 passed; `tests/cli` 132 passed; `tests/export` 87 passed and 2
skipped; `tests/identity` 106 passed; `tests/music` 34 passed; and
`tests/engine -m "not slow"` 854 passed, 14 skipped and 168 deselected. The
editor suite was run after mounting the router; subsequent changes were confined
to the visual module and its tests. The shared FastAPI dependency emitted a
Starlette deprecation warning in several suites.

On the Mac, the requested JavaScript suite had 505 passed and 1 skipped. No
JavaScript file was changed, so there were none to check with `node --check`.
The three generated-document `--check` commands passed on the snapshot.
