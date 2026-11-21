# Names on screen — namefirst (incomplete)

## Changes

`bti/engine/techniques/labels.py` extends `X-ANN-01` with optional `sub`, reusing the same `label_layer` and second-line scale as `X-ANN-02`. The default is empty, and an absent or empty value becomes `None`, just as the old one-line path did. This is preferable to X-ANN-02 for a person or subject: its fields and defaults describe the artwork itself, whereas X-ANN-01 names the spoken subject and leaves the second line explicit. `style/gae/techniques.json` defines the new parameter and offers the technique to detail, outside and comparison beats. `bti/draft/techniques_md.py` already generates the offered descriptions from the catalogue; a test checks that both examples and `sub` reach its output. `text_too_brief` already checks the new string as a separate line; a test covers that. The shared draft/deep-edit template, fast-edit template, generated storyboard skill, engine README, API guide and Vietnamese owner guide contain the new guidance. Tests are in `tests/engine/test_name_strip.py`, `tests/draft/test_claude_runner.py` and `tests/picks/test_auto_runners.py`; `tests/engine/namefirst_still_fixture.py` makes the still fixtures. Two old briefing length limits were raised for the required additional guidance.

The draft provider previously allowed only check, defaults and still. `bti/draft/providers/claudecode.py` now also allows `crop --grid -o look/*`, `crop --box * -o look/*`, `crop --region * -o look/*` and `crop --help`, in POSIX and all three existing Windows wrapper spellings; deny rules are unchanged. `bti/draft/workspace.py` substitutes the platform-specific crop wrapper into the shared draft/deep-edit task. The real still refusal used `out/look/`, whereas the permitted output is top-level `look/`; the task now states that explicitly. Fast edit uses typed operations and has no helper session. Picks already permits grid and box, including width variants, under top-level `look/` and its template already uses the platform-specific wrapper. A test extracts complete helper examples from the draft template and matches them against the permission rules.

## Unfinished: name warning

`name_not_shown` has not been implemented. Consequently there are no new Vietnamese warning labels or automatic-run behavior for it, and it has not been run on the supplied documents. Beat facts are fact IDs, not typed person names; picks' optional encyclopedia `entity` can be a place or building, and the supplied saved picks do not retain these entities for the people. Timing and regions do not reliably say which named person is visible. A capital-letter rule alone cannot distinguish people from sentence starts or places; a more selective identification and visibility rule still needs to be implemented and tested. `small_detail_not_lit` stops the automatic storyboard gate, but no claim is made that the absent new warning does so.

The requested real-document results also conflict with the first-introduction-only rule. Costanza is named in `b0003` at 28 seconds while `s0124` shows her head, then again in `b0008` while `s0013` shows her. Giovanni is named at 80.5209–81.8209 seconds in `b0006` while `s0010` (from 78.61 seconds) shows a borrowed portrait identified in that pick as Giovanni. `s0028` starts at 201.14 seconds and names him again. Under the first visible introduction rule, flagging both his introduction on `s0010` and the later `s0028` as first introductions requires a different interpretation. The work is left incomplete rather than claiming that this contradiction is resolved.

Person/figure names apparent from a human reading of the supplied timing include Jan van Eyck (also Van Eyck), Costanza Trenta (also Costanza), Giovanni Arnolfini (also Giovanni), Hernoul le Fin, Virgin Mary, Saint Martha, Saint Margaret, Philip the Good, Christ, God, Erwin Panofsky, Dürer and Velázquez. None can be reported as flagged because the check does not exist. This is not an automated recognition result; Hernoul le Fin is an uncertain identification of Giovanni, which also illustrates the alias problem. The required missing/shown/second mention/borrowed picture/no usable names fixtures and the real-document warning run therefore remain unverified.

## Catalogue text in full

### X-ANN-01

