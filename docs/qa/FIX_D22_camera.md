# FIX_D22_camera: drag the camera keys of a shot on the picture (step 5, "Ảnh gốc")

## What existed, and what was broken
- `preview.js` drew the keys of ONE camera, the parameter literally named `camera`, in both views: a rectangle per key (`cameraToBox`) with a legend row "K1  zoom 0.65" and one square knob at the bottom-right corner. Each rectangle and knob was its own svg element with its own handler.
- Broken, found by reading and confirmed in the browser:
  1. **Wrong aspect and size for every layout technique.** The frame was always the 16:9 canvas divided by zoom. LAY-01 (cell 900 x 740), CMP-01/03/04, X-CMP-01, LAY-02, LAY-08... look through a smaller cell, so the frame did not show what the camera sees.
  2. **No frames at all** for any technique whose camera parameter is not named `camera`: LAY-01 (`camera_left`, `camera_right`), LAY-02, LAY-05, LAY-06, LAY-07, CAM-02, CMP-02, X-CMP-01. Also the source view always showed the shot's first picture, never the picture the camera looks at (LAY-01 right).
  3. **Overlap:** later keys were drawn on top and swallowed the pointer; with keys that hold still (key 1 = key 2) one of them could not be reached; a small frame inside a large one only worked if it came later in the list.
  4. **The knob** only moved the bottom-right corner and kept the top-left corner, so the centre moved while resizing.
  5. **Undo:** the drag used the store's 900 ms merge window: a pause in the middle of a drag made two undo steps, and two drags of the same key within 900 ms made one.
  6. No selected key: nothing highlighted it, and the form on the right did not follow the picture or the other way round.
  7. In the frame view each mouse move asked the server for a new picture (debounced, but still a round trip while dragging).

## What was built
- `bti/editor/static/js/camgeom.js` (new, pure, tested): the table of which slot and which panel each camera parameter looks through (all 41 camera parameters of the 24 techniques, each line says which engine file it was read from), key to frame rectangle and back, centre move with limits, corner resize, hit testing with overlap, the zoom-out of the source view, selection rules.
- `bti/editor/static/js/camsel.js` (new): the selected key (shot, camera parameter, index), shared by picture and form.
- `preview.js`: frames, labels, highlight, four corner handles for the selected key, one pointer handler on the svg (picks with `hitTest`), a chooser "Camera:" next to the view switches when the shot has several cameras, drag as one undo step with its own merge key (no time limit), no server request while dragging.
- `formui.js`: the block of the selected key is marked ("đang chọn trên ảnh", scrolled into view when the picture selected it); a click or focus in a key's block selects that key on the picture.
- `labels.js` (block `d-camera`, `CAMERA_LABELS`), `edit.css` (frames, chooser, selected block), `docs/APP_GUIDE.md` (section "Kéo khung camera", the old "Chưa có" line removed).

