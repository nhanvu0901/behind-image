# Visual planner: real-data acceptance

Source: read-only `arnolfini-v3` on the Windows server, copied under `run/snap-planner/acceptance/arnolfini-v3`. No real model, download, video render or paid service was used. The golden visual script was copied separately into the snapshot. The workspace was built by `bti.visual.workspace.build_plan` with the same inputs used by the job.

## What was seen

The painting grid shows the full painting, legible fractional coordinates, both people, the mirror and the dog. The workspace also produced 48 region thumbnails; the first visibly shows the wall inscription. The first catalogue sheet shows recognizable maps, Bruges, a marten, textile, sculpture, carpet and portraits. 56 of 56 non-main assets have generated thumbnails. 1 have a caption; 0 have recorded subjects; 0 have recorded period. The catalogue faithfully exposes missing metadata rather than inventing it. Consequently the planner must inspect pictures and cannot infer every period or identity claim from these records alone.

The converted legacy script projects to 59 lines, 107 line items and 3 lines with borrowed pictures. Present picks have 59 lines, 98 items and 3 lines with borrowed pictures. This is a projection comparison, not evidence that a new plan improves picture coverage.

The original golden script fails the work-folder `check.cmd`: ERROR V1: 1, ERROR V3: 74, ERROR V5: 4, ERROR V6: 1, ERROR V7: 22, ERROR V8: 17, REPORT V10: 10, REPORT V12: 30, REPORT V6: 2, REPORT V7: 35, REPORT V8: 49, REPORT V9: 12. The hand-repaired copy examines the first ten moments and changes seven (including closer portraits, removing person marks and removing ungrounded subjects); its check still fails overall: ERROR V1: 1, ERROR V3: 65, ERROR V5: 2, ERROR V6: 1, ERROR V7: 22, ERROR V8: 12, REPORT V10: 7, REPORT V12: 30, REPORT V6: 2, REPORT V7: 35, REPORT V8: 44, REPORT V9: 12. Its first ten moments have 0 attached errors. Reports are not proof of semantic correctness. Removing `about` on two whole views is a limitation of this mechanical repair, not an endorsed editorial decision. The first real plan by a model and the resulting video have not been produced or reviewed.

## Work-folder files and sizes

- `check.cmd`: 150 bytes
- `crop.cmd`: 160 bytes
- `images/grid.jpg`: 370,004 bytes
- `images/main.jpg`: 329,634 bytes
- `images/pool_1.jpg`: 58,547 bytes
- `images/pool_10.jpg`: 84,121 bytes
- `images/pool_11.jpg`: 50,705 bytes
- `images/pool_12.jpg`: 41,054 bytes
- `images/pool_13.jpg`: 81,072 bytes
- `images/pool_14.jpg`: 55,661 bytes
- `images/pool_15.jpg`: 66,796 bytes
- `images/pool_16.jpg`: 106,027 bytes
- `images/pool_17.jpg`: 81,736 bytes
- `images/pool_18.jpg`: 103,927 bytes
- `images/pool_19.jpg`: 105,315 bytes
- `images/pool_2.jpg`: 80,211 bytes
- `images/pool_20.jpg`: 56,753 bytes
- `images/pool_21.jpg`: 71,035 bytes
- `images/pool_22.jpg`: 73,648 bytes
- `images/pool_23.jpg`: 33,942 bytes
- `images/pool_24.jpg`: 126,878 bytes
- `images/pool_25.jpg`: 39,672 bytes
- `images/pool_26.jpg`: 84,334 bytes
- `images/pool_27.jpg`: 63,433 bytes
- `images/pool_28.jpg`: 73,345 bytes
- `images/pool_29.jpg`: 58,547 bytes
- `images/pool_3.jpg`: 111,006 bytes
- `images/pool_30.jpg`: 25,208 bytes
- `images/pool_31.jpg`: 58,337 bytes
- `images/pool_32.jpg`: 30,063 bytes
- `images/pool_33.jpg`: 58,730 bytes
- `images/pool_34.jpg`: 34,929 bytes
- `images/pool_35.jpg`: 65,552 bytes
- `images/pool_36.jpg`: 10,890 bytes
- `images/pool_37.jpg`: 94,715 bytes
- `images/pool_38.jpg`: 62,768 bytes
- `images/pool_39.jpg`: 58,547 bytes
- `images/pool_4.jpg`: 54,942 bytes
- `images/pool_40.jpg`: 61,996 bytes
- `images/pool_41.jpg`: 36,306 bytes
- `images/pool_42.jpg`: 77,907 bytes
- `images/pool_43.jpg`: 69,491 bytes
- `images/pool_44.jpg`: 35,861 bytes
- `images/pool_45.jpg`: 60,790 bytes
- `images/pool_46.jpg`: 50,181 bytes
- `images/pool_47.jpg`: 58,547 bytes
- `images/pool_48.jpg`: 45,976 bytes
- `images/pool_49.jpg`: 37,137 bytes
- `images/pool_5.jpg`: 38,434 bytes
- `images/pool_50.jpg`: 73,498 bytes
- `images/pool_51.jpg`: 113,579 bytes
- `images/pool_52.jpg`: 63,050 bytes
- `images/pool_53.jpg`: 41,727 bytes
- `images/pool_54.jpg`: 35,228 bytes
- `images/pool_55.jpg`: 30,449 bytes
- `images/pool_56.jpg`: 117,508 bytes
- `images/pool_6.jpg`: 118,872 bytes
- `images/pool_7.jpg`: 65,499 bytes
- `images/pool_8.jpg`: 54,116 bytes
- `images/pool_9.jpg`: 85,548 bytes
- `images/region_0.jpg`: 24,674 bytes
- `images/region_1.jpg`: 76,753 bytes
- `images/region_10.jpg`: 48,635 bytes
- `images/region_11.jpg`: 20,420 bytes
- `images/region_12.jpg`: 28,180 bytes
- `images/region_13.jpg`: 40,537 bytes
- `images/region_14.jpg`: 11,854 bytes
- `images/region_15.jpg`: 14,881 bytes
- `images/region_16.jpg`: 19,926 bytes
- `images/region_17.jpg`: 69,217 bytes
- `images/region_18.jpg`: 74,464 bytes
- `images/region_19.jpg`: 78,008 bytes
- `images/region_2.jpg`: 23,920 bytes
- `images/region_20.jpg`: 36,256 bytes
- `images/region_21.jpg`: 36,723 bytes
- `images/region_22.jpg`: 16,966 bytes
- `images/region_23.jpg`: 25,497 bytes
- `images/region_24.jpg`: 57,396 bytes
- `images/region_25.jpg`: 16,919 bytes
- `images/region_26.jpg`: 28,071 bytes
- `images/region_27.jpg`: 46,541 bytes
- `images/region_28.jpg`: 50,681 bytes
- `images/region_29.jpg`: 35,658 bytes
- `images/region_3.jpg`: 16,942 bytes
- `images/region_30.jpg`: 4,985 bytes
- `images/region_31.jpg`: 2,129 bytes
- `images/region_32.jpg`: 17,355 bytes
- `images/region_33.jpg`: 5,815 bytes
- `images/region_34.jpg`: 2,573 bytes
- `images/region_35.jpg`: 2,128 bytes
- `images/region_36.jpg`: 2,267 bytes
- `images/region_37.jpg`: 23,295 bytes
- `images/region_38.jpg`: 12,187 bytes
- `images/region_39.jpg`: 57,878 bytes
- `images/region_4.jpg`: 97,755 bytes
- `images/region_40.jpg`: 81,528 bytes
- `images/region_41.jpg`: 45,560 bytes
- `images/region_42.jpg`: 86,103 bytes
- `images/region_43.jpg`: 4,471 bytes
- `images/region_44.jpg`: 79,262 bytes
- `images/region_45.jpg`: 2,808 bytes
- `images/region_46.jpg`: 80,587 bytes
- `images/region_47.jpg`: 2,275 bytes
- `images/region_5.jpg`: 59,879 bytes
- `images/region_6.jpg`: 43,309 bytes
- `images/region_7.jpg`: 63,310 bytes
- `images/region_8.jpg`: 40,824 bytes
- `images/region_9.jpg`: 59,000 bytes
- `inputs/catalogue.json`: 8,018 bytes, 679 whitespace-separated words
- `inputs/context.json`: 166 bytes, 11 whitespace-separated words
- `inputs/dossier.json`: 670 bytes, 75 whitespace-separated words
- `inputs/facts.json`: 7,346 bytes, 1,215 whitespace-separated words
- `inputs/main_large.jpg`: 1,816,554 bytes
- `inputs/narration.json`: 35,247 bytes, 5,070 whitespace-separated words
- `inputs/painting.json`: 11,665 bytes, 1,079 whitespace-separated words
- `inputs/picks.json`: 54,428 bytes, 4,286 whitespace-separated words
- `inputs/timing.json`: 156,527 bytes, 16,712 whitespace-separated words
- `TASK.md`: 4,778 bytes, 705 whitespace-separated words