- **name:** Name label strip
- **description:** A dark translucent strip across the lower frame with a white caps name and an optional smaller second line; the right end fades out.
- **usage_rule:** Show the first spoken name of an on-screen person, saint or thing. A person stands alone; a small thing also gets HI-01.
- **use_when:** The first time the narration speaks the proper name of a person or thing, or the unfamiliar name of an object such as a settle, and its subject is on screen, show that name on the naming word, long enough to read. On another picture name the subject the narration speaks of, not the picture itself.
- **needs:** The name from the narration. Use sub for a shortened caution in the narration’s own words when identity is uncertain, or a plain fact from the same sentence. On a borrowed picture sub may give its record title, maker and date only when available, never the photographer or photograph year. A strip is never alone for a small thing: use HI-01; never light a person or face.
- **never_when:** The name has been presented before; the subject is not on screen; the label invents certainty or a fact; the shot already has X-ANN-02; three or more parts are named in sequence (KEY-01). A face needs no label saying FACE, but a person named by the narration gets their name.
- **example:** Arnolfini: "The woman most often named as the wife in green is Costanza Trenta, first wife of the merchant Giovanni Arnolfini" (COSTANZA TRENTA / most often named as the wife); "Some historians see Saint Martha, patron of housewives" (SAINT MARTHA / some historians see Saint Martha; Hours of Henry VIII).

### X-ANN-02

