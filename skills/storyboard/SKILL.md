---
name: bti-storyboard
description: Step 5 of Behind the Image, the storyboard (a draft by a model, then typed operations on shots and overlays). Use when `bti status <project>` shows the step `edit` as current.
---

# Step 5: the storyboard (`edit` in `bti status`)

Read `AGENTS.md` first (the rules, the exit codes). This document is for the step called `edit` in the status and `storyboard` for its gate and for `bti doc storyboard`.

## Goal

A storyboard that the owner (or you, when allowed) approves: a list of shots, each with a technique, the picture it shows, a camera move and, where the narration calls for it, overlays on top.
The engine draws exactly what the storyboard says; it never decides.

## What it needs and what it gives

- Needs: the voice done (`timing.json`) and the picks approved. The first storyboard of a project is a **draft** made by a model.
- Gives: `storyboard.json` (shots, overlays, regions, a `locked` flag per shot) with the revision the operations use, a copy of every earlier save in `history/`, the change log of your batches, and the gate `storyboard` that unlocks the export.
- Every edit that is not a draft goes through `bti ops <project> storyboard` (typed operations, all or nothing, with a dry run and an undo). You never write the file.

## The actions and operations it uses

<!-- BEGIN GENERATED: actions -->
The visual path composes the approved visual script and reviews its moments; the legacy path uses a model draft and proposal. Both paths keep hand operations and the storyboard gate.

| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `storyboard.compose` | edit | Dựng storyboard |  |  |  |
| `draft.start` | edit | Dựng bản nháp |  | model: about 20 minutes | yes |
| `proposal.apply` | edit | Áp dụng |  |  |  |
| `storyboard.restore` | edit | Khôi phục bản gần nhất |  |  |  |
| `storyboard.validate` | edit | Kiểm tra |  |  |  |
| `storyboard.retime` | edit | Khớp lại với giọng đọc |  |  |  |
| `storyboard.review` | edit | Xem lại storyboard |  | model: about 10 to 15 minutes plus any repairs | yes |
| `storyboard.approve` | edit | Duyệt storyboard | yes |  |  |
| `storyboard.preview` | edit | Xem thử |  |  | yes |
| `storyboard.put` | edit | Lưu storyboard |  |  |  |
| `storyboard.ops` | edit | Sửa storyboard |  |  |  |
| `changes.list` | edit | Lịch sử thay đổi |  |  |  |
| `changes.undo` | edit | Hoàn tác |  |  |  |
| `draft.edit` | edit | Nhờ agent sửa |  | model: from about 30 seconds to about 20 minutes | yes |
| `identity.set` | edit | Chọn kiểu mở đầu |  |  |  |
| `draft.cancel` | edit | Dừng |  |  |  |
| `visual.edit` | edit | Sửa kịch bản hình |  | model: several minutes and picture search | yes |
| `visual.review` | edit | Xem lại video |  | model: about 10 to 15 minutes plus repairs | yes |
<!-- END GENERATED: actions -->