## Catalogue shown to the planner

- `ban_do_lucca`: `images/pool_1.jpg`; caption=''; shows=[]; period=None
- `brugge_blick_vom`: `images/pool_2.jpg`; caption=''; shows=[]; period=None
- `european_pine_marten`: `images/pool_3.jpg`; caption=''; shows=[]; period=None
- `length_velvet`: `images/pool_4.jpg`; caption=''; shows=[]; period=None
- `saint_margaret_antioch`: `images/pool_5.jpg`; caption=''; shows=[]; period=None
- `lotto_carpet`: `images/pool_6.jpg`; caption=''; shows=[]; period=None
- `marcia_1480`: `images/pool_7.jpg`; caption=''; shows=[]; period=None
- `philipp_good_van`: `images/pool_8.jpg`; caption=''; shows=[]; period=None
- `lavin_panofksyportrait_g`: `images/pool_9.jpg`; caption=''; shows=[]; period=None
- `moses_burning_bush`: `images/pool_10.jpg`; caption=''; shows=[]; period=None
- `img_5994`: `images/pool_11.jpg`; caption=''; shows=[]; period=None
- `jan_van_eyck`: `images/pool_12.jpg`; caption=''; shows=[]; period=None
- `great_art_explained`: `images/pool_13.jpg`; caption=''; shows=[]; period=None
- `las_meninas_diego`: `images/pool_14.jpg`; caption=''; shows=[]; period=None
- `jan_van_eyck_4565`: `images/pool_15.jpg`; caption=''; shows=[]; period=None
- `dyers_soaking_red`: `images/pool_16.jpg`; caption=''; shows=[]; period=None
- `rogier_van_der`: `images/pool_17.jpg`; caption=''; shows=[]; period=None
- `taming_tarasque_hours`: `images/pool_18.jpg`; caption=''; shows=[]; period=None
- `02_lucca_seen`: `images/pool_19.jpg`; caption='Lucca seen from the Guinigi Tower'; shows=[]; period=None
- `philip_good`: `images/pool_20.jpg`; caption=''; shows=[]; period=None
- `dyeing_british_library`: `images/pool_21.jpg`; caption=''; shows=[]; period=None
- `squirrel_perched_snowy`: `images/pool_22.jpg`; caption=''; shows=[]; period=None
- `adobestock_194234698`: `images/pool_23.jpg`; caption=''; shows=[]; period=None
- `moses_burning_bush_1d81`: `images/pool_24.jpg`; caption=''; shows=[]; period=None
- `spanish_autorretrato_sel`: `images/pool_25.jpg`; caption=''; shows=[]; period=None
- `hans_holbein_younger`: `images/pool_26.jpg`; caption=''; shows=[]; period=None
- `self_portrait_study`: `images/pool_27.jpg`; caption=''; shows=[]; period=None
- `diego_velazquez_self`: `images/pool_28.jpg`; caption=''; shows=[]; period=None
- `ban_do_lucca_2623`: `images/pool_29.jpg`; caption=''; shows=[]; period=None
- `portrait_philip_good`: `images/pool_30.jpg`; caption=''; shows=[]; period=None
- `jan_van_eyck_3e60`: `images/pool_31.jpg`; caption=''; shows=[]; period=None
- `length_velvet_c0b3`: `images/pool_32.jpg`; caption=''; shows=[]; period=None
- `saint_martha`: `images/pool_33.jpg`; caption=''; shows=[]; period=None
- `brylki_bursztynu_baltyck`: `images/pool_34.jpg`; caption=''; shows=[]; period=None
- `tondo_mirror_frame`: `images/pool_35.jpg`; caption=''; shows=[]; period=None
- `panofsky_erwin`: `images/pool_36.jpg`; caption=''; shows=[]; period=None
- `god_calling_moses`: `images/pool_37.jpg`; caption=''; shows=[]; period=None
- `self_portrait`: `images/pool_38.jpg`; caption=''; shows=[]; period=None
- `ban_do_lucca_2321`: `images/pool_39.jpg`; caption=''; shows=[]; period=None
- `portrait_philip_goo_3201`: `images/pool_40.jpg`; caption=''; shows=[]; period=None
- `virgin_blue_robe`: `images/pool_41.jpg`; caption=''; shows=[]; period=None
- `screen_shot_2014`: `images/pool_42.jpg`; caption=''; shows=[]; period=None
- `tomb_effigy_lady`: `images/pool_43.jpg`; caption=''; shows=[]; period=None
- `death_mask_richard`: `images/pool_44.jpg`; caption=''; shows=[]; period=None
- `selbstportrat_albrecht_d`: `images/pool_45.jpg`; caption=''; shows=[]; period=None
- `self_portrait_label`: `images/pool_46.jpg`; caption=''; shows=[]; period=None
- `ban_do_lucca_085d`: `images/pool_47.jpg`; caption=''; shows=[]; period=None
- `annunciation_jan_van`: `images/pool_48.jpg`; caption=''; shows=[]; period=None
- `l_inconnue_seine`: `images/pool_49.jpg`; caption=''; shows=[]; period=None
- `self_portrait_atribuido`: `images/pool_50.jpg`; caption=''; shows=[]; period=None
- `antique_map_bruges`: `images/pool_51.jpg`; caption=''; shows=[]; period=None
- `damask_fragment_pomegran`: `images/pool_52.jpg`; caption=''; shows=[]; period=None
- `gallerix_org`: `images/pool_53.jpg`; caption=''; shows=[]; period=None
- `durer_alte_pinakothek`: `images/pool_54.jpg`; caption=''; shows=[]; period=None
- `self_portrait_diego`: `images/pool_55.jpg`; caption=''; shows=[]; period=None
- `st_martha_tramples`: `images/pool_56.jpg`; caption=''; shows=[]; period=None

## Plan instruction as rendered in this work folder

# Write the visual script