- **name:** Artwork label (two lines)
- **description:** The same strip with two lines: the work title in caps, then ARTIST, YEAR in a smaller line beneath.
- **usage_rule:** Use for another artwork when the shot does not already use X-ANN-01 to name its spoken subject.
- **use_when:** A shot shows another artwork or a museum object for the first time and has no X-ANN-01 subject strip: the title in capitals and, in a smaller line, the maker and the date. It shows in the first seconds of that picture.
- **needs:** The title, the maker and the date from the picture's own record in `inputs/assets.json` (`title`, `artist`, `year`).
- **never_when:** A shot with X-ANN-01; a photographer or year of a photograph as the artwork maker or date; data that is not in the picture's record (never write a maker or a date from memory); the main painting; the same picture a second time; a picture that is not an artwork or an object (a street view, a portrait photograph of a person).
- **example:** St. Eligius b0049: "He was born at Baerle, probably in 1415." (the label of the painter's own Head of Christ, which the owner picked for the line)

## Draft rules 14 and 15 in full

14. **Light each small detail.** Whenever a detail sentence names a thing small on screen, use HI-01 on the thing, including consecutive shots and near views. "Small on the screen" also means a narrow or flat thing in a wide frame whose narrower side is under 20% of the frame's matching side (a bench, a rug, a string of beads, a candle). Start on the naming word and hold to the end of the shot, at least 2.5 s; a strip for a small thing accompanies the light; a named person gets a strip alone. Use a tight region of the thing itself, measured with `{{CROP_CMD}}` and added to `out/regions.json` when needed. Leave the thing under about 40% of both frame dimensions (or under 20% on its narrower side when narrow or flat): compiler zoom cap keeps tight small regions under 40%. Keep the centre 5% inside every edge throughout and `floor` / `surround_floor` at least 0.6. Use AN-01 only to distinguish one of several similar things so close a light would cover them all. Never light the opening shot or channel-name beat, the whole picture, a face, figure or something outside the painting; never use two spotlights at once or a ring on the same thing.
15. **Text on the screen is true and tidy.** Names appear on screen when first introduced. The first time the narration speaks a proper name and its subject is on screen, put that name in X-ANN-01 at the word that names it; never repeat that person's or thing's name later. Keep each line fully visible for at least 1.5 seconds for up to three words, adding 0.3 seconds per extra word up to 4 seconds. A person's strip stands alone: never spotlight a face or figure. A small thing still gets HI-01 with the strip. The narration says "The woman most often named as the wife in green is Costanza Trenta, first wife of the merchant Giovanni Arnolfini": use COSTANZA TRENTA with `sub` "most often named as the wife"; use GIOVANNI ARNOLFINI when he is first named on screen, with a plain fact such as "merchant" if useful. When identity is uncertain, `sub` must shorten the narration's own cautious words and never claim more certainty; a certain identity needs no `sub` or may use a plain fact from the same sentence. "Some historians see Saint Martha, patron of housewives" on the borrowed miniature gets SAINT MARTHA with `sub` "some historians see Saint Martha; Hours of Henry VIII" when that title is usable; include the record's maker and date too when available. Preserve the caution even if the record is incomplete. Never use a photographer or a photograph's year as the work's maker or date; never add X-ANN-02 on the same shot. Every other date, figure, place and name comes from the narration or the picture's own record; never a placeholder ("Unknown author"), a source note, the word "narration" or the same words twice. Write captions and sub-captions explicitly, `""` for none. MAP-01: only places named in narration; `region_label` `""`, `region_iso` `[]`, `sea_names` `false` unless named. KEY-01: allow about 2.5 s from the last named part’s word to the shot end; if the sentence ends on the list, labels come a little before their words.

## Draft rule 19 and changed kinds rows in full

19. **A beat of kind `outside` that has an outside picture shows that picture for most of the beat, not the painting.** The owner: "Don't just show the painting too much. The agent must search for the image that captures the narrative the most." The check `outside_on_painting` flags a beat whose outside picture is on screen for less than 45% of it, or for less than 25% when the beat has two kinds (`detail, outside`: the picture comes when the sentence reaches the thing, so the first part may stay on the painting), and in both cases for less than 3.5 seconds (the whole beat when it is shorter). A picture found at step 2 or 3 of the wider net (`step: 2` or `step: 3` in `picks`) is shown like any outside picture and gets its two-line label (`X-ANN-02`) with its own title and date, unless X-ANN-01 names the spoken subject on that shot, so that the viewer is never told it is the thing itself.

| `detail` | names or describes one thing that is in the painting | point_at | HI-01 for every thing small on screen; X-ANN-01 on the first spoken name of a visible person or thing; a person needs no light; AN-01 only for one among tightly grouped similar things; KEY-01 for three or more parts named in a row |
| `outside` | is about a person, place, object, event or custom that is not in the painting | context | X-LAY-01 on the outside picture of the beat, with X-ANN-01 for the first spoken subject name, its usable record in `sub`, otherwise X-ANN-02 (title, maker, year) when it is an artwork; FOOT-01 for a clip of today; no picture found: rule 20 |

## Verification

The requested Node suite produced:

```
ℹ tests 496
ℹ suites 0
ℹ pass 495
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
ℹ duration_ms 1042.070333
```

Windows snapshot `namefirst`, one test folder at a time, produced these summary lines exactly:

```
engine: ========= 784 passed, 14 skipped, 166 deselected in 359.33s (0:05:59) =========
draft: ============ 4 failed, 545 passed, 1 warning in 165.67s (0:02:45) =============
draft-final: ================= 549 passed, 1 warning in 168.45s (0:02:48) ==================
ops: ================= 539 passed, 1 warning in 132.01s (0:02:12) ==================
editor: ================= 530 passed, 1 warning in 247.31s (0:04:07) ==================
auto: ================= 242 passed, 1 warning in 101.94s (0:01:41) ==================
state: ================= 321 passed, 1 warning in 195.28s (0:03:15) ==================
picks: ============ 1 failed, 431 passed, 1 warning in 128.19s (0:02:08) =============
picks-final: ================= 432 passed, 1 warning in 129.50s (0:02:09) ==================
name-strip: ============================== 3 passed in 1.06s ==============================
```

The first draft run failed four existing checks: two fixed text/heading expectations and two briefing length ceilings. The truthfulness heading and small-thing pointer wording were restored; the ceilings were raised for the added requested guidance. The first picks run failed the old assertion that the draft provider excludes crop; it now asserts the new authorized permission. Both full retests passed. The initial mixed-folder focused test command was interrupted during snapshot copying before pytest began. The full engine run preceded the final catalogue wording and the two additional focused strip tests; the final focused run is listed above. The three requested generator checks (`bti.cli.docgen --check`, `bti.ops.doc --check`, `bti.editor.hints --check`) exited successfully with no output. Both `node --check` commands and `git diff --check` exited successfully.

The two stills were generated on the snapshot with `python -m bti.engine still`, copied into `.scratch/namefirst/stills/`, and inspected:

- `one.png`: a one-line SETTLE strip, legible; this is a strip rendering fixture and does not demonstrate the required spotlight on a real small thing.
- `two.png`: COSTANZA TRENTA with a legible smaller caution line. Both look correct as strips. The painting is visibly soft because the fixture starts from the repository's 192×263 image; neither image demonstrates a finished production frame.

The empty second line follows the old drawing path, and the engine suite drew the stored fixtures, but a direct before/after pixel comparison against the old version was not made. The name warning, its UI text, automatic-run policy, full name-recognition fixtures and the requested actual-warning results remain undone.
