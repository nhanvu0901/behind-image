# FIX catalogue: a short catalogue of techniques, each with its exact use case, and a storyboard that follows the kind of each line

Worker `catalogue`, 2026-11-20, worktree `.worktrees/catalogue` (branch `wt/catalogue`). Nothing was committed; no model was called; the server was used only through
the snapshot `D:\code\behind-the-image\run\snap-catalogue\` (the two real storyboards and the pictures of `output\` were read, nothing outside the snapshot was written).

## 1. What was built

| piece | where |
|---|---|
| the catalogue: `offered` for all 86 entries, `hidden_reason` for the 60 hidden ones, `serves` + the four texts (`use_when`, `needs`, `never_when`, `example`) for the 26 offered ones | `style/gae/techniques.json` (+ `techniques.schema.json`: the new fields, and "offered needs the four texts, hidden needs a reason") |
| `StyleBundle.offered()`, `offered_ids()`, `not_offered_text()` (what a model reads when it wrote a hidden technique) | `bti/engine/registry.py` |
| `inputs/techniques.md`: only the offered ones, grouped by the kind of line they serve, each with its four texts, slots and params; the program's techniques in a short last section; an index by kind (with the intent to write) | `bti/draft/techniques_md.py` |
| the draft task: table by `kinds`, rules 16 and 17 as decided, new rules 18 to 21, the two sentences deleted | `skills/storyboard_draft/TASK.template.md` |
| the fast edit briefing and catalogue (offered only, with `use when` / `never when`) | `skills/storyboard_edit/FAST.template.md`, `bti/draft/fastedit.py` (a marked block) |
| `technique_not_offered` (draft and slow edit), the repair of an outside picture shown too small (`outside_camera_refit`), a region framed in the panel of LAY-01 and X-CMP-01 | `bti/draft/compile.py` |
| `unknown_technique` with what to use instead for a typed fast-edit batch | `bti/draft/boxops.py` (a marked block) |
| the viewer checks `device_wrong_kind`, `device_too_little`, `outside_on_painting`, `outside_picture_small` and a fifth, `figure_on_wrong_picture` | `bti/engine/viewchecks.py` (`CATALOGUE_ISSUES`, merged into `CODES` and `ISSUE_CODES`) |
| the five codes stop the automatic run's storyboard gate, each with a reason in English and Vietnamese | `bti/auto_run/checks.py` (a marked block of `STOPS["storyboard"]`) |
| the Vietnamese sentences of the owner | `bti/editor/static/js/errmsg.js` (a block at the end: `CATALOGUE_SENTENCES`) |
| docs | `skills/storyboard/SKILL.md` (five rows and a paragraph), `docs/design/2026-11-18-explainer-components.md` (section 10), `docs/AGENT_API.md` (regenerated: the storyboard row of the quality bar) |
| tests | `tests/engine/test_catalogue_registry.py`, `test_viewchecks_kinds.py`, `test_catalogue_real.py` (+ `real_docs.py`, `fixtures/catalogue/`, `catalogue_stills.py`), `tests/draft/test_catalogue_compile.py`, `tests/editor_frontend/catalogue.test.mjs`; pins updated in `tests/draft/test_{explainers_briefing,fixdraft,identity_catalogue,workspace,box_briefing}.py`, `tests/auto/test_viewer_checks_bar.py`, `tests/editor_frontend/sbissues.test.mjs` |

`CONTRACT:` (status file) one registry field beyond the brief, `serves` (the kinds a technique serves, to group `techniques.md`), and one check beyond the four,
`figure_on_wrong_picture` (the owner's 42 ships over the saint cannot be told otherwise: see section 7). No technique was added or removed: 86 entries, 26 offered, 60 hidden.

## 2. The 86 techniques: offered, or why hidden

Counts of the reasons: `program` 13, `other_format` 14, `replaced` 7, `no_material` 17, `redundant` 9 (the brief expected about 13, 9 "other formats or replaced" and 21 "no material";
my split differs because I counted by what the technique needs: see section 9). `use` names the offered technique a model is told to use instead.

| # | id | name | offered | serves / reason hidden |
|---|---|---|---|---|
| 1 | `CAM-01` | Push-in | **yes** | detail, idea |
| 2 | `CAM-02` | Layered relative motion | no | `no_material`: Needs cut-out figures, a plate of the background behind them and their masks; the pictures step supplies none. |
| 3 | `CAM-03` | Pull-back | **yes** | whole, idea |
| 4 | `CAM-04` | Pan up | **yes** | detail |
| 5 | `CAM-05` | Zoom and shift | **yes** | detail |
| 6 | `CAM-06` | Hold and label reveal | no | `redundant`: STATIC-01 holds the whole painting and X-ANN-01 names it; the program writes the title label of the opening. Use: STATIC-01, X-ANN-01. |
| 7 | `TR-01` | Dissolve | **yes** | compare, outside |
| 8 | `TR-02` | Image slide in/out | no | `redundant`: LAY-01 shows another work beside the painting; a slide-in is not needed. Use: LAY-01. |
| 9 | `TR-03` | Panel opening | no | `no_material`: Needs the closed and the open wings of a triptych as pictures; the pictures step supplies none. |
| 10 | `TR-04` | Full-to-crop hard cut | no | `program`: The hard cut is what happens between two shots when no transition is written: leave `transition_in` out. |
| 11 | `LAY-01` | Two panels | **yes** | compare |
| 12 | `LAY-02` | Four-tile grid | no | `redundant`: X-CMP-01 shows several pictures one after another beside the painting; a four-tile grid is not needed. Use: X-CMP-01. |
| 13 | `LAY-03` | Five-column comparison | no | `redundant`: X-CMP-01 shows several pictures one after another beside the painting; five columns are not needed. Use: X-CMP-01. |
| 14 | `LAY-04` | Inset window | no | `redundant`: FOOT-01 shows a clip full frame and LAY-01 shows two pictures side by side; an inset over the painting is not needed. Use: FOOT-01, LAY-01. |
| 15 | `LAY-05` | Subject held, background changes | no | `no_material`: Needs a cut-out object with its mask and several background pictures; the pictures step supplies none. |
| 16 | `LAY-06` | Translucent vertical strips | no | `other_format`: An effect of one episode of the reference channel (overlapping translucent strips); no kind of line in this pipeline calls for it. |
| 17 | `LAY-07` | Grid with translucent object | no | `no_material`: Needs a cut-out object and a grid of footage clips; the pictures step supplies none. |
| 18 | `LAY-08` | Repeated symmetric motif | no | `other_format`: An effect of one episode of the reference channel (a motif tiled with mirror symmetry); no kind of line in this pipeline calls for it. |
| 19 | `HI-01` | Spotlight | **yes** | detail |
| 20 | `HI-02` | Progressive figure reveal | no | `no_material`: Needs a plate of the empty room and a cut-out mask of every group of figures; the pictures step supplies none. |
| 21 | `HI-03` | Colour kept on subject | no | `no_material`: Needs a mask of the subject that keeps its colour; the pictures step supplies none. |
| 22 | `AN-01` | Circle draw | **yes** | detail |
| 23 | `AN-02` | Object outline | no | `no_material`: Needs the outline of a figure (a mask or a list of points); the regions of the pictures step are ellipses. |
| 24 | `AN-03` | Perspective rays | **yes** | construction |
| 25 | `AN-04` | Map circle and arrow | no | `replaced`: MAP-01 draws real geography with the places and the route; a ring and an arrow on a satellite picture is the old way. Use: MAP-01. |
| 26 | `AN-05` | Dimension ruler | **yes** | figure |
| 27 | `AN-06` | Grid and geometric regions | **yes** | construction |
| 28 | `AN-07` | Dot field densifying | no | `other_format`: An effect of one episode of the reference channel (dots that multiply into a dot field); no kind of line in this pipeline calls for it. |
| 29 | `TXT-01` | Chapter title on blurred image | no | `program`: The program writes the chapter marks (the old chapter title card is replaced by them); you never write a card. |
| 30 | `TXT-02` | Sliding italic text | no | `other_format`: Reviews and critics sliding over a picture is an effect of one episode of the reference channel; the narration is never written on the screen. |
| 31 | `STATIC-01` | Black matte | **yes** | whole |
| 32 | `STATIC-02` | Source label | no | `redundant`: A source note on the screen is not wanted (the credits go in the description); X-ANN-02 gives the title, maker and date of another work. Use: X-ANN-02. |
| 33 | `STATIC-04` | Quote over image | no | `redundant`: A line that is written in the picture is lit and read by DOC-01; any other quotation is read by the narrator, never written on the screen. Use: DOC-01. |
| 34 | `STATIC-05` | Interviewee tag | no | `other_format`: A name tag for a person speaking on camera, which belongs to a series with interviews; this channel has no one on camera. |
| 35 | `STATIC-06` | Map with route | no | `replaced`: MAP-01 draws real geography with the places and the route; this grey map is the old way. Use: MAP-01. |
| 36 | `STATIC-07` | Multi-cell circular diagram | no | `other_format`: An effect of one episode of the reference channel (a circular diagram of cells); no kind of line in this pipeline calls for it. |
| 37 | `STATIC-08` | Name labels on figures | no | `replaced`: KEY-01 places a name beside each named part and keeps the names from touching; this is the old way. Use: KEY-01. |
| 38 | `STATIC-09` | Year centred on image | **yes** | dates, whole |
| 39 | `DIA-01` | Grid and projection rays | no | `no_material`: Needs a grid and the projection points measured on one particular picture (a distorted shape); the pictures step supplies none. |
| 40 | `DIA-02` | Two views of one object | no | `no_material`: Needs the corners of a distorted shape and of its true view measured on one particular picture; the pictures step supplies none. |
| 41 | `DIA-03` | Cross-section and light rays | no | `no_material`: Needs a scan of a paint cross-section with its layers named; the pictures step supplies none. |
| 42 | `DIA-04` | Figure and separated pieces | no | `no_material`: Needs a cut-out figure and the separate pieces of it; the pictures step supplies none. |
| 43 | `DIA-05` | Process silhouette | no | `no_material`: Needs a mask of a silhouette and footage of the process; the pictures step supplies none. |
| 44 | `DIA-06` | Room model and UV image | no | `no_material`: Needs a drawing of the room, a photograph of a detail and an ultraviolet photograph of it; the pictures step supplies none. |
| 45 | `DIA-07` | Eye and vision diagram | no | `no_material`: Needs the images of an eye diagram; the pictures step supplies none. |
| 46 | `CMP-01` | Grey and colour scan side by side | no | `replaced`: STATE-01 shows the same picture in two states (grey scan and colour, for example); this is the old way. Use: STATE-01. |
| 47 | `CMP-02` | Stages versus finished | no | `no_material`: Needs pictures of the stages of the work (scans of the underpainting and drafts); the pictures step supplies none. |
| 48 | `CMP-03` | White and colour versions | no | `no_material`: Needs several colour versions of one work; the pictures step supplies none. |
| 49 | `CMP-04` | Colour blocks beside detail | no | `other_format`: An effect of one episode of the reference channel (a picture reduced to colour blocks); no kind of line in this pipeline calls for it. |
| 50 | `CMP-05` | Two colour states | no | `replaced`: STATE-01 shows the same picture in two states; this is the old way. Use: STATE-01. |
| 51 | `FOOT-01` | Material footage and palette | **yes** | outside |
| 52 | `SHORT-01` | Three horizontal strips | no | `other_format`: Made for a vertical Short; this channel makes one long video about one painting. |
| 53 | `SHORT-02` | Changing view | no | `other_format`: Made for a vertical Short; this channel makes one long video about one painting. |
| 54 | `SHORT-03` | Large type changes | no | `other_format`: Made for a vertical Short; this channel makes one long video about one painting. |
| 55 | `SHORT-04` | Yellow label box | no | `other_format`: A caption box of a promo Short of the reference channel, not of its long films. |
| 56 | `SHORT-05` | Colour wheel from palette | no | `other_format`: Made for a vertical Short; this channel makes one long video about one painting. |
| 57 | `X-TR-01` | Hard cut | no | `program`: The hard cut is what happens between two shots when no transition is written: leave `transition_in` out. |
| 58 | `X-CARD-01` | Chapter card on black | no | `program`: The program writes the chapter marks (the old chapter card is replaced by them); you never write a card. |
| 59 | `X-CARD-02` | Main title card | no | `program`: The program writes the channel-name beat with the video's title (it replaced the title card); you never write a card. |
| 60 | `X-CARD-03` | End credit | no | `other_format`: An end-credit card: the credits of the pictures go in the video's description, not on the screen. |
| 61 | `X-CARD-04` | Question card on white | no | `other_format`: A question on a white card is not this channel's look (a black ground); the narrator asks the question over the painting. |
| 62 | `X-ANN-01` | Detail label strip (one line) | **yes** | detail |
| 63 | `X-ANN-02` | Artwork label (two lines) | **yes** | outside, compare |
| 64 | `X-ANN-03` | Recap labels at closing | **yes** | whole |
| 65 | `X-ANN-04` | Sequential group outlines | no | `no_material`: Needs the outline (a mask or a list of points) of each group of figures; the regions of the pictures step are ellipses. |
| 66 | `X-ANN-05` | Map point markers one by one | no | `replaced`: MAP-01 marks the places one by one on a real map; this is the old way. Use: MAP-01. |
| 67 | `X-LAY-01` | Stills sequence with fixed holds | **yes** | outside |
| 68 | `X-CMP-01` | Swap one side of a split | **yes** | compare |
| 69 | `X-CMP-02` | Wipe compare | no | `replaced`: STATE-01 shows the same picture in two states with a dissolve; this wipe is the old way. Use: STATE-01. |
| 70 | `X-TR-02` | Strip slides in, then splits | no | `redundant`: X-CMP-01 shows other works beside the painting one after another. Use: X-CMP-01. |
| 71 | `X-HI-01` | Dim to isolate then restore | no | `redundant`: HI-01 singles out one part with the same dimming. Use: HI-01. |
| 72 | `ID-OPEN-01` | Opening: raking light | no | `program`: The program writes the opening of the video as an overlay on its first shot; you never choose it. |
| 73 | `ID-LABEL-01` | Artwork label without a strip | no | `program`: The program writes the artwork label of the opening shot; you never choose it. |
| 74 | `ID-OPEN-02` | Opening: dim and name | no | `program`: The program writes the opening of the video as an overlay on its first shot; you never choose it. |
| 75 | `ID-BRAND-01` | Channel name written by light | no | `program`: The program writes the channel-name beat after the cold open; you never choose it. |
| 76 | `ID-BRAND-02` | Channel name on a dimmed picture | no | `program`: The program writes the channel-name beat after the cold open; you never choose it. |
| 77 | `ID-BRAND-03` | Channel name and video title written by light | no | `program`: The program writes the channel-name beat and the video's title after the cold open; you never choose it. |
| 78 | `ID-MARK-01` | Chapter mark written by light | no | `program`: The program writes the chapter marks; you never choose one. |
| 79 | `ID-MARK-02` | Chapter mark on a dimmed picture | no | `program`: The program writes the chapter marks; you never choose one. |
| 80 | `TIME-01` | Time axis with dates | **yes** | dates |
| 81 | `TREE-01` | Relations: family and patrons | **yes** | relations |
| 82 | `STATE-01` | The same picture in two states | **yes** | compare, construction |
| 83 | `MAP-01` | Atlas map | **yes** | journey |
| 84 | `KEY-01` | Labels as a key to parts of a picture | **yes** | detail |
| 85 | `NUM-01` | Big number with a comparison | **yes** | figure |
| 86 | `DOC-01` | A lit line of a document | **yes** | inscription |

## 3. The four texts of every offered technique, as written

`usage_rule` and `evidence` stay in the file untouched as the record of where each technique came from; no model reads `usage_rule` any more.

#### CAM-01 Push-in (serves: detail, idea)

- **use_when**: The sentence stays on ONE thing that is already in the frame and says something about it: it describes the thing, tells its history or gives a reading of it. The camera moves in slowly while the sentence is spoken, so that the eye settles on the thing. This is the usual treatment of a beat of kind `detail`, and of kind `idea` (a reading or an opinion that no picture can show: stay on the thing the opinion is about). The `region` of the shot is the thing; the compiler builds the move toward it.
- **needs**: A region of the picture that IS the thing the sentence is about (see `inputs/assets.json`). If the narration names a thing that has no region, measure the picture and add the region in `out/regions.json` first.
- **never_when**: The sentence moves from one thing to another (CAM-05), steps back to the whole (CAM-03), or is about something that is not in the painting (kind `outside`: show the outside picture, do not push in on the painting). Do not write the camera yourself unless the default is wrong, and never one that leaves the picture small between black bars (rule 13). Not four times in a row.
- **example**: St. Eligius b0002: "But now look at his eyes. They are not on the scales at all. They have turned upward, away from the work in his hand." (push in on the saint's face)

#### CAM-03 Pull-back (serves: whole, idea)

- **use_when**: The sentence steps back from details to the whole picture or to a wider group: a summing-up, the question the video asks, the end of a chapter ("so, a prayer or a shop sign?"), or a return to the whole after a run of details. The crop widens until the picture, or a wide band of it, fills the frame.
- **needs**: Nothing beyond the picture. The move starts on the last thing looked at (a region) and ends on the wide view.
- **never_when**: Twice in one chapter. It never ends on the tiny whole between black bars except in the three places rule 13 allows (the pull back that ends the cold open, ONE chapter opening, the last shot); everywhere else it ends on a wide band that fills the width of the screen.
- **example**: Arnolfini b0141: "Centuries of close study have not settled what this small, crowded panel is for. Is it a wedding picture, a memorial to a wife already gone, or a merchant's showroom?" (the pull back that ends the cold open)

#### CAM-04 Pan up (serves: detail)

- **use_when**: The sentence follows something tall or long from one end to the other, in the order it names the parts: a garment from the hem to the collar, a shelf of objects named one after another, a line of writing along an edge. The frame glides along the thing. The default glides up; a glide down is the same move with the two camera keys swapped.
- **needs**: A picture where the thing is longer than the frame at the zoom of the move: the thing must run past the edge of the frame. The region at the start of the thing.
- **never_when**: The thing fits in the frame (the glide has nothing to uncover), or the parts the sentence names do not lie in a line.
- **example**: St. Eligius b0024: "She wears gold brocade with a pomegranate pattern, probably from Italy, and a gold bonnet embroidered with pearls." (the finished video glides up the woman from the brocade to the bonnet)

#### CAM-05 Zoom and shift (serves: detail)

- **use_when**: The sentence moves the eye from one thing to another, or from a group to one member of it: "follow his hand to hers", "from the couple to the mirror", "up the dress to the fur". The shot starts on the wider view (or on the first thing) and arrives on the second thing as it is named. Use it as the first shot of a `detail` beat whose thing is not in the frame yet.
- **needs**: The region of the second thing (where the move ends). The start is the frame the shot before ended on, or the whole picture.
- **never_when**: The sentence stays on one thing (CAM-01), or the two things lie so close together that nothing travels. Never to add movement to a sentence that does not travel, and never a move that ends with the picture small between black bars (rule 13).
- **example**: Arnolfini b0140: "Follow his hand to hers, at the very centre of the panel." (from his hand to hers)

#### TR-01 Dissolve (serves: compare, outside)

- **use_when**: The change from one shot to the next is a change of STATE, not of subject: the same view in its second state, or a detail of the painting and the real object it shows (the painted mirror and a photograph of a real convex mirror). The first picture melts into the second over about a second.
- **needs**: Both pictures, in the two shots; the dissolve is written as the `transition_in` of the second shot.
- **never_when**: As a general softener between shots (the hard cut is the channel's habit and the default); at the start of a chapter; on every change of picture.
- **example**: St. Eligius b0042: "Mirrors like this were common in Netherlandish homes, where one hung opposite a window brightened the room." (from the painted mirror to a picture of a real one)

#### LAY-01 Two panels (serves: compare)

- **use_when**: The sentence compares a detail of the painting with another work: "Jan van Eyck painted such a mirror in his Arnolfini portrait". The two pictures sit side by side on the matte, each with a caption.
- **needs**: Both pictures: the other work in the picks of the beat, and the DETAIL of the painting that is compared, written as the `region` of the `left` slot (the compiler frames that region in its panel; with no region the panel shows the whole painting small and the detail is lost).
- **never_when**: The other picture was not found (stay on the detail of the painting); two pictures that are not being compared; the comparison is with several works one after another (X-CMP-01).
- **example**: St. Eligius b0045: "Jan van Eyck painted such a mirror in his Arnolfini portrait, and it is presumed to hold his own reflection."

#### HI-01 Spotlight (serves: detail)

- **use_when**: The sentence singles out one part while the frame must stay wide, because the part's place among the others is the point: the one lit candle in a chandelier, the box of weights among the objects on the counter, the tiny falconer in the mirror. The picture darkens a little around the part, the part stays bright, then the whole returns.
- **needs**: The point (a region of the picture) and its size (`rx`, `ry`), and a wide frame. The centre of the region stays inside the frame, 5% in from every edge, from the start of the layer to its end (look at both camera keys); `floor` is 0.6 or more.
- **never_when**: A close-up (the camera already frames the part); two shots in a row; the first minute; more than one in two minutes; together with AN-01 on the same thing.
- **example**: Arnolfini b0165: "High in the brass chandelier, only one candle is lit, and it has been read as the seeing eye of God."

#### AN-01 Circle draw (serves: detail)

- **use_when**: The sentence names a thing that stays small, or sits among similar things, even in the close view, so that the eye cannot find it alone: one coin among many, a small mark beside a signature, one candle among six. A thin ring is drawn around it on the word that names it, held for about two seconds, then it fades.
- **needs**: The point (a region of the picture that is the thing) and its size: the radius fits the thing, not the frame.
- **never_when**: The thing fills a third of the frame or more (the camera already shows it); together with HI-01 on the same thing; two rings at once for things the narration does not name together; the thing is not on screen.
- **example**: St. Eligius b0050: "Beside the signature sits a small heart-shaped sign." (a ring around the sign)

#### AN-03 Perspective rays (serves: construction)

- **use_when**: The sentence makes a claim about depth, perspective or lines that do or do not meet: "their angles suggest the painter did not know the new laws of perspective", "every line leads to the two central figures". White lines are drawn one by one from the edges the claim is about toward the point where they meet, or fail to meet, then they vanish.
- **needs**: The edges the lines follow, taken from the picture itself (the edges of the shelves, the floor tiles, a window frame) and the vanishing point as a point of the picture. The picture must show those edges.
- **never_when**: The narration makes no claim about space; the lines would be drawn across things the narration does not name; a sentence that only says the room is narrow or deep.
- **example**: St. Eligius b0043: "Look at the shelves behind the saint. Their angles suggest the painter did not know the new laws of perspective from Florence. He was still experimenting with space." (the finished video used only a camera move here)

#### AN-05 Dimension ruler (serves: figure)

- **use_when**: The sentence states a real size with its number and unit: "the panel is sixty by eighty-two centimetres", "the layer is forty micrometres thick". Two measuring lines with the numbers pop onto the picture, with a caption for the medium.
- **needs**: The number and its unit from the narration. The whole picture is in the frame with a margin above it: the width line and its number sit just above the picture, so on a frame that fills the screen's height (the default fit) the width number is cut off at the top edge; give the shot a camera about 15% wider than the fit.
- **never_when**: A size that is not in the narration (never measure a size yourself); a count or a price (NUM-01); a date (STATIC-09).
- **example**: No sentence in the two narrations calls for it.

#### AN-06 Grid and geometric regions (serves: construction)

- **use_when**: The sentence says that the picture is built on a shape or a division: a triangle of figures, two halves, a diagonal, the rule of thirds. A faint grid and a translucent shape (a triangle, a circle or a rectangle) are laid over the picture.
- **needs**: The points of the shape in the picture (for a triangle its three corners, as fractions of the picture's width and height), and a picture that really has that shape.
- **never_when**: Anything else: a sentence about the composition in general ("a crowded panel"), about colour or about meaning; a shape the narration does not state.
- **example**: No sentence in the two narrations calls for it.

#### STATIC-01 Black matte (serves: whole)

- **use_when**: The sentence speaks of the painting as an object: its date, its size, where it hangs, who owned it, how it came to be made, what became of it (a beat of kind `whole`), or the shot is a rest on the whole between two moves. The painting is held on the black matte and drifts very slowly.
- **needs**: Nothing beyond the picture itself: no region and no other picture.
- **never_when**: More than rule 13 allows: with the default camera the whole painting sits small between black bars, and that frame may total 5% of the running time (the end of the cold open, ONE chapter opening and the last shot). A camera that fills the width of the screen (a wide band of the picture) does not count against it. Not for a sentence about a thing in the painting (kind `detail`).
- **example**: St. Eligius b0058: "Today it hangs in New York, a rare survivor of what it shows."

#### STATIC-09 Year centred on image (serves: dates, whole)

- **use_when**: The sentence turns on one year: the year of the work, or a turning point that the narration names as one ("in 1476 Charles the Bold was defeated"). The year shows large in the middle of the picture for about three seconds.
- **needs**: The year, as the narration says it, and a calm, dark place in the picture to put it (`x_pct`, `y_pct`): the year is drawn straight over the picture with no dimming, so over a busy part (faces, brocade) it is hard to read.
- **never_when**: Every year that is mentioned in passing; in the same passage as TIME-01 (the axis shows the years); two years in one sentence.
- **example**: St. Eligius b0055: "In 1476 Charles the Bold, the last duke, was defeated in Switzerland."

#### FOOT-01 Material footage and palette (serves: outside)

- **use_when**: The sentence is about a place or a thing as it is TODAY, and a short clip of it is in the picks of the beat: "today it hangs in New York", "the tower still stands". The clip plays full frame with its own motion.
- **needs**: A clip (a picture of kind video) in the picks of the beat.
- **never_when**: A sentence about the past (use a picture made in that time); no clip in the picks (never invent one); a clip that shows something else.
- **example**: St. Eligius b0058: "Today it hangs in New York, a rare survivor of what it shows." (only when the picks hold a clip of the museum; the finished video had a still photograph)

#### X-ANN-01 Detail label strip (one line) (serves: detail)

- **use_when**: The sentence names, for the first time, a thing that is on the screen now and whose name a stranger to the painting would not know: "adder's tongues", "touchstones", "a master's mark". A dark strip with the name in capitals shows for about three seconds, starting on the word that names the thing.
- **needs**: The name in the narration's own words (one to five words, never a sentence). The thing is already in the frame when the label appears.
- **never_when**: The thing was labelled before; the text is an opinion, a date or a whole sentence; the thing is not on screen; the picture is another artwork (X-ANN-02 gives its title, maker and date); the sentence names three or more parts one after another (KEY-01); the thing needs no name (a face, a hand).
- **example**: St. Eligius b0033: "They are probably adder's tongues, fossilized shark teeth believed to change colour when they touched poison." (label ADDER'S TONGUES)

#### X-ANN-02 Artwork label (two lines) (serves: outside, compare)

- **use_when**: A shot shows another artwork or a museum object for the first time: the title in capitals and, in a smaller line, the maker and the date. It shows in the first seconds of that picture.
- **needs**: The title, the maker and the date from the picture's own record in `inputs/assets.json` (`title`, `artist`, `year`).
- **never_when**: Data that is not in the picture's record (never write a maker or a date from memory); the main painting; the same picture a second time; a picture that is not an artwork or an object (a street view, a portrait photograph of a person).
- **example**: St. Eligius b0049: "He was born at Baerle, probably in 1415." (the label of the painter's own Head of Christ, which the owner picked for the line)

#### X-ANN-03 Recap labels at closing (serves: whole)

- **use_when**: The beat is in the closing and recalls details seen earlier, by name, over the last wide view: "come back to the hands and the scales". Plain white words appear beside their details, one after another, as the narration names them.
- **needs**: The names, in the narration's words, and the place of each detail in the picture (regions).
- **never_when**: Anywhere but the closing; details the video never showed; more than five names; names that are not in the narration.
- **example**: Arnolfini b0194: "Come back to the hands at the centre, and to the line above the mirror, Jan van Eyck was here, 1434."

#### X-LAY-01 Stills sequence with fixed holds (serves: outside)

- **use_when**: The sentence is about a person, a place, an object, an event or a custom that is NOT in the painting, and the picks of the beat hold a picture of that thing: a portrait of the king, a view of the cathedral, a coin, an old print of the harbour. The picture fills the frame for most of the beat at its default fit (the whole picture as large as the frame allows, drifting very slowly), then the painting returns.
- **needs**: The picture of the thing itself (or one made in its time) in the picks of the beat, role `context`.
- **never_when**: The picture is not of the thing the sentence is about (a stock picture of something near it, a street map of a town that is only mentioned); the beat has no outside picture (stay on the detail the picks give and use no device to fill the gap); a camera that shows the picture small: it is shown at its default fit and the compiler puts it back, and a picture whose long side is under 1000 px is never enlarged beyond twice its size and then sits on the matte.
- **example**: St. Eligius b0012: "He became personal adviser to the Merovingian King Dagobert." (the portrait of King Dagobert)

#### X-CMP-01 Swap one side of a split (serves: compare)

- **use_when**: The sentence compares the same detail with two or more other pictures one after another: the painting stays in one half and the other half changes from picture to picture, one for each work named.
- **needs**: Two or more other pictures in the picks, in the order the narration names them, and the region of the painting that is being compared, written as the `region` of the `anchor` slot (the compiler frames it in its panel; with no region the whole painting sits small in the panel).
- **never_when**: One other picture only (LAY-01); pictures that are not being compared with the same thing.
- **example**: Arnolfini b0193: "His work was studied, copied and sought abroad, and his influence has been traced to Durer, and to Velazquez in Las Meninas." (the panel stays left while Dürer, then Las Meninas, take the right)

#### TIME-01 Time axis with dates (serves: dates)

- **use_when**: One passage gives three or more dated events of one story, in order: "born in 1415 ... a citizen of Bruges in 1444 ... joined a brotherhood in 1462". A dark shot of its own draws an axis, and each date grows out of it on the word that says it.
- **needs**: The dates (whole years) and a few words for each event, all from the narration. At least three events.
- **never_when**: One or two dates (use STATIC-09 for one, or nothing); a year mentioned in passing; before second 30 (say the date as a large figure on the picture).
- **example**: St. Eligius b0049: "He was born at Baerle, probably in 1415. He became a citizen of Bruges on 6 July 1444. Seven years after joining a brotherhood in 1462, he was named a distinguished member of the painters' guild."

#### TREE-01 Relations: family and patrons (serves: relations)

- **use_when**: One passage ties three or more people together: a family, a patron and the painters he hired, who married whom. A dark shot of its own draws the names with a line between them as the narration says each tie.
- **needs**: The names and the ties between them, all from the narration. At least three people.
- **never_when**: Two people only (say it, or label it); a tie the narration does not state; before second 30.
- **example**: No sentence in the two narrations calls for it (Arnolfini b0138 ties only two people).

#### STATE-01 The same picture in two states (serves: compare, construction)

- **use_when**: The sentence is about what lies under the paint or about how the picture changed: the underdrawing, an infrared or X-ray view, the picture before and after a restoration, the colours as they first were. The same crop is shown in two states and dissolves from one to the other on the word that names the new state.
- **needs**: The same picture in a second state (the same crop), in the picks of the beat.
- **never_when**: There is no second state of the picture (never use two different pictures); the sentence compares the painting with another work (LAY-01).
- **example**: No sentence in the two narrations calls for it.

#### MAP-01 Atlas map (serves: journey)

- **use_when**: The sentence is about a journey or a tie between two or more places (a beat of kind `journey`): where something travelled from and to, where a painter moved, a trade route, money that moved from one city to another. A map of real geography marks the places as the narration names them and draws a dotted route between them.
- **needs**: Two or more places named in the narration, in the order of the journey, with their coordinates; a route or a country tint only when the narration states it. The view is at least 300 km wide (the map has no coastline detail finer than that), so a map can join two towns but cannot show a street or a house.
- **never_when**: One place only: show a picture of that place instead (kind `outside`). Never as the picture of a town that is merely mentioned ("born at Limoges", "the harbour of Bruges", "defeated in Switzerland"), never for a spot inside a city, and never before second 30.
- **example**: St. Eligius b0008: "In 1282 the Hanse merchants even had their own scales, built in Lübeck, set up in Bruges." (from Lübeck to Bruges). The map the finished video put on b0011, "born at Limoges", is NOT a case: it is a picture of the place.

#### KEY-01 Labels as a key to parts of a picture (serves: detail)

- **use_when**: The sentence names three or more parts of the picture that are all in one frame, one after another ("the shelf of rings, silver pitchers, brooches and pearls, and the heavy chain"). A small label fades in beside each part on the word that names it, like the key of a map.
- **needs**: For every label: the region (or the [x, y] point) of the part in the picture, and its word in the narration. All the parts are inside the frame of the shot.
- **never_when**: One or two parts (X-ANN-01, or a ring); parts that are out of the frame; more than five labels on screen at once (split the sentence over two shots); words that are not names of things (opinions, dates).
- **example**: St. Eligius b0031: "So look again at the shelf of rings, silver pitchers, brooches and pearls, and at the heavy chain on the young man."

#### NUM-01 Big number with a comparison (serves: figure)

- **use_when**: The sentence has a quantity as its point: a count, a price, a size, a ratio ("600 pieces of belly fur against 2,000"). The figure shows large over the picture of the thing counted, with a row of small marks when a ratio helps.
- **needs**: The figure and its unit from the narration, and a picture of the THING COUNTED (squirrel fur for pelts, caravels for ships): an outside picture in the picks of the beat, or a detail of the painting when the thing is in it. One to four rows.
- **never_when**: The picture under the figure has nothing to do with the thing counted (a figure about ships over the saint's face); a year (STATIC-09); a number that is only a date or a name; a figure that is not in the narration.
- **example**: Arnolfini b0153: "An ordinary gown took about 600 pieces of belly fur, and this one may have used 2,000." (the finished video put the two figures over the squirrel picture). St. Eligius b0028, "its harbour held 42 British caravels", needs a picture of caravels, not the saint.

#### DOC-01 A lit line of a document (serves: inscription)

- **use_when**: The sentence reads or translates words that are WRITTEN IN THE PICTURE: an inscription, a signature, a motto, a letter, a ledger. The words stay lit while everything else dims; then the reading appears below them in today's words and the original line under it.
- **needs**: The region of the words (they are visible in the picture, and the camera moves in close enough to see them), the reading as the narration says it, and the original line only when the narration or the picture gives it (leave `original` empty rather than guess).
- **never_when**: The words are not visible in the picture (a quotation from a book: the narrator says it and nothing is written); no region covers the words.
- **example**: St. Eligius b0048: "Drop your eye to the bottom edge of the panel, where a line of Latin runs along it. Translated, it reads, Petrus Christus made me in the year 1449."

## 4. Use cases I tightened after reading how the technique is drawn, and why

The brief's table gave the heart of each; these changes come from the code or from the contact sheet (section 6):

1. **STATIC-01** (`use_when` / `never_when`): with the default camera the whole painting sits small between black bars, so the frame counts against the 5 % of rule 13; a camera that fills the width is a "wide band" and does not count. Said in the text.
2. **CAM-04**: the default glides UP; a glide down is the same move with the two camera keys swapped. The thing must run past the edge of the frame at the zoom of the move (else nothing is uncovered). Said in the text. In the still, a `cx` that is not the picture's middle leaves a black bar at the side: the pan keeps `cx = W / 2`.
3. **HI-01**: `floor` 0.6 or more and the region's centre 5 % inside the frame (rules 14, `highlight_off_frame`, `highlight_too_dark`); at 0.6 the dimming is gentle, which is what rule 14 wants.
4. **MAP-01**: the limit is the view (at least 300 km wide: the map has no coastline detail finer), not the distance between the two places; two towns 70 km apart can be joined, a street cannot.
5. **STATIC-09**: the year is drawn straight over the picture with no dimming, although the registry text says "over a blurred or dark image". On a busy part (a face, brocade) it was hard to read in my first still ("1436" over the Paele altarpiece). `needs` now asks for a calm dark place (`x_pct`, `y_pct`).
6. **AN-05**: the width line and its number sit just above the picture; on a frame that fills the screen's height (the default fit) the width number is cut off at the top edge (first still). `needs` now asks for a camera about 15 % wider than the fit.
7. **LAY-01 and X-CMP-01**: the compiler's default showed the WHOLE painting small in its panel, so "compares a detail" was not what the viewer saw (first still). `needs` says the detail is the `region` of the `left` (LAY-01) or `anchor` (X-CMP-01) slot, and the compiler now frames that region in the panel (section 9, decision 10).
8. **X-LAY-01**: the engine's default is 94 % of the frame's height, not the full fit; the viewer check uses the frame's height or width (the brief's wording) and 80 % of it, so the default always passes.
9. **DOC-01, KEY-01, NUM-01, TIME-01, TREE-01, STATE-01**: the old `usage_rule` text (1,000 to 1,400 characters of parameter help) is now split into the four texts; the parameter help stays in the generated `slots`, `params` and `example (the defaults ...)` lines.
10. **AN-03**: the real storyboard has no AN-03 although b0043 calls for it; the example is that line. **AN-05, AN-06, STATE-01, TREE-01**: no sentence of the two narrations calls for them (said so in `example`).

## 5. The five generated entries, as the model reads them

(`inputs/techniques.md`, generated from the registry; the full file is 53 KB, the old one was 81 KB.)

```
### MAP-01 Atlas map  [base]
- used as: a shot (the `technique` of a shot); intents: context, establish
- serves: journey
- use when: The sentence is about a journey or a tie between two or more places (a beat of kind `journey`): where something travelled from and to, where a painter moved, a trade route, money that moved from one city to another. A map of real geography marks the places as the narration names them and draws a dotted route between them.
- needs: Two or more places named in the narration, in the order of the journey, with their coordinates; a route or a country tint only when the narration states it. The view is at least 300 km wide (the map has no coastline detail finer than that), so a map can join two towns but cannot show a street or a house.
- never when: One place only: show a picture of that place instead (kind `outside`). Never as the picture of a town that is merely mentioned ("born at Limoges", "the harbour of Bruges", "defeated in Switzerland"), never for a spot inside a city, and never before second 30.
- real sentence: St. Eligius b0008: "In 1282 the Hanse merchants even had their own scales, built in Lübeck, set up in Bruges." (from Lübeck to Bruges). The map the finished video put on b0011, "born at Limoges", is NOT a case: it is a picture of the place.
- what: A map of real geography (Natural Earth, bundled, no network) drawn like an atlas plate: paper land, a blue-grey or sepia sea that is darker toward the coast with two water lines, an ink coastline, small place marks with italic labels that appear on the word that names them, a dotted route drawn with a travelling head, an optional tinted country, sea names, and a slow push from a wide view to a view fitted to the places.
- slots: none
- params: places:items(1..12)[{id:string*, name:string*, lonlat:lonlat*, at:at[0..600]=1.0, label_side:enum{auto|n|ne|e|se|s|sw|w|nw}=auto}], route:items(0..4)[{from:string*, to:string*, via:string=, shape:enum{curve|straight}=curve, at:at[0..600]=2.6, draw_s:number[0.2..60]=3.0, head:enum{dot|none}=dot}], region_iso:lines, region_label:string=Belgium, region_at:at=0.6, region_fill_s:number[0.1..10]=1.0, view_start_width_km:number[50..20000]=3800, view_start_center:string=, view_end_mode:enum{fit|manual}=fit, view_end_margin_pct:number[0..45]=19, view_end_center:string=, view_end_width_km:number[50..20000]=2400, push_s:number[0..60]=6.0, sea:enum{blue_grey|sepia}=blue_grey, sea_names:bool=True, sea_names_max:number[0..8]=3, graticule_deg:number[0..45]=5, grain:number[0..2]=1.0, vignette:number[0..2]=1.0, label_cap_pct:number[1.2..5]=2.4, fade_s:number[0.05..2]=0.3, seed:number[0..9999]=4
- example (the defaults; replace ALL of its data): {"places":[{"id":"bruges","name":"Bruges","lonlat":[3.2247,51.2093]},{"id":"lucca","name":"Lucca","lonlat":[10.5027,43.8429],"at":2.3}],"route":[{"from":"bruges","to":"lucca","via":"5.5, 48.8; 7.6, 46.0"}],"region_iso":["BE"],"region_label":"Belgium"}
- length: usually 8.0s (min 3.0, max 30.0)