Make the images help a viewer understand the narration. Read `inputs/narration.json` and `inputs/timing.json` for every line, sentence, word index and time, `inputs/facts.json` and `inputs/dossier.json` for facts, `inputs/painting.json` and `images/grid.jpg` for the painting, and `inputs/catalogue.json` and its thumbnails for every picture already in the pool. Use any pool picture at any moment; these are a catalogue, not an earlier plan. Start afresh from the narration. Do not carry forward an old subjects table or visual script.

The opening orients the viewer to the work, its maker and people before exploring its details and question.

Each moment has one subject and covers a continuous span of words within one line. Cover all words in order without overlap or gaps. Let the sentence or clause guide its length; moments must have at least 1.5 seconds of speech. Show the subject: when introducing a person show their face or figure, not an unrelated detail. For something outside the painting ask for a real picture of that thing, even if a similar picture exists in the pool; prefer pictures made in the period. Give each request alternative search words and a fallback that makes sense if nothing is found. The full painting is rare: use it when the whole work is the subject or when it orients the viewer. Vary views of a subject so the same region does not carry the whole story.

Introduce a named person, place or other work once, at the spoken name, while the subject is shown. Use a known picture or region for the introduction so it remains valid if a search fails. Give the second line a short, informative and appropriately cautious description that adds to the name. Ordinary things need no name; a thing gets one only if the narration introduces and explains an unfamiliar term. Mark only a small detail that must be found; never mark a person. Maps are for a journey or a connection between named places. A pair is for pictures being compared or two portraits named close together. Screen text must come from the narration or picture record, never a filename, source name or guess. Do not put narration on screen.

Examples: in a portrait show the sitter's face when their name is spoken and a real view of their birthplace when it is discussed. In a landscape follow a river through different views and seek an old picture of a town outside the painting. In a crowded religious scene show the saint's face at their introduction and point only to a small attribute that identifies them. In a still life frame the fruit when discussing it, and label an unfamiliar vessel only if the narration explains its name.

Write `out/visual.json` as `bti.visual/1` with `made_from`, `cast`, `wanted` and `moments`. `made_from` contains narration and timing hashes supplied in `inputs/context.json`. Cast entries have `id`, `kind` (person, place, work, thing, idea, text), `name`, `also`, `strip`, `sub`, `shown_by` (regions or pool pictures); a named unfamiliar thing also has `term: true`. Wanted entries have `id`, one cast `subject`, `kind` (portrait, work, place, object, document), `search`, `alt`, `period` (then, later, today, null), `status: "open"`, `picture: null`, `tried: []`.

A moment has `id`, `line`, word indices `w0` and `w1` (start inclusive, end exclusive), `about` (one cast id or null), `show`, `move` (hold, push, travel, pull), `from` (previous, whole, or region), `say`, and a Vietnamese sentence `why`. If a concrete subject cannot be shown, add `about_not_shown` explaining why. Show is one of `{"whole":true}`, `{"region":"NAME"}`, `{"picture":"KEY"}`, `{"want":"w1","else":{"region":"NAME"}}`, `{"pair":[{"picture":"A"},{"want":"w1","else":{"whole":true}}]}`, or `{"map":{"places":["Paris, France","Rome, Italy"]},"else":{"whole":true}}`. A want's fallback may also be the whole painting. Map picture is filled later.

Say entries are `{"intro":"cast-id","word":12}`, `{"point":[{"region":"NAME","word":12}]}`, `{"read":{"region":"NAME","text":"..."}}`, `{"labels":[{"region":"NAME","text":"..."}, ...]}` (at least three), or `{"number":{"text":"...","of":"..."}}`. Regions named for new details go in `out/regions.json` as an object of names to `{"box":[x0,y0,x1,y1],"what":"description"}`; coordinates are fractions of the painting. Use .\crop.cmd to inspect a crop or grid.

Run .\check.cmd. Fix every ERROR and check again. REPORT entries show whole-painting views, repeated regions or matters requiring your judgment; examine them, but they do not prevent completion. The checker cannot decide whether a term is unfamiliar, a description is sufficiently cautious, a map is meaningful, or screen text is grounded in the sources: you must decide those from the narration and dossier.


## Choose instruction rendered for Windows

# Choose pictures

Read `inputs/wants.json` and look at each candidate sheet. For each wanted subject choose the candidate that actually shows it, preferring a picture from the period; reject pictures that only resemble it. Return `out/choice.json` as an object keyed by wanted id: `{"w1":{"pick":1,"caption":"A concise English description","shows":["cast-id"],"period":"then"}}`. Use the candidate number, or `null` if none is suitable. A caption is at most 60 characters, describes the picture, and is not a file or source name. `shows` names the cast subjects actually visible; `period` is then, later, today, or null. Do not invent identities or dates. When nothing is suitable, the plan's fallback will be used and the owner will see the search wordings tried.

Run .\check.cmd and fix every ERROR. REPORT entries need your judgment.

If `tighten/inputs/regions.json` exists, inspect each enlarged region and place a tight box around the one thing it shows. Write `tighten/out/tighten.json` as `{"schema":"bti.picks.tighten/1","regions":[{"name":"REGION","action":"tight","box":[x0,y0,x1,y1],"thing":"description of the thing","confirmed":false,"reason":"Lý do."}]}`. Use the coordinates of that region's enlarged image. Run the check to make the review sheets, inspect them, set `confirmed` to true only when the box fits, and check again. If the object is absent, use `action: "drop"` and explain why.


## Check output: original golden script

