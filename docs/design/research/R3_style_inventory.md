# R3 - Great Art Explained: style and editing inventory

Registry: `style/gae/techniques.json` (schema `techniques.schema.json`, constants `style.json`). Previews: `style/gae/previews/<ID>.mp4|jpg` (640x360, H.264, no audio; cut from `demo_runs/claude_code/technique_reel.mp4` using `ref/reel_plan.json` start/end; `timeline.json` has no `technique_reel` section, so reel_plan.json was the source of segment times). Contact sheets were reviewed by eye and all 56 corner labels match their file names.

Totals: 71 techniques (56 catalogue + 15 added). Kinds: {'base': 39, 'transition': 6, 'overlay': 21, 'card': 5}. Engine: {'done': 43, 'partial': 25, 'missing': 3}.

## 1. All techniques

| id | name | kind | intents | channel_usage | engine | preview |
|---|---|---|---|---|---|---|
| CAM-01 | Push-in | base | explore, point_at | core | done | yes |
| CAM-02 | Layered relative motion | base | explore, establish | rare | partial | yes |
| CAM-03 | Pull-back | base | establish, context | core | done | yes |
| CAM-04 | Pan up | base | explore | occasional | done | yes |
| CAM-05 | Zoom and shift | base | explore, point_at | core | done | yes |
| CAM-06 | Hold and label reveal | base | establish, structure | occasional | done | yes |
| TR-01 | Dissolve | transition | transition, context | occasional | done | yes |
| TR-02 | Image slide in/out | transition | compare, transition | occasional | done | yes |
| TR-03 | Panel opening | transition | reveal, transition | rare | partial | yes |
| TR-04 | Full-to-crop hard cut | transition | transition, point_at | core | done | yes |
| LAY-01 | Two panels | base | compare, context | core | done | yes |
| LAY-02 | Four-tile grid | base | compare, explain_mechanism, context | occasional | done | yes |
| LAY-03 | Five-column comparison | base | compare | rare | partial | yes |
| LAY-04 | Inset window | base | context, compare | occasional | done | yes |
| LAY-05 | Subject held, background changes | base | context | rare | partial | yes |
| LAY-06 | Translucent vertical strips | base | context | rare | done | yes |
| LAY-07 | Grid with translucent object | base | context | rare | done | yes |
| LAY-08 | Repeated symmetric motif | base | context | rare | done | yes |
| HI-01 | Spotlight | overlay | isolate, point_at | core | done | yes |
| HI-02 | Progressive figure reveal | base | reveal, explore | occasional | partial | yes |
| HI-03 | Colour kept on subject | overlay | isolate | rare | done | yes |
| AN-01 | Circle draw | overlay | point_at | core | done | yes |
| AN-02 | Object outline | overlay | point_at, isolate | occasional | partial | yes |
| AN-03 | Perspective rays | overlay | explain_mechanism, point_at | occasional | done | yes |
| AN-04 | Map circle and arrow | overlay | context, quantify | occasional | partial | yes |
| AN-05 | Dimension ruler | overlay | quantify | occasional | done | yes |
| AN-06 | Grid and geometric regions | overlay | explain_mechanism | occasional | done | yes |
| AN-07 | Dot field densifying | base | reveal, explain_mechanism | rare | done | yes |
| TXT-01 | Chapter title on blurred image | card | structure | core | done | yes |
| TXT-02 | Sliding italic text | overlay | quote | rare | done | yes |
| STATIC-01 | Black matte | base | establish | core | done | yes |
| STATIC-02 | Source label | overlay | context | occasional | done | yes |
| STATIC-04 | Quote over image | overlay | quote | occasional | done | yes |
| STATIC-05 | Interviewee tag | overlay | context | other_series | partial | yes |
| STATIC-06 | Map with route | base | quantify, context | other_series | partial | yes |
| STATIC-07 | Multi-cell circular diagram | base | explain_mechanism | rare | done | yes |
| STATIC-08 | Name labels on figures | overlay | point_at, context | rare | partial | yes |
| STATIC-09 | Year centred on image | overlay | quantify, structure | occasional | done | yes |
| DIA-01 | Grid and projection rays | base | explain_mechanism | rare | partial | yes |
| DIA-02 | Two views of one object | base | explain_mechanism, compare | rare | partial | yes |
| DIA-03 | Cross-section and light rays | base | explain_mechanism, quantify | rare | partial | yes |
| DIA-04 | Figure and separated pieces | base | explain_mechanism | rare | partial | yes |
| DIA-05 | Process silhouette | base | explain_mechanism, reveal | rare | partial | yes |
| DIA-06 | Room model and UV image | base | explain_mechanism, context | rare | partial | yes |
| DIA-07 | Eye and vision diagram | base | explain_mechanism | rare | partial | yes |
| CMP-01 | Grey and colour scan side by side | base | compare | rare | done | yes |
| CMP-02 | Stages versus finished | base | compare, reveal | rare | partial | yes |
| CMP-03 | White and colour versions | base | compare | rare | done | yes |
| CMP-04 | Colour blocks beside detail | base | compare, explain_mechanism | rare | done | yes |
| CMP-05 | Two colour states | base | compare | rare | done | yes |
| FOOT-01 | Material footage and palette | base | context | occasional | partial | yes |
| SHORT-01 | Three horizontal strips | base | compare, context | shorts_only | done | yes |
| SHORT-02 | Changing view | base | explain_mechanism | shorts_only | partial | yes |
| SHORT-03 | Large type changes | base | quote, structure | shorts_only | done | yes |
| SHORT-04 | Yellow label box | overlay | structure | other_series | done | yes |
| SHORT-05 | Colour wheel from palette | base | explain_mechanism | shorts_only | partial | yes |
| X-TR-01 | Hard cut | transition | transition | core | done | reused TR-04 |
| X-CARD-01 | Chapter card on black | card | structure | core | done | no |
| X-CARD-02 | Main title card | card | structure | occasional | done | no |
| X-CARD-03 | End credit | card | structure | occasional | missing | no |
| X-CARD-04 | Question card on white | card | structure, quote | rare | missing | no |
| X-ANN-01 | Detail label strip (one line) | overlay | point_at, context | core | done | no |
| X-ANN-02 | Artwork label (two lines) | overlay | context, structure | core | done | no |
| X-ANN-03 | Recap labels at closing | overlay | structure, point_at | occasional | done | no |
| X-ANN-04 | Sequential group outlines | overlay | isolate, reveal, point_at | occasional | partial | no |
| X-ANN-05 | Map point markers one by one | overlay | quantify, context | rare | missing | no |
| X-LAY-01 | Stills sequence with fixed holds | base | context, structure | core | done | no |
| X-CMP-01 | Swap one side of a split | base | compare, context | core | partial | no |
| X-CMP-02 | Wipe compare | base | compare, reveal | rare | partial | reused CMP-05 |
| X-TR-02 | Strip slides in, then splits | transition | compare, transition | rare | partial | no |
| X-HI-01 | Dim to isolate then restore | overlay | isolate, point_at | core | done | no |

