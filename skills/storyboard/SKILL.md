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
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `draft.start` | edit | Dựng bản nháp |  | model: about 20 minutes | yes |
| `proposal.apply` | edit | Áp dụng |  |  |  |
| `storyboard.restore` | edit | Khôi phục bản gần nhất |  |  |  |
| `storyboard.validate` | edit | Kiểm tra |  |  |  |
| `storyboard.approve` | edit | Duyệt storyboard | yes |  |  |
| `storyboard.preview` | edit | Xem thử |  |  | yes |
| `storyboard.put` | edit | Lưu storyboard |  |  |  |
| `storyboard.ops` | edit | Sửa storyboard |  |  |  |
| `changes.list` | edit | Lịch sử thay đổi |  |  |  |
| `changes.undo` | edit | Hoàn tác |  |  |  |
| `draft.edit` | edit | Nhờ agent sửa |  | model: from about 30 seconds to about 20 minutes | yes |
| `identity.set` | edit | Chọn kiểu mở đầu |  |  |  |
| `draft.cancel` | edit | Dừng |  |  |  |
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
| `add_overlay` | Add an overlay (a ring of light, a label, an arrow...) to a shot. Parameters not given take the defaults of the technique; it starts at the start of the shot and lasts 3 s unless said otherwise. |
| `set_overlay` | Change an overlay of a shot: its technique (parameters then take the new defaults), start, duration or end, intent or note. Use set_params for its parameters. |
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
| annotation | `AN-01` Circle draw; `AN-02` Object outline; `AN-03` Perspective rays; `AN-04` Map circle and arrow; `AN-05` Dimension ruler; `AN-06` Grid and geometric regions; `AN-07` Dot field densifying; `KEY-01` Labels as a key to parts of a picture; `NUM-01` Big number with a comparison; `X-ANN-01` Detail label strip (one line); `X-ANN-02` Artwork label (two lines); `X-ANN-03` Recap labels at closing; `X-ANN-04` Sequential group outlines; `X-ANN-05` Map point markers one by one |
| camera | `CAM-01` Push-in; `CAM-02` Layered relative motion; `CAM-03` Pull-back; `CAM-04` Pan up; `CAM-05` Zoom and shift; `CAM-06` Hold and label reveal |
| card | `ID-BRAND-01` Channel name written by light; `ID-BRAND-02` Channel name on a dimmed picture; `ID-BRAND-03` Channel name and video title written by light; `ID-MARK-01` Chapter mark written by light; `ID-MARK-02` Chapter mark on a dimmed picture; `X-CARD-01` Chapter card on black; `X-CARD-02` Main title card; `X-CARD-03` End credit; `X-CARD-04` Question card on white |
| compare | `CMP-01` Grey and colour scan side by side; `CMP-02` Stages versus finished; `CMP-03` White and colour versions; `CMP-04` Colour blocks beside detail; `CMP-05` Two colour states; `STATE-01` The same picture in two states; `X-CMP-01` Swap one side of a split; `X-CMP-02` Wipe compare |
| diagram | `DIA-01` Grid and projection rays; `DIA-02` Two views of one object; `DIA-03` Cross-section and light rays; `DIA-04` Figure and separated pieces; `DIA-05` Process silhouette; `DIA-06` Room model and UV image; `DIA-07` Eye and vision diagram; `TIME-01` Time axis with dates; `TREE-01` Relations: family and patrons |
| footage | `FOOT-01` Material footage and palette |
| highlight | `DOC-01` A lit line of a document; `HI-01` Spotlight; `HI-02` Progressive figure reveal; `HI-03` Colour kept on subject; `ID-OPEN-01` Opening: raking light; `X-HI-01` Dim to isolate then restore |
| layout | `LAY-01` Two panels; `LAY-02` Four-tile grid; `LAY-03` Five-column comparison; `LAY-04` Inset window; `LAY-05` Subject held, background changes; `LAY-06` Translucent vertical strips; `LAY-07` Grid with translucent object; `LAY-08` Repeated symmetric motif; `X-LAY-01` Stills sequence with fixed holds |
| shorts | `SHORT-01` Three horizontal strips; `SHORT-02` Changing view; `SHORT-03` Large type changes; `SHORT-04` Yellow label box; `SHORT-05` Colour wheel from palette |
| static | `MAP-01` Atlas map; `STATIC-01` Black matte; `STATIC-02` Source label; `STATIC-04` Quote over image; `STATIC-05` Interviewee tag; `STATIC-06` Map with route; `STATIC-07` Multi-cell circular diagram; `STATIC-08` Name labels on figures; `STATIC-09` Year centred on image |
| text | `ID-LABEL-01` Artwork label without a strip; `ID-OPEN-02` Opening: dim and name; `TXT-01` Chapter title on blurred image; `TXT-02` Sliding italic text |
| transition | `TR-01` Dissolve; `TR-02` Image slide in/out; `TR-03` Panel opening; `TR-04` Full-to-crop hard cut; `X-TR-01` Hard cut; `X-TR-02` Strip slides in, then splits |