```text
ERROR V3: m0001: show a listed depiction of arnolfini_portrait or explain about_not_shown.
REPORT V9: m0001: whole painting view; verify it serves the narration.
ERROR V8: m0001: use a region present on the main painting.
REPORT V8: m0001: verify BAND_TOP is not a person and can be framed with the shown picture.
ERROR V3: m0002: show an existing painting region or pool picture.
ERROR V3: m0002: show a listed depiction of giovanni_arnolfini or explain about_not_shown.
ERROR V8: m0002: use a region present on the main painting.
REPORT V8: m0002: verify HUSBAND_FACE is not a person and can be framed with the shown picture.
ERROR V5: m0002: introduce giovanni_arnolfini while showing a listed depiction.
ERROR V3: m0003: show an existing painting region or pool picture.
ERROR V3: m0003: show a listed depiction of costanza_trenta or explain about_not_shown.
ERROR V5: m0003: introduce costanza_trenta while showing a listed depiction.
ERROR V8: m0003: do not point at person region WOMAN_FIGURE.
REPORT V8: m0003: verify WOMAN_FIGURE is not a person and can be framed with the shown picture.
REPORT V8: m0005: verify DOG is not a person and can be framed with the shown picture.
ERROR V3: m0006: show a listed depiction of doorway_visitors or explain about_not_shown.
ERROR V8: m0006: do not point at person region DOORWAY_FIGURES.
REPORT V8: m0006: verify DOORWAY_FIGURES is not a person and can be framed with the shown picture.
ERROR V8: m0007: use a region present on the main painting.
REPORT V8: m0007: verify DOORWAY_GLOW is not a person and can be framed with the shown picture.
ERROR V3: m0009: show an existing painting region or pool picture.
ERROR V3: m0009: show a listed depiction of costanza_trenta or explain about_not_shown.
ERROR V3: m0010: show a listed depiction of arnolfini_couple or explain about_not_shown.
REPORT V9: m0010: whole painting view; verify it serves the narration.
REPORT V8: m0010: verify JOINED_HANDS is not a person and can be framed with the shown picture.
ERROR V3: m0011: show an existing painting region or pool picture.
ERROR V3: m0011: show a listed depiction of arnolfini_couple or explain about_not_shown.
ERROR V3: m0012: show a listed depiction of bruges or explain about_not_shown.
REPORT V9: m0012: whole painting view; verify it serves the narration.
ERROR V3: m0014: show an existing painting region or pool picture.
ERROR V3: m0014: show a listed depiction of silks or explain about_not_shown.
ERROR V3: m0019: show a listed depiction of costanza_trenta or explain about_not_shown.
ERROR V3: m0021: show an existing painting region or pool picture.
ERROR V3: m0021: show a listed depiction of arnolfini_couple or explain about_not_shown.
ERROR V3: m0023: show an existing painting region or pool picture.
ERROR V3: m0023: show a listed depiction of costanza_trenta or explain about_not_shown.
REPORT V8: m0027: verify BLUE_HEM is not a person and can be framed with the shown picture.
ERROR V3: m0028: show an existing painting region or pool picture.
ERROR V3: m0031: show an existing painting region or pool picture.
ERROR V3: m0031: show a listed depiction of tabard or explain about_not_shown.
ERROR V5: m0031: introduce tabard while showing a listed depiction.
ERROR V3: m0032: show an existing painting region or pool picture.
ERROR V3: m0032: show a listed depiction of pine_marten_fur or explain about_not_shown.
REPORT V8: m0033: verify STRAW_HAT is not a person and can be framed with the shown picture.
REPORT V8: m0034: verify BOOTS is not a person and can be framed with the shown picture.
REPORT V8: m0035: verify JEWELLERY is not a person and can be framed with the shown picture.
ERROR V3: m0036: show an existing painting region or pool picture.
ERROR V3: m0036: show a listed depiction of arnolfini_couple or explain about_not_shown.
ERROR V3: m0037: show an existing painting region or pool picture.
ERROR V3: m0038: show an existing painting region or pool picture.
ERROR V3: m0038: show a listed depiction of red_bed or explain about_not_shown.
ERROR V3: m0039: show an existing painting region or pool picture.
REPORT V8: m0040: verify BENCH_CUSHION is not a person and can be framed with the shown picture.
ERROR V3: m0041: show an existing painting region or pool picture.
ERROR V3: m0041: show a listed depiction of gargoyles or explain about_not_shown.
ERROR V3: m0042: show a listed depiction of carved_saint or explain about_not_shown.
REPORT V9: m0042: whole painting view; verify it serves the narration.
REPORT V8: m0042: verify CARVED_SAINT is not a person and can be framed with the shown picture.
ERROR V3: m0043: show a listed depiction of saint_martha or explain about_not_shown.
REPORT V9: m0043: whole painting view; verify it serves the narration.
REPORT V8: m0043: verify CARVED_SAINT is not a person and can be framed with the shown picture.
REPORT V8: m0044: verify RUG is not a person and can be framed with the shown picture.
REPORT V8: m0045: verify ORANGES is not a person and can be framed with the shown picture.
ERROR V3: m0046: show an existing painting region or pool picture.
ERROR V3: m0046: show a listed depiction of glass_window or explain about_not_shown.
REPORT V8: m0046: verify WINDOW is not a person and can be framed with the shown picture.
ERROR V3: m0047: show a listed depiction of cherry_tree or explain about_not_shown.
REPORT V9: m0047: whole painting view; verify it serves the narration.
REPORT V8: m0047: verify CHERRY_TREE is not a person and can be framed with the shown picture.
REPORT V8: m0048: verify CHANDELIER is not a person and can be framed with the shown picture.
REPORT V8: m0048: verify LIT_CANDLE is not a person and can be framed with the shown picture.
ERROR V3: m0049: show an existing painting region or pool picture.
ERROR V3: m0050: show an existing painting region or pool picture.
ERROR V3: m0050: show a listed depiction of convex_mirror or explain about_not_shown.
REPORT V8: m0050: verify MIRROR is not a person and can be framed with the shown picture.
ERROR V3: m0051: show a listed depiction of convex_mirror or explain about_not_shown.
ERROR V3: m0052: show an existing painting region or pool picture.
ERROR V3: m0052: show a listed depiction of convex_mirror or explain about_not_shown.
ERROR V8: m0054: use a region present on the main painting.
REPORT V8: m0054: verify DOORWAY_GLOW is not a person and can be framed with the shown picture.
REPORT V8: m0055: verify RAISED_HAND is not a person and can be framed with the shown picture.
ERROR V3: m0057: show a listed depiction of doorway_visitors or explain about_not_shown.
REPORT V9: m0057: whole painting view; verify it serves the narration.
ERROR V8: m0060: do not point at person region ROUNDELS_MAN.
REPORT V8: m0060: verify ROUNDELS_MAN is not a person and can be framed with the shown picture.
ERROR V3: m0061: show a listed depiction of passion_roundels or explain about_not_shown.
REPORT V9: m0061: whole painting view; verify it serves the narration.
ERROR V3: m0062: show a listed depiction of crucifixion_roundel or explain about_not_shown.
REPORT V12: m0062: verify screen text against the narration or picture record: 'Garden prayer'.
REPORT V12: m0062: verify screen text against the narration or picture record: 'Crucifixion'.
ERROR V8: m0062: do not point at person region CRUCIFIXION_ROUNDEL.
REPORT V8: m0062: verify CRUCIFIXION_ROUNDEL is not a person and can be framed with the shown picture.
ERROR V8: m0063: do not point at person region ROUNDELS_MAN.
REPORT V8: m0063: verify ROUNDELS_MAN is not a person and can be framed with the shown picture.
ERROR V8: m0063: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0063: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V1: m0064: start at word 1030 and keep the range inside line b0166.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_DEPOSITION is not a person and can be framed with the shown picture.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_ENTOMBMENT is not a person and can be framed with the shown picture.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_RISING is not a person and can be framed with the shown picture.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_DESCENT is not a person and can be framed with the shown picture.
ERROR V8: m0064: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0064: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V3: m0065: show an existing painting region or pool picture.
ERROR V3: m0065: show a listed depiction of passion_roundels_her_side or explain about_not_shown.
ERROR V8: m0065: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0065: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V3: m0067: show an existing painting region or pool picture.
ERROR V3: m0067: show a listed depiction of tomb_dog or explain about_not_shown.
ERROR V3: m0068: show an existing painting region or pool picture.
ERROR V3: m0069: show a listed depiction of death_mask or explain about_not_shown.
ERROR V3: m0070: show an existing painting region or pool picture.
ERROR V3: m0070: show a listed depiction of tabard or explain about_not_shown.
REPORT V8: m0071: verify JOINED_HANDS is not a person and can be framed with the shown picture.
REPORT V12: m0074: verify screen text against the narration or picture record: "The painter's signature".
REPORT V8: m0076: verify ORANGES is not a person and can be framed with the shown picture.
REPORT V8: m0077: verify ORANGES is not a person and can be framed with the shown picture.
REPORT V8: m0080: verify DOG is not a person and can be framed with the shown picture.
ERROR V3: m0081: show an existing painting region or pool picture.
ERROR V3: m0081: show a listed depiction of tabard or explain about_not_shown.
REPORT V8: m0081: verify TABARD is not a person and can be framed with the shown picture.
ERROR V3: m0082: show a listed depiction of carved_saint or explain about_not_shown.
REPORT V9: m0082: whole painting view; verify it serves the narration.
REPORT V8: m0082: verify CARVED_SAINT is not a person and can be framed with the shown picture.
ERROR V3: m0083: show an existing painting region or pool picture.
ERROR V3: m0083: show a listed depiction of red_bed or explain about_not_shown.
REPORT V8: m0084: verify DOG is not a person and can be framed with the shown picture.
ERROR V3: m0085: show a listed depiction of carved_saint or explain about_not_shown.
REPORT V8: m0085: verify CARVED_SAINT is not a person and can be framed with the shown picture.
REPORT V8: m0086: verify JOINED_HANDS is not a person and can be framed with the shown picture.
ERROR V3: m0087: show an existing painting region or pool picture.
ERROR V3: m0090: show an existing painting region or pool picture.
ERROR V3: m0091: show an existing painting region or pool picture.
ERROR V3: m0092: show an existing painting region or pool picture.
ERROR V3: m0093: show an existing painting region or pool picture.
REPORT V8: m0093: verify CHANDELIER is not a person and can be framed with the shown picture.
REPORT V8: m0093: verify WHITE_HEADDRESS is not a person and can be framed with the shown picture.
REPORT V8: m0094: verify SILL_ORANGE_REFLECTION is not a person and can be framed with the shown picture.
REPORT V9: m0095: whole painting view; verify it serves the narration.
REPORT V8: m0095: verify SILL_ORANGE_REFLECTION is not a person and can be framed with the shown picture.
ERROR V3: m0096: show an existing painting region or pool picture.
ERROR V3: m0096: show a listed depiction of costanza_trenta or explain about_not_shown.
ERROR V3: m0097: show an existing painting region or pool picture.
ERROR V3: m0097: show a listed depiction of joined_hands or explain about_not_shown.
REPORT V8: m0097: verify JOINED_HANDS is not a person and can be framed with the shown picture.
ERROR V8: m0097: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0097: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V3: m0098: show an existing painting region or pool picture.
ERROR V3: m0098: show a listed depiction of small_dog or explain about_not_shown.
REPORT V8: m0098: verify DOG is not a person and can be framed with the shown picture.
REPORT V12: m0101: verify screen text against the narration or picture record: "Witness or painter's mark".
ERROR V3: m0103: show an existing painting region or pool picture.
ERROR V5: m0104: move the intro word to where albrecht_durer's name or alias is spoken.
ERROR V3: m0105: show a listed depiction of albrecht_durer or explain about_not_shown.
REPORT V9: m0106: whole painting view; verify it serves the narration.
ERROR V3: m0108: show a listed depiction of joined_hands or explain about_not_shown.
REPORT V9: m0108: whole painting view; verify it serves the narration.
REPORT V7: arnolfini_family: verify the subtitle is no more certain than the narration.
REPORT V12: arnolfini_family: verify the subtitle against the narration or picture record.
ERROR V7: lucca_to_bruges: shorten sub to six words and omit the name and aliases.
REPORT V6: lucca_to_bruges: verify whether this is a proper name that needs a strip.
REPORT V7: lucca_to_bruges: verify the subtitle is no more certain than the narration.
REPORT V12: lucca_to_bruges: verify the subtitle against the narration or picture record.
ERROR V7: earliest_inventory: shorten sub to six words and omit the name and aliases.
REPORT V7: earliest_inventory: verify the subtitle is no more certain than the narration.
REPORT V12: earliest_inventory: verify the subtitle against the narration or picture record.
ERROR V7: virgin_mary: shorten sub to six words and omit the name and aliases.
REPORT V7: virgin_mary: verify the subtitle is no more certain than the narration.
REPORT V12: virgin_mary: verify the subtitle against the narration or picture record.
ERROR V7: virgin_mary_rug_painting: shorten sub to six words and omit the name and aliases.
REPORT V7: virgin_mary_rug_painting: verify the subtitle is no more certain than the narration.
REPORT V12: virgin_mary_rug_painting: verify the subtitle against the narration or picture record.
ERROR V7: baltic: shorten sub to six words and omit the name and aliases.
REPORT V7: baltic: verify the subtitle is no more certain than the narration.
REPORT V12: baltic: verify the subtitle against the narration or picture record.
REPORT V7: baltic_to_bruges: verify the subtitle is no more certain than the narration.
REPORT V12: baltic_to_bruges: verify the subtitle against the narration or picture record.
ERROR V7: christ: shorten sub to six words and omit the name and aliases.
REPORT V7: christ: verify the subtitle is no more certain than the narration.
REPORT V12: christ: verify the subtitle against the narration or picture record.
ERROR V7: arnolfini_portrait: shorten sub to six words and omit the name and aliases.
REPORT V7: arnolfini_portrait: verify the subtitle is no more certain than the narration.
REPORT V12: arnolfini_portrait: verify the subtitle against the narration or picture record.
ERROR V7: giovanni_arnolfini: shorten sub to six words and omit the name and aliases.
REPORT V7: giovanni_arnolfini: verify the subtitle is no more certain than the narration.
ERROR V7: costanza_trenta: shorten sub to six words and omit the name and aliases.
REPORT V7: costanza_trenta: verify the subtitle is no more certain than the narration.
REPORT V12: costanza_trenta: verify the subtitle against the narration or picture record.
REPORT V7: arnolfini_couple: verify the subtitle is no more certain than the narration.
REPORT V7: bruges: verify the subtitle is no more certain than the narration.
REPORT V7: lucca: verify the subtitle is no more certain than the narration.
REPORT V12: lucca: verify the subtitle against the narration or picture record.
REPORT V7: silks: verify the subtitle is no more certain than the narration.
REPORT V12: silks: verify the subtitle against the narration or picture record.
REPORT V7: jan_van_eyck: verify the subtitle is no more certain than the narration.
REPORT V12: jan_van_eyck: verify the subtitle against the narration or picture record.
ERROR V7: philip_the_good: shorten sub to six words and omit the name and aliases.
REPORT V7: philip_the_good: verify the subtitle is no more certain than the narration.
REPORT V7: latin_inscription: verify the subtitle is no more certain than the narration.
REPORT V7: dyers_miniature: verify the subtitle is no more certain than the narration.
REPORT V12: dyers_miniature: verify the subtitle against the narration or picture record.
ERROR V6: tabard: set term true for a named unfamiliar thing.
REPORT V6: tabard: verify the strip is used only if the narration explains an unfamiliar term.
REPORT V7: tabard: verify the subtitle is no more certain than the narration.
REPORT V12: tabard: verify the subtitle against the narration or picture record.
ERROR V7: carved_saint: shorten sub to six words and omit the name and aliases.
REPORT V7: carved_saint: verify the subtitle is no more certain than the narration.
REPORT V12: carved_saint: verify the subtitle against the narration or picture record.
REPORT V7: saint_martha: verify the subtitle is no more certain than the narration.
REPORT V7: saint_margaret: verify the subtitle is no more certain than the narration.
ERROR V7: doorway_visitors: shorten sub to six words and omit the name and aliases.
REPORT V7: doorway_visitors: verify the subtitle is no more certain than the narration.
REPORT V12: doorway_visitors: verify the subtitle against the narration or picture record.
REPORT V7: amber_beads: verify the subtitle is no more certain than the narration.
ERROR V7: passion_roundels: shorten sub to six words and omit the name and aliases.
REPORT V7: passion_roundels: verify the subtitle is no more certain than the narration.
REPORT V12: passion_roundels: verify the subtitle against the narration or picture record.
ERROR V7: crucifixion_roundel: shorten sub to six words and omit the name and aliases.
REPORT V7: crucifixion_roundel: verify the subtitle is no more certain than the narration.
REPORT V12: crucifixion_roundel: verify the subtitle against the narration or picture record.
ERROR V7: passion_roundels_her_side: shorten sub to six words and omit the name and aliases.
REPORT V7: passion_roundels_her_side: verify the subtitle is no more certain than the narration.
REPORT V12: passion_roundels_her_side: verify the subtitle against the narration or picture record.
ERROR V7: tomb_dog: shorten sub to six words and omit the name and aliases.
REPORT V7: tomb_dog: verify the subtitle is no more certain than the narration.
ERROR V7: death_mask: shorten sub to six words and omit the name and aliases.
REPORT V7: death_mask: verify the subtitle is no more certain than the narration.
REPORT V12: death_mask: verify the subtitle against the narration or picture record.
ERROR V7: wedding_or_memorial: shorten sub to six words and omit the name and aliases.
REPORT V7: wedding_or_memorial: verify the subtitle is no more certain than the narration.
REPORT V12: wedding_or_memorial: verify the subtitle against the narration or picture record.
ERROR V7: alchemist: shorten sub to six words and omit the name and aliases.
REPORT V7: alchemist: verify the subtitle is no more certain than the narration.
REPORT V12: alchemist: verify the subtitle against the narration or picture record.
ERROR V7: oil_glazes: shorten sub to six words and omit the name and aliases.
REPORT V7: oil_glazes: verify the subtitle is no more certain than the narration.
REPORT V12: oil_glazes: verify the subtitle against the narration or picture record.
ERROR V7: albrecht_durer: shorten sub to six words and omit the name and aliases.
REPORT V7: albrecht_durer: verify the subtitle is no more certain than the narration.
REPORT V12: albrecht_durer: verify the subtitle against the narration or picture record.
ERROR V7: diego_velazquez: shorten sub to six words and omit the name and aliases.
REPORT V7: diego_velazquez: verify the subtitle is no more certain than the narration.
REPORT V12: diego_velazquez: verify the subtitle against the narration or picture record.
REPORT V10: m0008: WOMAN_HEAD appears in 5 moments; choose another view or subject.
REPORT V10: m0020: WOMAN_HEAD appears in 5 moments; choose another view or subject.
REPORT V10: m0069: WOMAN_HEAD appears in 5 moments; choose another view or subject.
REPORT V10: m0078: WOMAN_HEAD appears in 5 moments; choose another view or subject.
REPORT V10: m0102: WOMAN_HEAD appears in 5 moments; choose another view or subject.
REPORT V10: m0009: FULL_UPPER appears in 5 moments; choose another view or subject.
REPORT V10: m0037: FULL_UPPER appears in 5 moments; choose another view or subject.
REPORT V10: m0049: FULL_UPPER appears in 5 moments; choose another view or subject.
REPORT V10: m0052: FULL_UPPER appears in 5 moments; choose another view or subject.
REPORT V10: m0103: FULL_UPPER appears in 5 moments; choose another view or subject.
Please repair the errors and check again.
```