`channel_usage` is a judgement from how many exemplars the research found and the sync analysis (core = recurs across videos or episode structure; rare = one exemplar). Param min/max and timing min/max are UI bounds picked by the registry author unless a `measured` value is attached.

## 2. Added entries (not in the 56 catalogue records)

- **X-TR-01 Hard cut** (transition, done): The picture changes instantly between two shots with no fade, dissolve or wipe. Evidence: measurements.md Framing and structure; capabilities_report.md Structure decisions; EFFECTS_CATALOG TR-04.
- **X-CARD-01 Chapter card on black** (card, done): A black frame with a small centred caps chapter title low in the frame, then a hard cut. Evidence: measurements.md Chapter card; T15Kv6dtYO0 chapter card FASHIONS AND FABRICS; capabilities_report.md (8 cards 2.8 s in build).
- **X-CARD-02 Main title card** (card, done): Title of the work, artist and year centred over a blurred, darkened image of the painting. Evidence: capabilities_report.md Structure decisions (title after hook, 2.6 s: benchmark choice); EFFECTS_CATALOG TXT-01 (chapter title variant); visual-a/two-samples.md A-S02.
- **X-CARD-03 End credit** (card, missing): A credit line centred at the bottom over the closing matte. Evidence: measurements.md Overlays/text: Closing.
- **X-CARD-04 Question card on white** (card, missing): A brown serif question or title on a white background. Evidence: visual-a/T9JvUDrrXmY.md A-T9-02 (190.190 s, 350.350 s); visual-a/catalog-gaps.md A-T9-02.
- **X-ANN-01 Detail label strip (one line)** (overlay, done): A dark translucent strip across the lower frame with one white caps line naming the detail; the right end of the strip fades out. Evidence: measurements.md Detail label; visual-b/T15Kv6dtYO0.md ARNOLFINI-03 (DETAIL_LABEL); visual-b/catalog.md DETAIL_LABEL.
- **X-ANN-02 Artwork label (two lines)** (overlay, done): The same strip with two lines: the work title in caps, then ARTIST, YEAR in a smaller line beneath. Evidence: measurements.md Detail label: second smaller line (artist, year); visual-b/lKIbT-4UFaE.md NIGHTHAWKS-01 (work label appears then vanishes); capabilities_report.md (still_shot two-line label).
- **X-ANN-03 Recap labels at closing** (overlay, done): Plain white words (for example CANDLE, ROUNDELS, MOURNING DRESS, DOG) placed near their details over the black matte, with no strip. Evidence: measurements.md Closing; capabilities_report.md / build_v2.py recap ScreenText.
- **X-ANN-04 Sequential group outlines** (overlay, partial): White outlines are drawn around groups one after another, then all disappear while the whole painting stays. Evidence: SYNCHRONIZATION_ANALYSIS (Supper 21:11-21:25, Goya 1058-1129); scene-sync/longform-cases.md goya-continuous, supper-continuous; visual-b/GLW9omJfAdk.md GOYA-04.
- **X-ANN-05 Map point markers one by one** (overlay, missing): Red dots appear one by one on a map. Evidence: visual-a/catalog.md A-J09 (cuHgxPe3J7I 140.007-149.516 s).
- **X-LAY-01 Stills sequence with fixed holds** (base, done): Several context stills follow each other, each held a fixed 4.0 s with a hard cut between them. Evidence: measurements.md Framing and structure; ref/qa_pacing2.txt (build holds median 7.4 s vs 4.0 s reference).
- **X-CMP-01 Swap one side of a split** (base, partial): The anchor painting stays in one cell while the other cell's image or video is replaced by another comparison. Evidence: SYNCHRONIZATION_ANALYSIS (principle 1); scene-sync/dynamic-cases.md starry-landscape; scene-sync/longform-cases.md supper-continuous 21:48-22:05.
- **X-CMP-02 Wipe compare** (base, partial): A monochrome version enters from the right edge, a vertical border sweeps left, the two versions sit side by side, then dissolve to the colour image. Evidence: SYNCHRONIZATION_ANALYSIS (principle 4); scene-sync/longform-cases.md mona (dense-0554); scene-sync/longform-cases.md mona s10 (monochrome type unidentified).
- **X-TR-02 Strip slides in, then splits** (transition, partial): A strip from a second work slides up from the bottom into a full-frame image, then moves right so it sits beside the first painting. Evidence: scene-sync/longform-cases.md goya-continuous-s07 / goya-micro 1119-1125.
- **X-HI-01 Dim to isolate then restore** (overlay, done): The whole frame darkens around a figure or object that stays bright, then brightness returns and the frame widens back. Evidence: SYNCHRONIZATION_ANALYSIS (principle 3); scene-sync/longform-cases.md goya-continuous-s05/s09, supper-continuous-s11; scene-sync/dynamic-cases.md raphael-perspective 721-747.