## How the frame's size and aspect are derived
The engine's definition (`bti/engine/vfx.py`, `Img.view`): panel x = panel_w / 2 + (x - cx) * zoom. So a key sees, in source pixels, a rectangle of (panel_w / zoom) x (panel_h / zoom) centred on (cx, cy); the aspect is the panel's, the size follows from zoom (a unit test maps the engine's own formula back and gets the panel edges).
The panel is what the technique's engine code draws the picture into, read from the code and from the shot's own parameters (registry defaults when the shot has none):
- whole frame (1920 x 1080, the storyboard's `canvas`): CAM-01..06, STATIC-01, X-LAY-01, AN-07, HI-02, CAM-02 (both layers), LAY-04 `camera`, LAY-05 (all), LAY-06, LAY-07 `object_camera`, CMP-05, X-CMP-02;
- LAY-01: `panel_w_px` x `panel_h_px` (900 x 740 by default) for BOTH `camera_left` (slot `left`) and `camera_right` (slot `right`); the picture of the view is the slot of the selected camera;
- the same rule with the technique's own parameters: LAY-02 `tile_w_px` x `tile_h_px`; LAY-04 `inset_camera` `inset_w_px` x `inset_h_px`; CMP-01/03/04 and X-CMP-01 `panel_w_px` x `panel_h_px`; CMP-02 `finished_box` size and `derive_px` square; LAY-07 tiles: the canvas split in `columns` columns and as many rows as there are tiles with a picture; LAY-08: the canvas divided by the `tiles` "CxR" string; LAY-06 `camera_base` looks at `background` or, when empty, at `image`.
A unit test fails when the registry gets a camera parameter that the table does not know (and when the table names a parameter that is not in the registry); an unknown one falls back to "first image slot, whole frame".

## Limits applied while dragging
Hard limits = the engine's validation (`limits.py`: |cx|, |cy| <= 1e6, 0 < zoom <= 1000) and the lowest zoom the form accepts (0.01). Soft limit: the centre stays inside the picture; a key that is already outside is not pulled back, only kept from going further out. The frame itself may be larger than the picture (matte around it: the default camera of a matte shot is about 5 % taller than the picture); a literal "frame inside the picture" would make every default key impossible. The corner handle projects the pointer on the frame's diagonal, so a diagonal pull follows the pointer exactly and the centre never moves.

## Overlap rules
The selected key's corner handles win everywhere. Elsewhere the smallest frame under the pointer is picked. Equal frames (a camera that holds still first: key 1 = key 2, as in the LAY-01 shot of `arnolfini`) are a stack: a drag moves the selected one; a click without movement passes the selection to the next one in the stack.

## Tests
- `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`: 248 pass (212 before, +36 in `tests/editor_frontend/camgeom.test.mjs`).
- Browser: `tests/e2e/storyboard/camera_frames.mjs` (against the second instance on the server, as in `docs/qa/STAGES_ui.md`, project `arnolfini`, real mouse events over CDP): 54 PASS, 0 FAIL on the last run. It covers: three keys (frames, labels, aspect, size ratio from the zooms, one highlighted, legend, handles), centre drag of an unselected frame (numbers, selection, one undo step, dirty, number fields, no frame request from the server), corner drag with a 1.3 s pause (one undo step), undo and redo through the real buttons, click without movement, form to picture, nested frames (small inside large, handles of the selected win), save and compare with the stored storyboard, LAY-01 (chooser, cell aspect, drag, corner, stack walk, other camera, frame-view note), a sweep over all 41 camera parameters of the 24 techniques (three frames of the right aspect each, a real drag in 25 of them), a shot with 44 keys, 1280x720 (preview >= 300 px, instruction box, tool row), the timeline click, the Hình tab, no script error. Each run starts from the repo's original `arnolfini` storyboard and restores it at the end.
- Screenshots: `.scratch/dcamera/shots/` (1700x1000 and 1280x720: three-keys, three-keys-after-corner, overlap, lay01-left, lay01-right; lay01-1280-source).
- Python: no Python changed. `tools/deploy/snapshot_test.sh dcamera -- tests/editor -q`: 415 passed (last line of this file).

## Known limits
- A frame larger than what the view shows is clipped at the edge of the preview. The view zooms out to hold all frames when a camera is opened (or when its number of keys changes), but not on every edit, so the picture does not change size under the pointer or under a typed number.
- Corner handles only on the selected key and only at corners (no edge handles).
- In the frame view (no "Ảnh gốc") frames are drawn only for a camera that fills the whole frame (through the camera at the playhead); a camera of a cell shows a note asking for "Ảnh gốc".
- The preview shows the shot under the playhead; frames of a shot other than the selected one are not drawn (unchanged).
- The rig: `node tests/e2e/stages/remote.mjs restart` followed by a run left a stale ssh tunnel twice (two "fetch failed" journeys); a fresh `up` is reliable, so the final run was made that way.
- Python: snapshot_test.sh dcamera -- tests/editor -q: 415 passed (no Python changed).