## Check output: repaired copy

```text
REPORT V9: m0001: whole painting view; verify it serves the narration.
REPORT V8: m0005: verify DOG is not a person and can be framed with the shown picture.
REPORT V9: m0010: whole painting view; verify it serves the narration.
REPORT V8: m0010: verify JOINED_HANDS is not a person and can be framed with the shown picture.
ERROR V3: m0011: show an existing painting region or pool picture.
ERROR V3: m0011: show a listed depiction of arnolfini_couple or explain about_not_shown.
ERROR V3: m0012: show a listed depiction of bruges or explain about_not_shown.
REPORT V9: m0012: whole painting view; verify it serves the narration.
ERROR V3: m0014: show an existing painting region or pool picture.
ERROR V3: m0014: show a listed depiction of silks or explain about_not_shown.
ERROR V3: m0019: show a listed depiction of costanza_trenta or explain about_not_shown.
ERROR V3: m0021: show an existing painting region or pool picture.
ERROR V3: m0021: show a listed depiction of arnolfini_couple or explain about_not_shown.
ERROR V3: m0023: show an existing painting region or pool picture.
ERROR V3: m0023: show a listed depiction of costanza_trenta or explain about_not_shown.
REPORT V8: m0027: verify BLUE_HEM is not a person and can be framed with the shown picture.
ERROR V3: m0028: show an existing painting region or pool picture.
ERROR V3: m0031: show an existing painting region or pool picture.
ERROR V3: m0031: show a listed depiction of tabard or explain about_not_shown.
ERROR V5: m0031: introduce tabard while showing a listed depiction.
ERROR V3: m0032: show an existing painting region or pool picture.
ERROR V3: m0032: show a listed depiction of pine_marten_fur or explain about_not_shown.
REPORT V8: m0033: verify STRAW_HAT is not a person and can be framed with the shown picture.
REPORT V8: m0034: verify BOOTS is not a person and can be framed with the shown picture.
REPORT V8: m0035: verify JEWELLERY is not a person and can be framed with the shown picture.
ERROR V3: m0036: show an existing painting region or pool picture.
ERROR V3: m0036: show a listed depiction of arnolfini_couple or explain about_not_shown.
ERROR V3: m0037: show an existing painting region or pool picture.
ERROR V3: m0038: show an existing painting region or pool picture.
ERROR V3: m0038: show a listed depiction of red_bed or explain about_not_shown.
ERROR V3: m0039: show an existing painting region or pool picture.
REPORT V8: m0040: verify BENCH_CUSHION is not a person and can be framed with the shown picture.
ERROR V3: m0041: show an existing painting region or pool picture.
ERROR V3: m0041: show a listed depiction of gargoyles or explain about_not_shown.
ERROR V3: m0042: show a listed depiction of carved_saint or explain about_not_shown.
REPORT V9: m0042: whole painting view; verify it serves the narration.
REPORT V8: m0042: verify CARVED_SAINT is not a person and can be framed with the shown picture.
ERROR V3: m0043: show a listed depiction of saint_martha or explain about_not_shown.
REPORT V9: m0043: whole painting view; verify it serves the narration.
REPORT V8: m0043: verify CARVED_SAINT is not a person and can be framed with the shown picture.
REPORT V8: m0044: verify RUG is not a person and can be framed with the shown picture.
REPORT V8: m0045: verify ORANGES is not a person and can be framed with the shown picture.
ERROR V3: m0046: show an existing painting region or pool picture.
ERROR V3: m0046: show a listed depiction of glass_window or explain about_not_shown.
REPORT V8: m0046: verify WINDOW is not a person and can be framed with the shown picture.
ERROR V3: m0047: show a listed depiction of cherry_tree or explain about_not_shown.
REPORT V9: m0047: whole painting view; verify it serves the narration.
REPORT V8: m0047: verify CHERRY_TREE is not a person and can be framed with the shown picture.
REPORT V8: m0048: verify CHANDELIER is not a person and can be framed with the shown picture.
REPORT V8: m0048: verify LIT_CANDLE is not a person and can be framed with the shown picture.
ERROR V3: m0049: show an existing painting region or pool picture.
ERROR V3: m0050: show an existing painting region or pool picture.
ERROR V3: m0050: show a listed depiction of convex_mirror or explain about_not_shown.
REPORT V8: m0050: verify MIRROR is not a person and can be framed with the shown picture.
ERROR V3: m0051: show a listed depiction of convex_mirror or explain about_not_shown.
ERROR V3: m0052: show an existing painting region or pool picture.
ERROR V3: m0052: show a listed depiction of convex_mirror or explain about_not_shown.
ERROR V8: m0054: use a region present on the main painting.
REPORT V8: m0054: verify DOORWAY_GLOW is not a person and can be framed with the shown picture.
REPORT V8: m0055: verify RAISED_HAND is not a person and can be framed with the shown picture.
ERROR V3: m0057: show a listed depiction of doorway_visitors or explain about_not_shown.
REPORT V9: m0057: whole painting view; verify it serves the narration.
ERROR V8: m0060: do not point at person region ROUNDELS_MAN.
REPORT V8: m0060: verify ROUNDELS_MAN is not a person and can be framed with the shown picture.
ERROR V3: m0061: show a listed depiction of passion_roundels or explain about_not_shown.
REPORT V9: m0061: whole painting view; verify it serves the narration.
ERROR V3: m0062: show a listed depiction of crucifixion_roundel or explain about_not_shown.
REPORT V12: m0062: verify screen text against the narration or picture record: 'Garden prayer'.
REPORT V12: m0062: verify screen text against the narration or picture record: 'Crucifixion'.
ERROR V8: m0062: do not point at person region CRUCIFIXION_ROUNDEL.
REPORT V8: m0062: verify CRUCIFIXION_ROUNDEL is not a person and can be framed with the shown picture.
ERROR V8: m0063: do not point at person region ROUNDELS_MAN.
REPORT V8: m0063: verify ROUNDELS_MAN is not a person and can be framed with the shown picture.
ERROR V8: m0063: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0063: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V1: m0064: start at word 1030 and keep the range inside line b0166.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_DEPOSITION is not a person and can be framed with the shown picture.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_ENTOMBMENT is not a person and can be framed with the shown picture.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_RISING is not a person and can be framed with the shown picture.
ERROR V8: m0064: use a region present on the main painting.
REPORT V8: m0064: verify ROUNDEL_DESCENT is not a person and can be framed with the shown picture.
ERROR V8: m0064: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0064: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V3: m0065: show an existing painting region or pool picture.
ERROR V3: m0065: show a listed depiction of passion_roundels_her_side or explain about_not_shown.
ERROR V8: m0065: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0065: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V3: m0067: show an existing painting region or pool picture.
ERROR V3: m0067: show a listed depiction of tomb_dog or explain about_not_shown.
ERROR V3: m0068: show an existing painting region or pool picture.
ERROR V3: m0069: show a listed depiction of death_mask or explain about_not_shown.
ERROR V3: m0070: show an existing painting region or pool picture.
ERROR V3: m0070: show a listed depiction of tabard or explain about_not_shown.
REPORT V8: m0071: verify JOINED_HANDS is not a person and can be framed with the shown picture.
REPORT V12: m0074: verify screen text against the narration or picture record: "The painter's signature".
REPORT V8: m0076: verify ORANGES is not a person and can be framed with the shown picture.
REPORT V8: m0077: verify ORANGES is not a person and can be framed with the shown picture.
REPORT V8: m0080: verify DOG is not a person and can be framed with the shown picture.
ERROR V3: m0081: show an existing painting region or pool picture.
ERROR V3: m0081: show a listed depiction of tabard or explain about_not_shown.
REPORT V8: m0081: verify TABARD is not a person and can be framed with the shown picture.
ERROR V3: m0082: show a listed depiction of carved_saint or explain about_not_shown.
REPORT V9: m0082: whole painting view; verify it serves the narration.
REPORT V8: m0082: verify CARVED_SAINT is not a person and can be framed with the shown picture.
ERROR V3: m0083: show an existing painting region or pool picture.
ERROR V3: m0083: show a listed depiction of red_bed or explain about_not_shown.
REPORT V8: m0084: verify DOG is not a person and can be framed with the shown picture.
ERROR V3: m0085: show a listed depiction of carved_saint or explain about_not_shown.
REPORT V8: m0085: verify CARVED_SAINT is not a person and can be framed with the shown picture.
REPORT V8: m0086: verify JOINED_HANDS is not a person and can be framed with the shown picture.
ERROR V3: m0087: show an existing painting region or pool picture.
ERROR V3: m0090: show an existing painting region or pool picture.
ERROR V3: m0091: show an existing painting region or pool picture.
ERROR V3: m0092: show an existing painting region or pool picture.
ERROR V3: m0093: show an existing painting region or pool picture.
REPORT V8: m0093: verify CHANDELIER is not a person and can be framed with the shown picture.
REPORT V8: m0093: verify WHITE_HEADDRESS is not a person and can be framed with the shown picture.
REPORT V8: m0094: verify SILL_ORANGE_REFLECTION is not a person and can be framed with the shown picture.
REPORT V9: m0095: whole painting view; verify it serves the narration.
REPORT V8: m0095: verify SILL_ORANGE_REFLECTION is not a person and can be framed with the shown picture.
ERROR V3: m0096: show an existing painting region or pool picture.
ERROR V3: m0096: show a listed depiction of costanza_trenta or explain about_not_shown.
ERROR V3: m0097: show an existing painting region or pool picture.
ERROR V3: m0097: show a listed depiction of joined_hands or explain about_not_shown.
REPORT V8: m0097: verify JOINED_HANDS is not a person and can be framed with the shown picture.
ERROR V8: m0097: do not point at person region ROUNDELS_WOMAN.
REPORT V8: m0097: verify ROUNDELS_WOMAN is not a person and can be framed with the shown picture.
ERROR V3: m0098: show an existing painting region or pool picture.
ERROR V3: m0098: show a listed depiction of small_dog or explain about_not_shown.
REPORT V8: m0098: verify DOG is not a person and can be framed with the shown picture.
REPORT V12: m0101: verify screen text against the narration or picture record: "Witness or painter's mark".
ERROR V3: m0103: show an existing painting region or pool picture.
ERROR V5: m0104: move the intro word to where albrecht_durer's name or alias is spoken.
ERROR V3: m0105: show a listed depiction of albrecht_durer or explain about_not_shown.
REPORT V9: m0106: whole painting view; verify it serves the narration.
ERROR V3: m0108: show a listed depiction of joined_hands or explain about_not_shown.
REPORT V9: m0108: whole painting view; verify it serves the narration.
REPORT V7: arnolfini_family: verify the subtitle is no more certain than the narration.
REPORT V12: arnolfini_family: verify the subtitle against the narration or picture record.
ERROR V7: lucca_to_bruges: shorten sub to six words and omit the name and aliases.
REPORT V6: lucca_to_bruges: verify whether this is a proper name that needs a strip.
REPORT V7: lucca_to_bruges: verify the subtitle is no more certain than the narration.
REPORT V12: lucca_to_bruges: verify the subtitle against the narration or picture record.
ERROR V7: earliest_inventory: shorten sub to six words and omit the name and aliases.
REPORT V7: earliest_inventory: verify the subtitle is no more certain than the narration.
REPORT V12: earliest_inventory: verify the subtitle against the narration or picture record.
ERROR V7: virgin_mary: shorten sub to six words and omit the name and aliases.
REPORT V7: virgin_mary: verify the subtitle is no more certain than the narration.
REPORT V12: virgin_mary: verify the subtitle against the narration or picture record.
ERROR V7: virgin_mary_rug_painting: shorten sub to six words and omit the name and aliases.
REPORT V7: virgin_mary_rug_painting: verify the subtitle is no more certain than the narration.
REPORT V12: virgin_mary_rug_painting: verify the subtitle against the narration or picture record.
ERROR V7: baltic: shorten sub to six words and omit the name and aliases.
REPORT V7: baltic: verify the subtitle is no more certain than the narration.
REPORT V12: baltic: verify the subtitle against the narration or picture record.
REPORT V7: baltic_to_bruges: verify the subtitle is no more certain than the narration.
REPORT V12: baltic_to_bruges: verify the subtitle against the narration or picture record.
ERROR V7: christ: shorten sub to six words and omit the name and aliases.
REPORT V7: christ: verify the subtitle is no more certain than the narration.
REPORT V12: christ: verify the subtitle against the narration or picture record.
ERROR V7: arnolfini_portrait: shorten sub to six words and omit the name and aliases.
REPORT V7: arnolfini_portrait: verify the subtitle is no more certain than the narration.
REPORT V12: arnolfini_portrait: verify the subtitle against the narration or picture record.
ERROR V7: giovanni_arnolfini: shorten sub to six words and omit the name and aliases.
REPORT V7: giovanni_arnolfini: verify the subtitle is no more certain than the narration.
ERROR V7: costanza_trenta: shorten sub to six words and omit the name and aliases.
REPORT V7: costanza_trenta: verify the subtitle is no more certain than the narration.
REPORT V12: costanza_trenta: verify the subtitle against the narration or picture record.
REPORT V7: arnolfini_couple: verify the subtitle is no more certain than the narration.
REPORT V7: bruges: verify the subtitle is no more certain than the narration.
REPORT V7: lucca: verify the subtitle is no more certain than the narration.
REPORT V12: lucca: verify the subtitle against the narration or picture record.
REPORT V7: silks: verify the subtitle is no more certain than the narration.
REPORT V12: silks: verify the subtitle against the narration or picture record.
REPORT V7: jan_van_eyck: verify the subtitle is no more certain than the narration.
REPORT V12: jan_van_eyck: verify the subtitle against the narration or picture record.
ERROR V7: philip_the_good: shorten sub to six words and omit the name and aliases.
REPORT V7: philip_the_good: verify the subtitle is no more certain than the narration.
REPORT V7: latin_inscription: verify the subtitle is no more certain than the narration.
REPORT V7: dyers_miniature: verify the subtitle is no more certain than the narration.
REPORT V12: dyers_miniature: verify the subtitle against the narration or picture record.
ERROR V6: tabard: set term true for a named unfamiliar thing.
REPORT V6: tabard: verify the strip is used only if the narration explains an unfamiliar term.
REPORT V7: tabard: verify the subtitle is no more certain than the narration.
REPORT V12: tabard: verify the subtitle against the narration or picture record.
ERROR V7: carved_saint: shorten sub to six words and omit the name and aliases.
REPORT V7: carved_saint: verify the subtitle is no more certain than the narration.
REPORT V12: carved_saint: verify the subtitle against the narration or picture record.
REPORT V7: saint_martha: verify the subtitle is no more certain than the narration.
REPORT V7: saint_margaret: verify the subtitle is no more certain than the narration.
ERROR V7: doorway_visitors: shorten sub to six words and omit the name and aliases.
REPORT V7: doorway_visitors: verify the subtitle is no more certain than the narration.
REPORT V12: doorway_visitors: verify the subtitle against the narration or picture record.
REPORT V7: amber_beads: verify the subtitle is no more certain than the narration.
ERROR V7: passion_roundels: shorten sub to six words and omit the name and aliases.
REPORT V7: passion_roundels: verify the subtitle is no more certain than the narration.
REPORT V12: passion_roundels: verify the subtitle against the narration or picture record.
ERROR V7: crucifixion_roundel: shorten sub to six words and omit the name and aliases.
REPORT V7: crucifixion_roundel: verify the subtitle is no more certain than the narration.
REPORT V12: crucifixion_roundel: verify the subtitle against the narration or picture record.
ERROR V7: passion_roundels_her_side: shorten sub to six words and omit the name and aliases.
REPORT V7: passion_roundels_her_side: verify the subtitle is no more certain than the narration.
REPORT V12: passion_roundels_her_side: verify the subtitle against the narration or picture record.
ERROR V7: tomb_dog: shorten sub to six words and omit the name and aliases.
REPORT V7: tomb_dog: verify the subtitle is no more certain than the narration.
ERROR V7: death_mask: shorten sub to six words and omit the name and aliases.
REPORT V7: death_mask: verify the subtitle is no more certain than the narration.
REPORT V12: death_mask: verify the subtitle against the narration or picture record.
ERROR V7: wedding_or_memorial: shorten sub to six words and omit the name and aliases.
REPORT V7: wedding_or_memorial: verify the subtitle is no more certain than the narration.
REPORT V12: wedding_or_memorial: verify the subtitle against the narration or picture record.
ERROR V7: alchemist: shorten sub to six words and omit the name and aliases.
REPORT V7: alchemist: verify the subtitle is no more certain than the narration.
REPORT V12: alchemist: verify the subtitle against the narration or picture record.
ERROR V7: oil_glazes: shorten sub to six words and omit the name and aliases.
REPORT V7: oil_glazes: verify the subtitle is no more certain than the narration.
REPORT V12: oil_glazes: verify the subtitle against the narration or picture record.
ERROR V7: albrecht_durer: shorten sub to six words and omit the name and aliases.
REPORT V7: albrecht_durer: verify the subtitle is no more certain than the narration.
REPORT V12: albrecht_durer: verify the subtitle against the narration or picture record.
ERROR V7: diego_velazquez: shorten sub to six words and omit the name and aliases.
REPORT V7: diego_velazquez: verify the subtitle is no more certain than the narration.
REPORT V12: diego_velazquez: verify the subtitle against the narration or picture record.
REPORT V10: m0003: WOMAN_HEAD appears in 7 moments; choose another view or subject.
REPORT V10: m0008: WOMAN_HEAD appears in 7 moments; choose another view or subject.
REPORT V10: m0009: WOMAN_HEAD appears in 7 moments; choose another view or subject.
REPORT V10: m0020: WOMAN_HEAD appears in 7 moments; choose another view or subject.
REPORT V10: m0069: WOMAN_HEAD appears in 7 moments; choose another view or subject.
REPORT V10: m0078: WOMAN_HEAD appears in 7 moments; choose another view or subject.
REPORT V10: m0102: WOMAN_HEAD appears in 7 moments; choose another view or subject.
Please repair the errors and check again.
```