Candidates from the brief that were folded in: hard cut, chapter card, main title card, detail label, two-line label, recap labels, 4.0 s stills, swap-one-side, wipe-compare, strip slide-then-split, end credit. Extra from research: question card on white, sequential group outlines, map point markers, dim-isolate-restore.

## 3. Engine partial or missing, and what it would take

- **CAM-02 Layered relative motion** [partial]: Clean empty-room plate not available; plate is cv2.inpaint+blur stand-in, GrabCut mask rough (wall chunk next to Giovanni). Would need hand-painted layers
- **TR-03 Panel opening** [partial]: Shutter art is a stand-in (no real triptych); timing only coarse in reference
- **LAY-03 Five-column comparison** [partial]: Reference columns are five different works; stand-in uses one painting in 5 treatments
- **LAY-05 Subject held, background changes** [partial]: Rough mask; backgrounds are paintings, not footage
- **HI-02 Progressive figure reveal** [partial]: Stand-in plate is smeared; hook in final uses a clean detail move
- **AN-02 Object outline** [partial]: Outline follows the rough mask, not the true silhouette
- **AN-04 Map circle and arrow** [partial]: Procedural stand-in map (no map asset)
- **STATIC-05 Interviewee tag** [partial]: No interview footage; text is a generic placeholder
- **STATIC-06 Map with route** [partial]: Stand-in map
- **STATIC-08 Name labels on figures** [partial]: Labels sit over the figures heads instead of beside them (placement defect, not re-rendered)
- **DIA-01 Grid and projection rays** [partial]: No anamorphic skull; analogue only
- **DIA-02 Two views of one object** [partial]: Different object
- **DIA-03 Cross-section and light rays** [partial]: Schematic, not a real micrograph
- **DIA-04 Figure and separated pieces** [partial]: Different subject
- **DIA-05 Process silhouette** [partial]: No process footage
- **DIA-06 Room model and UV image** [partial]: Simulated UV
- **DIA-07 Eye and vision diagram** [partial]: Different diagram
- **CMP-02 Stages versus finished** [partial]: Stages are blur levels, not real underdrawing
- **FOOT-01 Material footage and palette** [partial]: No real footage
- **SHORT-02 Changing view** [partial]: No skull; BORDER_REPLICATE smears vertical streaks at the warped edge (visible defect, not re-rendered)
- **SHORT-05 Colour wheel from palette** [partial]: Palette wheel is synthetic
- **X-CARD-03 End credit** [missing]: build_v2.py has no credit element; wording, timing and style unknown.
- **X-CARD-04 Question card on white** [missing]: No card of this colour scheme in the benchmark; timing and animation unknown (still frames only).
- **X-ANN-04 Sequential group outlines** [partial]: Only a single progressive outline is built; no multi-group sequencing or clean mask.
- **X-ANN-05 Map point markers one by one** [missing]: Not built; benchmark map has a route and an arrow, not point markers.
- **X-CMP-01 Swap one side of a split** [partial]: Only the initial slide-in of one panel is built; swapping content during the shot is not.
- **X-CMP-02 Wipe compare** [partial]: Reel has a 3.5 s wipe of two colour states; the hold-split and final dissolve of the observed behaviour were not verified.
- **X-TR-02 Strip slides in, then splits** [partial]: Slide-in from the side exists (TR-02); the vertical strip to full frame to split sequence is not built.

