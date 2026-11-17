"""Numeric limits shared by the engine command line and (by import) the editor's HTTP API.

One place, so the two entrances never disagree about what a valid width, frame rate or time range is.
"""
from __future__ import annotations

FRAME_WIDTH_MIN, FRAME_WIDTH_MAX = 64, 1920         # one still frame (`/frame`, `/thumb`, CLI `still`, CLI `render`)
PREVIEW_WIDTH_MIN, PREVIEW_WIDTH_MAX = 160, 1280    # the editor's preview clip
FPS_MIN, FPS_MAX = 1, 30                            # frames per second of a rendered clip
PREVIEW_MAX_SECONDS = 30.0
PREVIEW_MAX_FRAMES = 900
CANVAS_FPS_MIN, CANVAS_FPS_MAX = 1, 60              # `canvas.fps` of the storyboard document
THREADS_MAX = 64                                    # CLI `--threads`; 0 means "automatic"
CANVAS_W, CANVAS_H = 1920, 1080                     # the engine always draws on this canvas; boxes are in these pixels
POINT_ABS_MAX = 1e6                                 # a point coordinate beyond this is nonsense in any unit (canvas px, source px, fractions)
CAMERA_ZOOM_MAX = 1000                              # screen px per source px; beyond this a camera key is nonsense
BOX_MIN_PX = 16                                     # a `box` param (canvas px) is at least this wide and high