The first storyboard: `draft.start` (a model works in a scratch folder for about 20 minutes and writes a **proposal**; the app compares the project before and after and drops the result if anything else changed; `--set note="..."` gives the model the owner's wish for this draft, up to 600 characters, for example "fewer close-ups": add it only when the owner said something, and never put a rule of this document in it),
then `proposal.apply` (`{"accept": "all"}` for the first draft; the proposal id is in the path the status shows). Later changes in words, for the owner's kind of request ("zoom more slowly into the mirror"), are
`draft.edit` (`--set instruction="..." --set 'scope={"shots":["s0012"]}'` or `{"chapter": "c02"}` or `{"all": true}`); for exact changes use the operations:

<!-- BEGIN GENERATED: ops -->
| operation | what it does |
|---|---|
| `set_technique` | Change the technique of a shot. Parameters not given take the defaults of the new technique (the same as POST .../defaults); slots that still fit are kept; the shot's note (the reason written for the old treatment) is cleared. |
| `set_params` | Change some parameters of a shot or of one of its overlays. A value of null returns that parameter to its default. |
| `set_slot` | Put an asset into a slot of a shot or overlay (or empty the slot with asset null). When the main picture of a shot changes, its camera keys are fitted to the new picture the way the page does and its note (the reason written for the old picture) is cleared. |
| `add_overlay` | Add an overlay (a ring of light, a label, an arrow...) to a shot. Parameters not given take the defaults of the technique; it starts at the start of the shot and, when dur and end are left out, HI-01 runs to the end of its shot while others last 3 s. A length past the end of the shot is cut to the shot. |
| `set_overlay` | Change an overlay of a shot: its technique (parameters then take the new defaults), start, duration or end (cut to the shot if past its end), intent or note. Use set_params for its parameters. |
| `remove_overlay` | Remove an overlay from a shot. |
| `split_shot` | Cut a shot in two at a time. Each half keeps the camera pose it had at that time and the overlays go to the half they start in (an overlay that crosses the cut is shortened), as when the page cuts. |
| `merge_shots` | Merge shots that follow each other into the first of them: it keeps its camera poses over the time it had, takes the overlays of the others and lasts until the end of the last. |
| `move_boundary` | Move the cut where a shot begins to another time: the shot before it gets longer or shorter by the same amount. Overlays that no longer fit their shot are shifted or shortened, as when the page moves a cut. |
| `replace_range` | Replace a run of consecutive shots by new shots that cover exactly the same span of narration (the shape the fast edit produces: shots changed or added, others removed). The first new shot starts where the run starts; the others start inside it. |
| `lock` | Lock a shot (or one overlay of it): every operation on it is refused until it is unlocked, whoever sends it. |
| `unlock` | Unlock a shot (or one overlay of it). The only operation a locked shot accepts; unlocking something that is not locked changes nothing. |
<!-- END GENERATED: ops -->

`bti schema ops storyboard` prints the fields and an example of each. A time is a number of seconds or a narration word `{"w": 154}`; `ref` names something a batch creates so that a later operation of the same batch can say `"$name"`.
A locked shot refuses every operation except `unlock`; `lock` what the owner has settled. The style of the opening and of the chapter marks is chosen with `identity.set` (`--set style=raking` or `dim`), never by editing shots.

The catalogue of techniques, under its headings (a shot takes a `base` or `card` technique, an overlay an `overlay` one, a transition goes in `transition_in`):

<!-- BEGIN GENERATED: techniques -->
| heading | techniques (id, name) |
|---|---|
| annotation | `AN-01` Circle draw; `AN-02` Object outline; `AN-03` Perspective rays; `AN-04` Map circle and arrow; `AN-05` Dimension ruler; `AN-06` Grid and geometric regions; `AN-07` Dot field densifying; `KEY-01` Labels as a key to parts of a picture; `NUM-01` Big number with a comparison; `X-ANN-01` Name label strip; `X-ANN-02` Artwork label (two lines); `X-ANN-03` Recap labels at closing; `X-ANN-04` Sequential group outlines; `X-ANN-05` Map point markers one by one |
| camera | `CAM-01` Push-in; `CAM-02` Layered relative motion; `CAM-03` Pull-back; `CAM-04` Pan up; `CAM-05` Zoom and shift; `CAM-06` Hold and label reveal |
| card | `ID-BRAND-01` Channel name written by light; `ID-BRAND-02` Channel name on a dimmed picture; `ID-BRAND-03` Channel name and video title written by light; `ID-BRAND-04` Raking light sweep over relief onto detail; `ID-MARK-01` Chapter mark written by light; `ID-MARK-02` Chapter mark on a dimmed picture; `X-CARD-01` Chapter card on black; `X-CARD-02` Main title card; `X-CARD-03` End credit; `X-CARD-04` Question card on white |
| compare | `CMP-01` Grey and colour scan side by side; `CMP-02` Stages versus finished; `CMP-03` White and colour versions; `CMP-04` Colour blocks beside detail; `CMP-05` Two colour states; `STATE-01` The same picture in two states; `X-CMP-01` Swap one side of a split; `X-CMP-02` Wipe compare |
| diagram | `DIA-01` Grid and projection rays; `DIA-02` Two views of one object; `DIA-03` Cross-section and light rays; `DIA-04` Figure and separated pieces; `DIA-05` Process silhouette; `DIA-06` Room model and UV image; `DIA-07` Eye and vision diagram; `TIME-01` Time axis with dates; `TREE-01` Relations: family and patrons |
| footage | `FOOT-01` Material footage and palette |
| highlight | `DOC-01` A lit line of a document; `HI-01` Spotlight; `HI-02` Progressive figure reveal; `HI-03` Colour kept on subject; `ID-OPEN-01` Opening: raking light; `X-HI-01` Dim to isolate then restore |
| layout | `LAY-01` Two panels; `LAY-02` Four-tile grid; `LAY-03` Five-column comparison; `LAY-04` Inset window; `LAY-05` Subject held, background changes; `LAY-06` Translucent vertical strips; `LAY-07` Grid with translucent object; `LAY-08` Repeated symmetric motif; `X-LAY-01` Stills sequence with fixed holds |
| shorts | `SHORT-01` Three horizontal strips; `SHORT-02` Changing view; `SHORT-03` Large type changes; `SHORT-04` Yellow label box; `SHORT-05` Colour wheel from palette |
| static | `MAP-01` Atlas map; `STATIC-01` Black matte; `STATIC-02` Source label; `STATIC-04` Quote over image; `STATIC-05` Interviewee tag; `STATIC-06` Map with route; `STATIC-07` Multi-cell circular diagram; `STATIC-08` Name labels on figures; `STATIC-09` Year centred on image |
| text | `ID-LABEL-01` Artwork label without a strip; `ID-OPEN-02` Opening: dim and name; `TXT-01` Chapter title on blurred image; `TXT-02` Sliding italic text |
| transition | `TR-01` Dissolve; `TR-02` Image slide in/out; `TR-03` Panel opening; `TR-04` Full-to-crop hard cut; `X-TR-01` Hard cut; `X-TR-02` Strip slides in, then splits |

87 techniques in 12 headings; `bti` does not list their parameters: GET /api/styles/{style} does, and `bti schema ops storyboard` shows how `set_technique` and `set_params` take them.
<!-- END GENERATED: techniques -->

## A worked session

Fixture project `ops1` (ten shots `s0001` to `s0010`, `s0006` locked). The ids and the numbers come from the fixture; read yours from the project.

```text
# fixture: ops
$ bti do ops1 storyboard.validate
ok: storyboard.validate: 0 error(s), 3 warning(s)
$ cat > ops.json <<'EOF'
[{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 260}},
 {"op": "lock", "shot": "s0003"}]
EOF
$ bti ops ops1 storyboard --file ops.json --dry-run
dry run: nothing was written; 2 operation(s) applied; revision <rev>
changes:
...
$ bti ops ops1 storyboard --file ops.json
batch batch_0001 written; 2 operation(s) applied; revision <rev>
changes:
...
undo: bti undo <project> batch_0001
$ bti changes ops1 storyboard
batch        doc         actor                 time                 note
batch_0001   storyboard  cli:bti               <time>
...
$ bti approve ops1 storyboard
a person is needed: gate_needs_human (HTTP 403)
  detail: The storyboard gate can only be approved by the owner: automatic running is off for this project.
  fix: Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate (the switch on the page, PUT /api/projects/ops1/auto), then call again.
(exit 3)
# owner: auto on
$ bti approve ops1 storyboard
approved storyboard as cli:bti
```

Approving is refused while the storyboard has errors (`storyboard_has_errors`), items that lack a picture, a clip or a mask (`storyboard_incomplete`) or a shot the engine cannot draw (`undrawable`); `storyboard.validate` lists them.
Any later change drops the approval: approve again and export again.

## What a good result is

Take these from `skills/storyboard_draft/TASK.template.md` and `skills/storyboard_edit/FAST.template.md` (what the draft and edit models are told), and from `docs/APP_GUIDE.md` (section 7).

- **Pacing.** The reference channel's median shot is about 7 seconds, one in ten is under 4 seconds, none is under 2.5 seconds, and a shot over 30 seconds is split with a move or a detail. A beat is usually one to three shots. A camera move under 3 seconds is a cut in disguise; over 20 seconds it needs a second event to stay alive.
- **The frame is full.** An upright painting shown whole is a small picture between two black bars (the main painting of 3840 px width fills the screen at `zoom` 0.5; under 0.3 it is that small picture). Show it whole for at most 5% of the video (30 seconds in ten minutes): the pull back that ends the cold open, one chapter opening and the last shot. Every other shot fills the screen: the painting at full width with a slow travel up or down, a wide band of it, or a detail. The first real draft had 41 of its 109 shots on the small picture and needed a request for each. Neighbouring shots never end and start on the same frame; the chapter marks and the channel-name beat take the pose of the shots beside them.
- **Introduce a visible name once.** At the first spoken introduction of an on-screen person, saint or thing, use `X-ANN-01` on the naming word and leave each line readable: 1.5 seconds for up to three words, 0.3 seconds per extra word, at most 4 seconds. A person’s strip stands alone; never spotlight a face or figure. A small thing also gets `HI-01`. Put the narration’s own shortened caution in `sub` for an uncertain identity, or leave it empty for a certain one (a plain fact from that sentence is also fine). On a borrowed picture the first line names the subject the narration names; the small line may add the work’s title, maker and date from its record, never the photographer or the year of the photograph. Do not add `X-ANN-02` on the same shot. For example, "The woman most often named as the wife in green is Costanza Trenta" gives COSTANZA TRENTA / most often named as the wife; "Some historians see Saint Martha" gives SAINT MARTHA / some historians see Saint Martha, with usable work metadata when available.
- **Light every small named detail.** Use `HI-01` on the thing itself even in consecutive or near shots. Measure a tight region with `./crop` if needed. Begin on its word and continue to the shot end, at least 2.5 seconds; leave the thing below about 40% of the frame width and height. A strip naming it accompanies the light. Keep its centre 5% inside the frame and `floor` / `surround_floor` at least 0.6. Use a ring instead only for one of several similar objects so close that one pool of light would cover them all. Do not light the opening or channel-name beat, the whole picture, a face or figure, or something outside the painting; do not use two spotlights at the same moment or a ring on the same thing.
- **Text on the screen is true and tidy.** A date, figure, place, name or map label comes from the narration (a spelled number counts); a caption is the narration's word, the picture's own title or nothing, never a placeholder ("UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950"), a note to the reader ("Source: an estimate cited in the narration") or the same words twice. A `MAP-01` carries no `region_label`, `region_iso` or `sea_names` that the narration does not name. No map, time axis, tree or two-state picture in the first 30 seconds: the painting is on screen as the viewer arrives.
- **Only pictures that a line has.** A picture the owner took out of every line stays in the project but must not be used again (the draft is not offered it); a small one (long side under 1000 px) is shown no larger than its pixels allow.
- **The owner's picks first.** The pictures the owner chose for a line are what its shots show. A line with none stays on the main painting and moves (zoom in, go to a detail, pull back); never hold a still for more than one shot in a row.
- **A line about something outside the painting needs a picture outside the painting.** A person, a place, a document or another work is shown with the picture the picks give it (`context`, `document`, `compare`, `map`), not with the painting held; if the picks give none, go back to step 4 and ask for one rather than filling the time.
- **Explanatory devices only where the narration makes that point.** `MAP-01` (a place, a journey, a territory: use it instead of the three older map techniques), `TIME-01` (dated events), `TREE-01` (who is related to whom), `KEY-01` (names for parts of the picture), `NUM-01` (a figure or two figures compared), `STATE-01` (the same picture in two states), `DOC-01` (one line of a document, lit). Tie every item to the word that names it (`at: {"w": 154}`); take dates, places, figures and relations only from the narration and the project's sources, and leave an item out when unsure. About 6 to 12 in a ten-minute video, never two in a row, none through general talk: most lines are served better by a camera move.
- **Move toward the thing as it is named.** Start the shot a word before the detail's name; end a spotlight or ring when the sentence moves on; after a detail come back to the painting.
- **Prefer the core techniques**; use occasional and rare ones where a line clearly calls for them; never a technique of the `shorts` heading (they are for Shorts). Do not use the same technique four times in a row.
- **Never put the narration on screen.** Labels are one to five words of your own ("Latin inscription"); no parameter holds a sentence of the narration. The video has no burned-in subtitles.
- **The channel identity is the program's.** The `ID-*` techniques (the opening, the channel-name beat, the chapter marks) are written by the compiler: never add one, never write a title card or a chapter card. Change their style with `identity.set`. The video starts with the program's opening shot (`s0000`: the whole painting before the first word, when the first word starts at 3.3 s or later); never write or change it, and never start the model's first shot with a still view of the whole painting. The title shown under the channel name is the field `video_title` of the storyboard's `identity` object (`identity.set` with `--set video_title="..."` besides `style`; one line, at most 90 characters).
- **After the voice was made again, fit the storyboard to it.** The cards, the channel-name beat and the end of the video are anchored by absolute time; when the voice is assembled again (another silence before the first word or before the title, or one sentence read again) every word moves and they do not. `bti status` then lists `storyboard.retime` ("Khớp lại với giọng đọc") as the next command: run `bti do <project> storyboard.retime`. It moves what is off, puts the opening shot in (or takes it out), sets the end and applies the identity again; it changes no shot of the model or the owner (except the start of the shot after the opening shot), leaves locked shots and a wrong number of cards and says so (`report.left`), costs nothing and is one batch you can `bti undo`. Until it is done `storyboard.approve` and `export.start` are not ready and the routes refuse with `storyboard_off_voice`. The automatic run does it by itself before the gate.
- **Respect locks and scope.** Never touch a locked shot; a batch with a `scope` that an operation leaves is refused whole (`out_of_scope`).

## The warnings of `storyboard.validate` that are the owner's rejections

None of these blocks a save or the approval, but an automatic run stops at them (`quality_warning`, `docs/AGENT_API.md` section 9) and the owner rejects the look. Each issue says what is wrong and what to do; the numbers are estimates from the shot's camera, the picture's size and the parameters (nothing is rendered).

| code | what it means | what to do |
|---|---|---|
| `upright_whole_share` | The main painting covers under 60% of the screen for more than 6% of the running time (a clip under a minute is never judged). `args`: `share`, `seconds`, `count`, `worst` (the shots). | Give those shots a framing that fills the screen (`set_params` with a `camera` at `zoom >= 0.6 x 1920 / width`, the painting at full width travelling up or down); keep the whole painting for the cold open's pull back, one chapter opening and the last shot. |
| `highlight_off_frame` | The lit spot of an `HI-01` or `X-HI-01` is at the edge of the frame (nearer than 5%) or outside it at some moment of its window. | Move the camera so that the region stays inside (`set_params` `camera`), or use a tighter region. |
| `small_detail_not_lit` | A small named detail has no pointer. | Add a spotlight on a tight region of the detail. |
| `highlight_nothing_to_dim` | The lit ellipse covers too much of the frame. | End the camera wider or use a tighter region. |
| `text_too_brief` | Text is not fully visible long enough to read. | Start the shot or overlay earlier, or drop the text. |
| `highlight_too_dark` | A highlight leaves the frame nearly black. | Raise `floor` (`surround_floor` for `X-HI-01`) to about 0.6. |
| `caption_placeholder`, `caption_repeats` | On-screen text that is a placeholder, says `narration`, is only the picture file's artist and year under a caption of its own, or repeats words. `args.param` names it. | `set_params` the text to words from the narration, to the picture's own title, or to `""`. |
| `text_not_in_narration` | A figure, date, place, name or map label (`MAP-01` `region_label`, places, `sea_names`; `NUM-01` `value`; `TIME-01` dates; `STATIC-09` `year`; `DOC-01` `reading`; `TREE-01` names) that the narration never says; a year, title or artist of the shot's own picture is allowed. `args.missing` lists the words. | Use what the narration says, or `""` (for `sea_names` and `region_label`: off and empty). It does not see text inside a picture, the names a map draws from its own data, or free labels such as `X-ANN-01`. |
| `asset_not_in_lines` | A shot shows a picture that no line of the narration has (`picks.json`) and that is not the main painting. | `set_slot` the picture of a line of that part, or the main painting; do not add it to the lines again unless the owner asks (step 4). |
| `explainer_early` | A base explanatory shot (`MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`) starts in the first 30 seconds. | Show the dates as large figures on the painting (`STATIC-09` overlay) and move the diagram to a later chapter. |
| `device_wrong_kind` | A device (`MAP-01`, `TIME-01`, `NUM-01`, `DOC-01`, `AN-03`, `AN-06`, `TREE-01`, `LAY-01`, `X-CMP-01`) sits on a line whose `kinds` (the pictures step wrote them into `picks.json`) do not call for it: a map needs `journey`, a time axis `dates`, a figure `figure`, a lit line `inscription`, perspective lines and shapes `construction`, a tree `relations`, two panels `compare`. Judged only on lines that carry `kinds`. `args`: `technique`, `beats`, `kinds`, `needs`. | `remove_overlay` it (or `set_technique` the shot to a camera technique) and keep the picture the picks give. |
| `device_too_little` | A map with fewer than two places and no route, a time axis with fewer than three items, a key with fewer than three labels, a tree with fewer than three people. `args`: `technique`, `count`, `min`, `items`. | For one place show the picture of that place; for one or two dates use a `STATIC-09` year; for one or two names use `X-ANN-01`; or remove the device. |
| `figure_on_wrong_picture` | A large figure (`NUM-01`) lies over another picture although the picks of its line (kind `figure`) hold the picture of the thing counted. | Make the picture of the thing counted the base of that shot (`set_slot`), or remove the figure. |
| `outside_on_painting` | A line of kind `outside` has its outside picture in the picks (a `context`, `document` or `video` item) but the picture is on screen for less than 45% of the line (25% when the line has two kinds, because the picture then comes when the sentence reaches the thing) or for less than 3.5 seconds. `args`: `beat`, `seconds`, `share`, `limit`. | Put a shot of that picture (`X-LAY-01`; `FOOT-01` for a clip) at the start of the line; a line whose picture was not found (`missing`) is never flagged. |
| `outside_picture_small` | A picture that is not the painting is drawn under 80% of its default fit (the frame's height or width; a picture whose long side is under 1000 px is held to twice its size). `args`: `asset`, `zoom`, `fit`. | `set_params` the shot's `camera` to the default fit, or leave the camera out. |
| `frame_off_painting` | A camera key of a shot on the main painting shows more than 1% of its frame outside the painted area of the picture (`content_box` of the asset: a museum photograph of a panel has a black ground round the painting), and the frame does not hold the whole painting. `args`: `shot`, `key` (the camera key, from 0), `share`, `box` (`[x0, y0, x1, y1]` in pixels of the picture), `cx`, `cy`, `zoom`. The compiler moves or tightens such a key by itself when it compiles (and says so: the warning `frame_moved_into_painting`); a shot you changed with an operation, or a locked shot, is yours. | `set_params` the shot's `camera`: move the centre of that key away from the edge of the box, or zoom in; a frame that is a pull back on the whole painting (the box inside the frame) may show the ground. |
| `camera_off_region` | At the end of a main-painting shot pointing at a region, the region box extends outside the frame. | Name the right `region` on the shot (or enlarge/re-measure the region) so the compiler frames all of it. |
| `thing_arrives_late` | A named region is wholly inside the frame for less than 2 s and less than 55% of the shot. | Start closer (`from`), lengthen the shot, or keep the move on one region. |
| `shot_short` | A shot lasts under 2.5 seconds (tolerated by an automatic run: it is a flash, not a defect). | `merge_shots` it into the one before, or `move_boundary` its cut. |

## What a model is offered (the catalogue)

The registry (`style/gae/techniques.json`) holds 86 techniques, but a model that writes a storyboard is offered only 26 (the field `offered`): each says when to use it, what it needs, when never, and gives a real example sentence, and `inputs/techniques.md` lists them grouped by the kind of line they serve (the `kinds` of a beat, decided at the pictures step). The other 60 are hidden, each with a reason (the program writes it, it is for another format, it was replaced, it needs material the pipeline never supplies, or an offered technique does its job) and the offered technique to use instead. A draft or an edit turn that names a hidden technique is refused (the draft's check says so; a typed batch gets `unknown_technique`), and the message says what to use instead. The owner's own edits and the stored storyboards are never judged by this: a shot that already has a hidden technique keeps it and draws as before.

## The refusals you will meet

| code | what to do |
|---|---|
| `unknown_shot`, `unknown_overlay`, `unknown_asset`, `unknown_region`, `unknown_technique`, `unknown_param`, `unknown_slot` | The refusal lists `allowed` and the path of the wrong field (`ops[0].shot`): use one of them, or create the thing earlier in the batch and name it with a `ref`. |
| `locked` | `unlock` the shot first only if the owner said so; otherwise leave it out of the batch. |
| `validation_failed` | The result would have an error the save refuses: read `issues` (each names the operation by `op_index`), change that operation; nothing was written. |
| `wrong_technique_kind`, `technique_unavailable`, `slot_kind_mismatch` | Use a technique of the right kind that the engine can draw, and a picture of the kind the slot takes (image, video or mask). |
| `shot_too_short`, `not_consecutive`, `span_mismatch` | A cut would leave a piece under 0.2 seconds; `merge_shots` and `replace_range` take shots that follow each other and the new shots must cover exactly the old span. |
| `stale_revision` (exit 5) | The storyboard changed under you: send the command again (it reads the new revision). |
| `undo_conflict` | A later batch changed what you want to undo: undo the later batches first. |
| `draft_not_ready`, `voice_done`, `picks_approved` | The draft needs the voice and the approved picks: steps 3 and 4. |
| `draft_tampered`, `draft_no_output`, `compile_empty` | The draft agent's result was dropped: run `draft.start` again. |
| `edit_outside_scope`, `escalate`, `cannot`, `edit_no_change` | A request in words could not be met within its scope: narrow it, widen the scope, or do it with operations. |
| `storyboard_corrupt`, `storyboard_unreadable` | `storyboard.restore` brings back the newest good copy from `history/`. |
| `storyboard_has_errors`, `storyboard_incomplete`, `undrawable` | Fix what `storyboard.validate` lists, then approve. |
| `storyboard_off_voice` | The voice was made again and the cards, the channel-name beat or the end sit where the old voice put them: run `bti do <project> storyboard.retime`, then approve again. |
| `gate_needs_human` (exit 3) | The owner has not allowed you to approve this gate: stop and ask. |