## Verification

Windows snapshot suites: `tests/visual` 102 passed; `tests/draft` 643 passed; `tests/picks` 506 passed after updating the action-list expectation; `tests/editor` 534 passed; `tests/auto` 270 passed after correcting action ordering; `tests/ops` 565 passed; `tests/cli` 132 passed; `tests/export` 87 passed, 2 skipped; `tests/identity` 108 passed; `tests/music` 34 passed; `tests/engine -m "not slow"` 858 passed, 14 skipped, 168 deselected. The two export server tests require real rendering and the heavy slot, so were not enabled. Engine skips include optional reel/project fixtures. The Python suites that load FastAPI emitted its existing Starlette/httpx deprecation warning.

On the Mac, the requested Node suites reported 507 passed and 1 skipped because this worktree has no `.venv/bin/python`. I read the skipped engine-code catalogue test: this change introduces no new frontend issue code. No JavaScript was changed, so there were no changed JS files for `node --check`. The three generators (`bti.cli.docgen`, `bti.ops.doc`, `bti.editor.hints`) passed `--check` after regenerating the changed action tables.

The agent and search calls in tests use scripted fakes; the web-on tests use a fake web source. No real plan session has been run. Writes use separate undoable picks batches followed by the visual save; a concurrent change after the initial revision check can leave partial logged batches if a later step refuses.

## Needs another worker

The legacy `docs/VISUAL.md` description predates the new map fallback and optional pool picture and needs an update by its owner outside this worker's module scope.
