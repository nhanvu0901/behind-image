"""An engine `Project` for a document that is not saved anywhere: the compiler needs `validate`, `draw_check`, `default_params` and
`frame_at` on a project that has no storyboard.json yet (a first draft), or whose files are copies (a workspace).

`DraftProject` is the engine's own `Project` with two methods overridden: it never reloads a file, and it takes its timing from
memory. Everything else is the facade, unchanged.

`scaled_images`: inside a workspace the pictures are downscaled copies (no larger than 1568 px) but every coordinate in a document
is in SOURCE pixels. While this context is active, an image read from a listed path is stretched back to its declared size, so
that the camera, the regions and the overlays land where the declared numbers say. Only the helper commands use it.
"""
from __future__ import annotations

import contextlib
import copy
import json
import os
import shutil
import tempfile
from pathlib import Path

from bti.engine import api as engine_api
from bti.engine.timing import Timing

_STUB = {"schema": "bti.storyboard/1", "shots": [], "assets": {}, "end": {"t": 1.0}}


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


class DraftProject(engine_api.Project):
    def __init__(self, project_dir: Path, storyboard: dict, timing: dict):
        self._scratch = tempfile.mkdtemp(prefix="bti-draft-proj-")
        try:
            (Path(self._scratch) / "storyboard.json").write_text(json.dumps(_STUB), encoding="utf-8")
            super().__init__(Path(self._scratch))
        except BaseException:
            shutil.rmtree(self._scratch, ignore_errors=True)
            raise
        self.dir = Path(project_dir)
        self._saved = copy.deepcopy(storyboard)
        self._tm_obj = Timing(copy.deepcopy(timing))

    def _reload_if_changed(self):
        return None

    def _timing_for(self, sb):
        return self._tm_obj

    def close(self) -> None:
        shutil.rmtree(self._scratch, ignore_errors=True)

    def set_saved(self, storyboard: dict) -> None:
        self._saved = copy.deepcopy(storyboard)


@contextlib.contextmanager
def scaled_images(project_dir: Path, assets: dict):
    """See the module docstring. `assets` is the storyboard's assets map (declared `width`/`height`, `file`)."""
    import cv2
    from bti.engine import vfx
    want: dict = {}
    for a in (assets or {}).values():
        if isinstance(a, dict) and isinstance(a.get("file"), str) and a.get("width") and a.get("height"):
            want[_norm(Path(project_dir) / a["file"])] = (int(a["width"]), int(a["height"]))
    orig = vfx.Img

    class _Scaled(orig):
        def __init__(self, path_or_arr, name=""):
            if isinstance(path_or_arr, str):
                arr = cv2.imread(path_or_arr, cv2.IMREAD_COLOR)
                size = want.get(_norm(path_or_arr))
                if arr is not None and size and (arr.shape[1], arr.shape[0]) != size:
                    arr = cv2.resize(arr, size, interpolation=cv2.INTER_CUBIC)
                if arr is not None:
                    name = name or os.path.basename(path_or_arr)
                    path_or_arr = arr
            super().__init__(path_or_arr, name)

    vfx.Img = _Scaled
    try:
        yield
    finally:
        vfx.Img = orig