86 techniques in 12 headings; `bti` does not list their parameters: GET /api/styles/{style} does, and `bti schema ops storyboard` shows how `set_technique` and `set_params` take them.
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

- **Pacing.** The reference channel's median shot is about 7 seconds, one in ten is under 4 seconds, none is under 1.5 seconds, and a shot over 30 seconds is split with a move or a detail. A beat is usually one to three shots. A camera move under 3 seconds is a cut in disguise; over 20 seconds it needs a second event to stay alive.
- **The frame is full.** An upright painting shown whole is a small picture between two black bars (the main painting of 3840 px width fills the screen at `zoom` 0.5; under 0.3 it is that small picture). Show it whole for at most 5% of the video (30 seconds in ten minutes): the pull back that ends the cold open, one chapter opening and the last shot. Every other shot fills the screen: the painting at full width with a slow travel up or down, a wide band of it, or a detail. The first real draft had 41 of its 109 shots on the small picture and needed a request for each. Neighbouring shots never end and start on the same frame; the chapter marks and the channel-name beat take the pose of the shots beside them.
- **Highlights are rare and stay lit.** `HI-01` and `X-HI-01`: at most one in two minutes, none in the first minute, only on a wide frame to point at an object, never when the camera already frames it closely. The region stays inside the frame (5% in from every edge) from the start to the end of the layer, so look at the camera after any change of it, and the rest of the picture keeps at least 0.6 of its light (`floor`, `surround_floor`): the default 0.2 left the first export with three stretches of five seconds at a mean luma under 26 (the video's median is 55; 16 is black, 235 white).
- **Text on the screen is true and tidy.** A date, figure, place, name or map label comes from the narration (a spelled number counts); a caption is the narration's word, the picture's own title or nothing, never a placeholder ("UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950"), a note to the reader ("Source: an estimate cited in the narration") or the same words twice. A `MAP-01` carries no `region_label`, `region_iso` or `sea_names` that the narration does not name. No map, time axis, tree or two-state picture in the first 30 seconds: the painting is on screen as the viewer arrives.
- **Only pictures that a line has.** A picture the owner took out of every line stays in the project but must not be used again (the draft is not offered it); a small one (long side under 1000 px) is shown no larger than its pixels allow.
- **The owner's picks first.** The pictures the owner chose for a line are what its shots show. A line with none stays on the main painting and moves (zoom in, go to a detail, pull back); never hold a still for more than one shot in a row.
- **A line about something outside the painting needs a picture outside the painting.** A person, a place, a document or another work is shown with the picture the picks give it (`context`, `document`, `compare`, `map`), not with the painting held; if the picks give none, go back to step 4 and ask for one rather than filling the time.
- **Explanatory devices only where the narration makes that point.** `MAP-01` (a place, a journey, a territory: use it instead of the three older map techniques), `TIME-01` (dated events), `TREE-01` (who is related to whom), `KEY-01` (names for parts of the picture), `NUM-01` (a figure or two figures compared), `STATE-01` (the same picture in two states), `DOC-01` (one line of a document, lit). Tie every item to the word that names it (`at: {"w": 154}`); take dates, places, figures and relations only from the narration and the project's sources, and leave an item out when unsure. About 6 to 12 in a ten-minute video, never two in a row, none through general talk: most lines are served better by a camera move.
- **Move toward the thing as it is named.** Start the shot a word before the detail's name; end a spotlight or ring when the sentence moves on; after a detail come back to the painting.
- **Prefer the core techniques**; use occasional and rare ones where a line clearly calls for them; never a technique of the `shorts` heading (they are for Shorts). Do not use the same technique four times in a row.
- **Never put the narration on screen.** Labels are one to five words of your own ("Latin inscription"); no parameter holds a sentence of the narration. The video has no burned-in subtitles.
- **The channel identity is the program's.** The `ID-*` techniques (the opening, the channel-name beat, the chapter marks) are written by the compiler: never add one, never write a title card or a chapter card. Change their style with `identity.set`.
- **Respect locks and scope.** Never touch a locked shot; a batch with a `scope` that an operation leaves is refused whole (`out_of_scope`).

## The warnings of `storyboard.validate` that are the owner's rejections

None of these blocks a save or the approval, but an automatic run stops at them (`quality_warning`, `docs/AGENT_API.md` section 9) and the owner rejects the look. Each issue says what is wrong and what to do; the numbers are estimates from the shot's camera, the picture's size and the parameters (nothing is rendered).

| code | what it means | what to do |
|---|---|---|
| `upright_whole_share` | The main painting covers under 60% of the screen for more than 6% of the running time (a clip under a minute is never judged). `args`: `share`, `seconds`, `count`, `worst` (the shots). | Give those shots a framing that fills the screen (`set_params` with a `camera` at `zoom >= 0.6 x 1920 / width`, the painting at full width travelling up or down); keep the whole painting for the cold open's pull back, one chapter opening and the last shot. |
| `highlight_off_frame` | The lit spot of an `HI-01` or `X-HI-01` is at the edge of the frame (nearer than 5%) or outside it at some moment of its window. | Move the camera so that the region stays inside (`set_params` `camera`), or `remove_overlay`. |
| `highlight_too_dark` | The frame under a highlight has a mean luma under 32 (16 to 235) and the highlight takes away a quarter of it. The issue's `args` give the `floor` that would do (empty: none would). | `remove_overlay` when the camera already frames the object closely; else `set_params` `floor` (`surround_floor` for `X-HI-01`) to that value or about 0.6. |
| `caption_placeholder`, `caption_repeats` | On-screen text that is a placeholder, says `narration`, is only the picture file's artist and year under a caption of its own, or repeats words. `args.param` names it. | `set_params` the text to words from the narration, to the picture's own title, or to `""`. |
| `text_not_in_narration` | A figure, date, place, name or map label (`MAP-01` `region_label`, places, `sea_names`; `NUM-01` `value`; `TIME-01` dates; `STATIC-09` `year`; `DOC-01` `reading`; `TREE-01` names) that the narration never says; a year, title or artist of the shot's own picture is allowed. `args.missing` lists the words. | Use what the narration says, or `""` (for `sea_names` and `region_label`: off and empty). It does not see text inside a picture, the names a map draws from its own data, or free labels such as `X-ANN-01`. |
| `asset_not_in_lines` | A shot shows a picture that no line of the narration has (`picks.json`) and that is not the main painting. | `set_slot` the picture of a line of that part, or the main painting; do not add it to the lines again unless the owner asks (step 4). |
| `explainer_early` | A base explanatory shot (`MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`) starts in the first 30 seconds. | Show the dates as large figures on the painting (`STATIC-09` overlay) and move the diagram to a later chapter. |
| `shot_short` | A shot lasts under 1.5 seconds (tolerated by an automatic run: it is a flash, not a defect). | `merge_shots` it into the one before, or `move_boundary` its cut. |

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
| `gate_needs_human` (exit 3) | The owner has not allowed you to approve this gate: stop and ask. |