Common themes: (a) no real footage, maps, interview or UV material in the benchmark assets, so stand-ins were used (AN-04, STATIC-05/06, FOOT-01, DIA-06); (b) GrabCut cut-outs are rough, which limits CAM-02, HI-02, LAY-05, HI-03, AN-02, DIA-04/05; (c) known visible defects left unrendered: SHORT-02 edge streaks, STATIC-08 labels over heads, SHORT-04 clipped text; (d) behaviours seen only in the sync analysis (multi-group outlines, swap during shot, strip-then-split, map markers, end credit) were never built.

## 4. Parameters with no measured reference value

Counts of params with `measured: null` per technique (default is then the benchmark's own value or a placeholder):

- CAM-01: focus_center
- CAM-02: fg_zoom, bg_zoom, easing
- CAM-03: focus_center
- CAM-04: direction
- CAM-06: label_text
- TR-02: from_edge, easing
- TR-03: hinge_angle_deg, perspective_squeeze_pct
- LAY-01: gap_px, caption_left, caption_right, split_pct
- LAY-02: connectors, connector_draw_s, gap_px
- LAY-03: columns, gap_px
- LAY-04: inset_w_px, inset_corner, inset_push
- LAY-05: seconds_per_background
- LAY-06: strip_count, strip_opacity
- LAY-07: overlay_opacity
- LAY-08: tiles
- HI-01: ramp_in_s, ramp_out_s, feather, rx, ry
- HI-02: group_slide_s, reveal_order
- HI-03: desaturate_ramp_s, outside_saturation
- AN-02: draw_s, stroke_px, color, fade_s
- AN-03: ray_count, stagger_s, line_px, color, each_draw_s
- AN-04: route_draw_s, route_color, label
- AN-05: width_label, height_label, medium_caption
- AN-06: grid_draw_s, region_opacity, shape
- AN-07: dots_start, dots_end, radius_start_px, radius_end_px, crossfade_to_painting
- TXT-01: title, blur_sigma, darken, fade_in_s, font
- TXT-02: text, speed_px_s, size_px, direction
- STATIC-01: painting_height_pct, shadow
- STATIC-02: text, size_px, margin_left_px
- STATIC-04: quote, size_px, background_dim
- STATIC-05: name, size_px
- STATIC-06: route_color, route_draw_s, route_style
- STATIC-07: sectors, stagger_s
- STATIC-08: size_px, leader_lines
- STATIC-09: year, size_px, tracking_px
- DIA-01: ray_count, ray_draw_s
- DIA-02: warp_s
- DIA-03: ray_count, ray_color, ray_stagger_s
- DIA-04: drift_s
- DIA-05: stages
- DIA-06: uv_label
- DIA-07: ray_count
- CMP-01: colour_fade_s
- CMP-02: stages
- CMP-03: panels
- CMP-04: blocks_start, blocks_end
- CMP-05: wipe_s
- FOOT-01: cards
- SHORT-01: swap_every_s, frame_aspect
- SHORT-02: warp_s, frame_aspect
- SHORT-03: size_px, seconds_per_line, frame_aspect
- SHORT-04: text, box_color, pop_s
- SHORT-05: sectors, sector_stagger_s
- X-CARD-01: title
- X-CARD-02: title, artist, year, fade_in_s, blur_sigma, darken, card_duration_s
- X-CARD-03: credit_text, y_pct, size_px
- X-CARD-04: text, text_color, background
- X-ANN-01: text, case
- X-ANN-02: title, artist_year, second_line_scale
- X-ANN-03: text, size_px, hold_s, fade_in_s, fade_out_s
- X-ANN-04: group_count, per_group_draw_s, stroke_px, color, clear_all_at_end
- X-ANN-05: marker_count, stagger_s, color
- X-LAY-01: push, label
- X-CMP-01: anchor_side, swap_transition, anchor_push, seconds_per_swap
- X-CMP-02: wipe_s, from_edge, hold_split_s, end_dissolve_s
- X-TR-02: slide_from, slide_s, split_to
- X-HI-01: ramp_in_s, hold_s, ramp_out_s, shape

Overall 167 of 219 params are unmeasured. Caveats on measured ones: scroll-text, slide-in and panel-opening timing come from 1 fps tiles (+/-0.5 s); spotlight surround level is estimated by eye; the benchmark's reel used floor 0.35 while the Arnolfini build used 0.20. Params with `default: null` (for example focus centre, label text, SHORT-04 text) are content, not style.

## 5. Research items that could not be turned into techniques

- Pure horizontal or diagonal pans, push-out variants beyond CAM-03, wipes other than the Mona Lisa vertical sweep, easing for non-measured moves: research states there is not enough evidence (EFFECTS_CATALOG footer; visual-a/catalog.md).
- True 3D, parallax reprojection, AI generation: explicitly not evidenced; CAM-02 is only recorded as relative layer motion.
- Footage content itself (museum footage, hand painting, sculptures filmed, interview, archival film, book pages): source material, not editing effects (FOOT-01 only keeps the interleaving). Tilt/orbit of filmed statues (A-N05) is camera footage, not an edit.
- Static layout states with unknown change mechanism: LAY-08 symmetric wheel (source image or edit unknown), STATIC-07 circular diagram, DIA-04/05/06/07, CMP-04/05, SHORT-05 (still only). Kept as catalogue records but their motion is not established.
- Top/bottom two-painting stack (Supper 20:37-20:48) and three-image closing frame (Sargent): treated as LAY-01 variants, no separate entry.
- Starry 10:39 diagonal white lines over a four-landscape grid and rectangular accent lights on the Raphael fresco (A-R08): covered by LAY-02/AN-03 and HI-01 respectively; the rectangular-light variant is not parameterised.
- Per-word cue onset: the channel's cue-to-word alignment is not measurable (ASR has segment timestamps only), so `anchor: word` records intent, not a measured offset. Benchmark's own 6/6 within 0.25 s is benchmark data, kept in style.json.
- Intro, sponsor and outro: the catalogue treats them as places where primitives are used, not as effects; only recap labels and end credit were added, and end credit wording/timing is unknown.
- Font name: research only says Futura-like; no exact font inferred.
- The 7 videos without MP4 and Shorts beyond the 5 SHORT records were not examined; no claims were made about them.