### NUM-01 Big number with a comparison  [overlay]
- used as: an overlay (inside the `overlays` of a shot); intents: quantify, context
- serves: figure
- use when: The sentence has a quantity as its point: a count, a price, a size, a ratio ("600 pieces of belly fur against 2,000"). The figure shows large over the picture of the thing counted, with a row of small marks when a ratio helps.
- needs: The figure and its unit from the narration, and a picture of the THING COUNTED (squirrel fur for pelts, caravels for ships): an outside picture in the picks of the beat, or a detail of the painting when the thing is in it. One to four rows.
- never when: The picture under the figure has nothing to do with the thing counted (a figure about ships over the saint's face); a year (STATIC-09); a number that is only a date or a name; a figure that is not in the narration.
- real sentence: Arnolfini b0153: "An ordinary gown took about 600 pieces of belly fur, and this one may have used 2,000." (the finished video put the two figures over the squirrel picture). St. Eligius b0028, "its harbour held 42 British caravels", needs a picture of caravels, not the saint.
- what: A figure stated large over the dimmed picture, alone or against others: up to four rows, each a small italic label, the figure in big numerals with its units, and a count of small round marks that run out one after another so that a ratio can be seen at a glance; a caption says what one mark stands for and a small line gives the source.
- slots: none
- params: rows:items(1..4)[{label:string=, value:string*, units:string=, count:number[0..60]=0, at:at[0..600]=1.0}], caption:string=each dot is fifty squirr, source:string=Source: the sample narra, dim_picture_to:number[0.2..1.0]=0.38, cap_pct:number[6.0..14.0]=8.0, align:enum{left|right}=left, marks_s:number[0.2..4.0]=1.1, leave_s:number[0.1..2.0]=0.5
- example (the defaults; replace ALL of its data): {"rows":[{"label":"An ordinary gown","value":"600","units":"pelts","count":12},{"label":"This gown","value":"2,000","units":"pelts","count":40,"at":2.9}],"caption":"each dot is fifty squirrel pelts","source":"Source: the sample narration of the Arnolfini video"}
- length: usually 7.0s (min 3.0, max 20.0)

### X-LAY-01 Stills sequence with fixed holds  [base]
- used as: a shot (the `technique` of a shot); intents: context, structure
- serves: outside
- use when: The sentence is about a person, a place, an object, an event or a custom that is NOT in the painting, and the picks of the beat hold a picture of that thing: a portrait of the king, a view of the cathedral, a coin, an old print of the harbour. The picture fills the frame for most of the beat at its default fit (the whole picture as large as the frame allows, drifting very slowly), then the painting returns.
- needs: The picture of the thing itself (or one made in its time) in the picks of the beat, role `context`.
- never when: The picture is not of the thing the sentence is about (a stock picture of something near it, a street map of a town that is only mentioned); the beat has no outside picture (stay on the detail the picks give and use no device to fill the gap); a camera that shows the picture small: it is shown at its default fit and the compiler puts it back, and a picture whose long side is under 1000 px is never enlarged beyond twice its size and then sits on the matte.
- real sentence: St. Eligius b0012: "He became personal adviser to the Merovingian King Dagobert." (the portrait of King Dagobert)
- what: Several context stills follow each other, each held a fixed 4.0 s with a hard cut between them.
- slots: image*
- params: camera, shadow:bool=True
- length: usually 4.0s (min 1.0, max 10.0)

### LAY-01 Two panels  [base]
- used as: a shot (the `technique` of a shot); intents: compare, context
- serves: compare
- use when: The sentence compares a detail of the painting with another work: "Jan van Eyck painted such a mirror in his Arnolfini portrait". The two pictures sit side by side on the matte, each with a caption.
- needs: Both pictures: the other work in the picks of the beat, and the DETAIL of the painting that is compared, written as the `region` of the `left` slot (the compiler frames that region in its panel; with no region the panel shows the whole painting small and the detail is lost).
- never when: The other picture was not found (stay on the detail of the painting); two pictures that are not being compared; the comparison is with several works one after another (X-CMP-01).
- real sentence: St. Eligius b0045: "Jan van Eyck painted such a mirror in his Arnolfini portrait, and it is presumed to hold his own reflection."
- what: Two images or crops sit side by side on the matte with a gap, each with a caption.
- slots: left*, right*
- params: camera, camera, caption_left:string=, caption_left_sub:string=, caption_right:string=, caption_right_sub:string=, panel_w_px:number[100..1900]=900, panel_h_px:number[100..1080]=740, panel_y_px:number[0..900]=36, left_x_px:number[0..1900]=50, right_x_px:number[0..1900]=970, slide_delay_s:number[0..10]=0.1, slide_s:number[0.1..5]=0.85
- length: usually 5.0s (min 2.0, max 60.0)

### AN-03 Perspective rays  [overlay]
- used as: an overlay (inside the `overlays` of a shot); intents: explain_mechanism, point_at
- serves: construction
- use when: The sentence makes a claim about depth, perspective or lines that do or do not meet: "their angles suggest the painter did not know the new laws of perspective", "every line leads to the two central figures". White lines are drawn one by one from the edges the claim is about toward the point where they meet, or fail to meet, then they vanish.
- needs: The edges the lines follow, taken from the picture itself (the edges of the shelves, the floor tiles, a window frame) and the vanishing point as a point of the picture. The picture must show those edges.
- never when: The narration makes no claim about space; the lines would be drawn across things the narration does not name; a sentence that only says the room is narrow or deep.
- real sentence: St. Eligius b0043: "Look at the shelves behind the saint. Their angles suggest the painter did not know the new laws of perspective from Florence. He was still experimenting with space." (the finished video used only a camera move here)
- what: White lines converge on a vanishing point, appear one by one, then vanish.
- slots: image*(region ok)
- params: vanishing_point:point*, origins:points, origin_space:enum{frame|source}=frame, ray_count:number[1..20]=9, stagger_s:number[0.0..1.5]=0.35, each_draw_s:number[0.1..2.0]=0.45, line_px:number[1..10]=4, color:color=#ffffff, opacity:number[0..1]=0.9, fade_s:number[0.0..2.0]=0.4, dim_base:number[0.1..1.0]=0.8, dim_ramp_s:number[0.0..3.0]=0.3
- length: usually 6.0s (min 3.0, max 25.0)
```

## 6. What the contact sheet showed

Two sheets of 13 stills, drawn by the engine on the pictures of `projects/technique_lab` (`tests/engine/catalogue_stills.py`, run in the snapshot): `.scratch/catalogue/sheet/sheet_1.jpg` and
`sheet_2.jpg` (in the worktree); both opened with the Read tool. All 26 drew, with no validation error. Each does what its `use_when` says:

| technique | what the still showed |
|---|---|
| CAM-01 | the camera inside the mirror's surroundings, frame filled (after the compiler's region camera; the engine's bare default stayed small between bars) |
| CAM-05 | the move ends on the joined hands |
| CAM-03 | ends on a wide band that fills the screen's width |
| CAM-04 | a glide up the two figures, the picture filling the width |
| STATIC-01 | the whole painting small on the matte (what rule 13 budgets) |
| X-ANN-01 | the strip AMBER BEADS over the close view |
| AN-01 | one thin ring around one small roundel of the mirror frame |
| HI-01 | spotlight on the chandelier with a wide frame; at `floor` 0.6 the dimming is gentle |
| KEY-01 | four labels beside their parts, none touching another |
| DOC-01 | the window lit on the signature, the reading and the original under it |
| AN-03 | nine white lines from the edges to one point |
| AN-06 | a thirds grid and a translucent triangle |
| AN-05 | both measuring lines with 59.7 cm and 82.5 cm and the medium caption (first still: the width number was cut off at the top edge: tightened) |
| X-ANN-03 | three plain words beside their details over the whole painting |
| X-LAY-01 | the outside portrait at its default fit, centred on the matte |
| X-ANN-02 | the two-line strip with title, maker and year over the outside picture |
| LAY-01 | the mirror detail beside the Paele altarpiece with two captions (first still: the whole painting small on the left: fixed in the compiler) |
| X-CMP-01 | the mirror detail on the left, another work on the right (same first finding, same fix) |
| FOOT-01 | the clip full frame with its label |
| STATE-01 | the same crop in its infrared-style state with the state's name |
| MAP-01 | Lübeck and Bruges with a dotted route on an atlas plate |
| TIME-01 | an axis with three dates, 1444 accented |
| NUM-01 | 600 and 2,000 pelts with rows of dots over the picture of the fur |
| STATIC-09 | a year on a calm dark part of the portrait (first still: over a busy part it was hard to read: tightened) |
| TREE-01 | three names with the ties drawn between them |
| TR-01 | two pictures overlapping in the middle of a dissolve |

None failed to draw. Not shown by a still: motion (the camera moves, the ring is drawn, the labels fade in); the stills are single frames chosen at the moment the effect is complete.

## 7. What the checks flag on the real St. Eligius storyboard

The `kinds` of the 61 lines, made by hand from the narration (`ELIGIUS_KINDS` in `tests/engine/real_docs.py`; the old picks have none), then `storyboard.validate` on the stored storyboard:

```
b0001: detail  b0002: detail  b0003: whole+detail  b0004: detail
b0005: whole  b0006: detail+outside  b0007: outside  b0008: outside+journey
b0009: detail  b0010: detail  b0011: detail+outside  b0012: outside
b0013: outside  b0014: outside+journey  b0015: outside  b0016: detail+outside
b0017: detail+idea  b0018: whole  b0019: detail  b0020: outside
b0021: outside  b0022: idea  b0023: detail  b0024: detail
b0025: idea  b0026: detail  b0027: outside  b0028: figure
b0029: outside  b0030: figure  b0031: detail  b0032: detail
b0033: detail+outside  b0034: detail  b0035: outside  b0036: outside
b0037: detail  b0038: detail  b0039: idea  b0040: detail
b0041: detail  b0042: outside  b0043: construction  b0044: detail
b0045: compare  b0046: outside  b0047: idea  b0048: inscription
b0049: dates  b0050: detail  b0051: idea  b0052: idea
b0053: detail  b0054: outside  b0055: outside  b0056: outside
b0057: outside+journey  b0058: whole  b0059: whole  b0060: whole+idea
b0061: outside
```

With these `kinds` and the old picks the checks flag exactly the three one-place maps of the owner's list, each twice (wrong kind and too little), and nothing else
(`tests/engine/test_catalogue_real.py`, positive and negative):

| code | shot | line | message (English, as the model reads it) |
|---|---|---|---|
| `device_wrong_kind` | s0024 | b0011 | MAP-01 in shot s0024 is drawn on line b0011, whose kinds are detail, outside, but it serves only a line of kind journey. Use a device only on a line whose kinds call for it (MAP-01: journey; TIME-01: dates; NUM-01: figure; DOC-01: |
| `device_too_little` | s0024 | b0011 | MAP-01 in shot s0024 has 1 places but needs at least 2 (or a route). Remove the device or give it what it needs: a map needs two places or a route (for one place show the picture of the place), a time axis three dated events (for  |
| `device_wrong_kind` | s0054 | b0027 | MAP-01 in shot s0054 is drawn on line b0027, whose kinds are outside, but it serves only a line of kind journey. Use a device only on a line whose kinds call for it (MAP-01: journey; TIME-01: dates; NUM-01: figure; DOC-01: inscrip |
| `device_too_little` | s0054 | b0027 | MAP-01 in shot s0054 has 1 places but needs at least 2 (or a route). Remove the device or give it what it needs: a map needs two places or a route (for one place show the picture of the place), a time axis three dated events (for  |
| `device_wrong_kind` | s0102 | b0055 | MAP-01 in shot s0102 is drawn on line b0055, whose kinds are outside, but it serves only a line of kind journey. Use a device only on a line whose kinds call for it (MAP-01: journey; TIME-01: dates; NUM-01: figure; DOC-01: inscrip |
| `device_too_little` | s0102 | b0055 | MAP-01 in shot s0102 has 1 places but needs at least 2 (or a route). Remove the device or give it what it needs: a map needs two places or a route (for one place show the picture of the place), a time axis three dated events (for  |
| `figure_on_wrong_picture` | s0056 | b0028 | The large figure of shot s0056 is laid over 'A Goldsmith in his Shop', but the picks of line b0028 hold the picture of the thing counted (caravel_view). Put the large figure over the picture of the thing counted (the outside pictu |

* The three maps are shots `s0024` (2:26, "born at Limoges", line b0011), `s0054` (5:36, Bruges, b0027) and `s0102` (11:04, Switzerland, b0055). The maps that tie two places are NOT flagged: `s0018` Lübeck to Bruges (b0008, kinds outside + journey), `s0029` Noyon and Bruges (b0014), `s0107` Bruges to Antwerp with a route (b0057); neither is the time axis `s0092` (three dates, b0049).
* **The figure over the saint** (`s0056`, 5:48, line b0028, 42 ships): none of the brief's four checks can flag it, because the old picks have no line for b0028 at all (the line is one of the six with no picks entry) and the kinds say `figure`, which NUM-01 serves. The rule "the picture under a large figure is the thing counted" needed a check of its own: `figure_on_wrong_picture` raises it as soon as the picks of the line hold a picture of the thing counted. In the table above that picture is a hand-made `caravel_view` item added to b0028 (what the pictures step would now find); without that item the figure is not flagged (6 flags, the maps only). I say so plainly: with the old picks alone the figure is not caught.
* `outside_on_painting` and `outside_picture_small` flag nothing on this video: its five outside pictures (Dagobert, shark teeth, mirror, Head of Christ, the Met) are shown for most of their lines and at the default camera.

## 8. Stored storyboards stay valid and draw as before

* `validate` of both real storyboards (stub pictures of the declared size) gives the very issues it gave before the change: `tests/engine/fixtures/catalogue/issues_before.json` was taken from the unchanged code before any edit; arnolfini: `project_name_differs` (the fixture folder name) and `audio_missing`; eligius: `audio_missing`; no error (`test_catalogue_real.py`).
* The middle frame of every shot, 115 of St. Eligius and 113 of the Arnolfini, drawn with the real main painting and the real pictures of `output\<key>\4_pictures` (the others as flat stubs), has the same sha256 before and after: 228 of 228 identical (`tests/engine/real_docs.py frames`; the baseline was taken on the unchanged code, then again after all the changes of this task). The Arnolfini uses hidden `STATIC-04` (3 times), `X-HI-01`, and both videos the program's `ID-*` techniques.
* A re-draft that copies the stored shots of a real video unchanged (decompiled specs, compiled with the identity applied) raises no `technique_not_offered` (`tests/draft/test_catalogue_compile.py`).

## 9. Decisions where the brief was silent

1. **Field shapes.** `offered` is a boolean on every entry; `hidden_reason` is an object `{code, use, note}` (`code` one of the five, `use` the offered ids to use instead, `note` one plain sentence); `serves` is the list of kinds, the first being where `techniques.md` lists the technique. The JSON schema was changed for them (not in your list of files, but the schema fails without it: `offered` is required; an offered entry needs the four texts, a hidden one a reason).
2. **The 60 reasons** are mine; see the table. `program`: the 8 identity techniques, `X-CARD-01`, `X-CARD-02`, `TXT-01` (old cards, replaced by the channel-name beat and the chapter marks) and `X-TR-01`, `TR-04` (the hard cut is the default). `X-CARD-03` (end credit) and `X-CARD-04` (white question card) are `other_format`, because nothing writes them. Effects of one episode of the reference channel that no kind of line calls for (`LAY-06`, `LAY-08`, `AN-07`, `STATIC-07`, `TXT-02`, `CMP-04`) are `other_format`. Techniques that need a picture-specific diagram (`DIA-01`, `DIA-02`, `DIA-07`) are `no_material`.
3. **Fast edit.** The reduced catalogue of the prompt box lists only offered techniques plus those on the scope's shots (a hidden technique the shot already has stays listed, so the model can change its parameters), with `use when` and `never when`. A typed batch that names a hidden technique is refused before the dry run with the existing code `unknown_technique` and the sentence that names the replacement (`bti/ops/errors.py` is not mine, so no new code); a technique the shot already has is never refused. `fastedit.py` and `boxops.py` are not in your list: marked blocks of 3 and 40 lines.
4. **What counts as stored.** `technique_not_offered` is not raised for a technique the saved storyboard already has on the shot of the same id (the shot, one of its overlays, its transition). A re-draft copying a stored shot unchanged is verbatim and not rebuilt at all. In a proposal run (`degrade`) a shot that names a hidden technique is replaced by a plain push-in and listed in `degraded`, like a Shorts-only technique; an overlay is dropped; a transition is refused with the shot.
5. **The kinds of a beat** come from the project's `picks.json` (`beats[<id>].kinds`, the contract of the pictures brief) and the beats' times from the timing's `beats`. A device belongs to the beats it shares at least 1 s with (or half of itself when shorter); it is wrong only when none of those beats calls for it; when any of those beats has no `kinds` nothing is judged. Unknown words are no kinds.
6. **"Outside picture".** For `outside_on_painting`: an item of role `context`, `document` or `video` of a line of kind `outside` (a `map` is drawn by MAP-01 and a `compare` picture is another work, so neither counts; a line with status `skip` or with no such item, that is a picture that was not found, is silent); it is "on screen" in any slot of any shot overlapping the line. For the fit and the compiler: every picture used by a `context`, `document`, `video`, `compare` or `map` item and never by a `main` or `detail` item, and not the main asset.
7. **Default fit** = the zoom at which the picture fills the frame's height or width, `min(1920 / w, 1080 / h)`; a picture whose long side is under 1000 px is held to `zoom` 2. `outside_picture_small` fires under 80 % of it (on shots with a `camera` parameter whose primary picture is an outside one).
8. **The repair.** A camera of the model that shows an outside picture under 80 % of its fit, or a small picture past `zoom` 2, is replaced by the technique's default camera and the compiler says so with the warning `outside_camera_refit`. When the model wrote no camera, the compiler's own default for a small outside picture is held to `zoom` 2 without a message (the engine's X-LAY-01 default would be 2.5 for a 600 x 400 picture).
9. **The fifth check**, `figure_on_wrong_picture` (section 7). It needs a line of kind `figure` whose picks hold an outside picture, and a NUM-01 laid over another picture.
10. **A region in the panel** (found on the contact sheet): the compiler now frames the `region` of the `left`/`right` slot of LAY-01 and of the `anchor` slot of X-CMP-01 in its panel (about 80 % of the panel), unless the model wrote its own `camera_left`/`camera_right`/`camera_anchor`. Without it the use case "compares a detail" was not what the viewer saw.
11. **`techniques.md`.** The usage class (core, occasional) is dropped from the headings (it is the reference channel's habit and misled: "KEY-01 core: the channel uses it all the time"); the index by intent is replaced by an index by kind that also says the `intent` to write for that kind; the label of the real sentence is `real sentence` (not `example`, which the tests parse for the defaults line). The program's techniques are listed last in a short section (one entry each, no parameters).
12. **Hand-made kinds** for the proof are for all 61 lines, not only those with devices: a device that overlaps a line without kinds is not judged.
13. **Generated docs.** `docs/AGENT_API.md` (section 9, the storyboard row) is generated by `python -m bti.editor.hints` from `bti/auto_run/checks.py`; I regenerated it (one line). `python -m bti.cli.docgen --check` passes. The other worker `linekinds` also edits `STOPS` (the picks gate): regenerate that line after merging.
14. **Test pins.** The old tests pinned sentences that the brief deletes ("ANY place", "6 to 12", "street-map tiles", the intent index, `- when:`) and sizes; they were rewritten to the new text, and the size bounds raised with the reason in each docstring (the draft task 27,252 to 31,200 bytes, the fast briefing 9,355 to 9,950, the fast catalogue of a whole video +1,500 characters).

## 10. Tests

Python, on the server, snapshot `catalogue`, one folder per run (never `-m slow`), the last line of pytest exactly as printed:

| folder | last line |
|---|---|
| `tests/engine` | `883 passed, 14 skipped in 2699.31s (0:44:59)` |
| `tests/auto` | `212 passed, 1 warning in 82.97s (0:01:22)` |
| `tests/identity` | `88 passed in 1.97s` |
| `tests/editor` | `508 passed, 1 warning in 232.83s (0:03:52)` |
| `tests/state` | `302 passed, 1 warning in 181.30s (0:03:01)` |
| `tests/cli` (final run) | `130 passed, 1 warning in 47.09s` |
| `tests/draft` (final run, on the final tree) | `483 passed, 1 warning in 158.79s (0:02:38)` |

* `tests/cli` failed once, `test_every_name_in_code_ticks_is_a_word_the_app_has` (`1 failed, 129 passed, 1 warning in 42.16s`): my new paragraph of `skills/storyboard/SKILL.md` put snake_case words in code ticks that no document or registry of the app has; I reworded it and the folder passed.
* `tests/draft` was also run earlier in the work (`480 passed`, then `483 passed in 156.68s` on the tree before the last two small edits: rule 14 of the task, the SKILL.md wording).
* `python -m bti.cli.docgen --check`: exit 0, nothing stale. `python -m bti.editor.hints --check` (the generated part of `docs/AGENT_API.md`): exit 0 after I regenerated one line.
* JavaScript, on the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs tests/output/*.test.mjs` printed `ℹ tests 470`, `ℹ pass 469`, `ℹ fail 0`, `ℹ skipped 1` (the skipped one needs `.venv/bin/python`; I ran its comparison of `ISSUE_CODES` with the sentences by hand: 153 codes, none missing, none extra). `node --check bti/editor/static/js/errmsg.js`: ok.
* New or rewritten tests: `tests/engine/test_catalogue_registry.py` (18), `test_viewchecks_kinds.py` (44), `test_catalogue_real.py` (9), `tests/draft/test_catalogue_compile.py` (29), `tests/editor_frontend/catalogue.test.mjs` (10).

## 11. What I could not verify, and what other workers must do

* No model was called: I could not see how a model reads the new `techniques.md` and task, nor whether it follows the kinds. The first real run is the test.
* The checks of kinds were exercised on made-up storyboards and on St. Eligius with hand-made kinds; no real `kinds` written by the pictures step were available (the branches are not in this worktree). They read `picks.json` `beats[<id>].kinds` and the item roles; if `linekinds` stores them elsewhere, `viewchecks._beat_rows` is the one place to change.
* **Needs another worker (`bti/draft/workspace.py`, not mine):** the model's own `check` helper runs inside the workspace, whose folder has no `picks.json`, so the five viewer checks of kinds are silent THERE (`technique_not_offered` and the camera repair are not: they use the picks in `compile_input.json`). They do run in the server-side compile of the draft, at the storyboard gate and in `storyboard.validate`. Writing the picks document (with `kinds`) into the workspace root would also switch on `asset_not_in_lines` inside the helper. One line in `build()`.
* **Needs another worker (`bti/ops/errors.py`):** a code `technique_not_offered` for typed batches (I reused `unknown_technique`).
* The Vietnamese sentences were tested as text (node) and not looked at on the page; the test of `sbissues.test.mjs` that compares `ISSUE_CODES` with the sentences is skipped on the Mac (no `.venv`); I ran its comparison by hand (153 codes, none missing, none extra).
* FOOT-01 was drawn on the lab's clip, which is a still-like clip of the same painting: its motion and its sound were not judged.

