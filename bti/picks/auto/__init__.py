"""The agent that chooses the pictures of step 4 ("Để agent chọn hình").

    from bti.picks.auto import start, escalate, overview, AutoError

`start(pid, pdir, beats=None, redo=False, base_rev=None)` starts the long job and answers its record; `escalate(pid, pdir, beat_ids, note=...)`
is the plain function for the instruction box of step 4; `overview(pid, pdir)` is what the page reads. The design and the four parts are in
`bti/picks/auto/job.py`; `retry.start(...)` (`bti/picks/auto/retry.py`) finishes a run whose chosen pictures could not be downloaded (`picks.retry_missing`); the two files the agent writes are in `bti/picks/auto/shapes.py`; the agent's briefings are
`skills/picks_auto/PLAN.template.md` and `CHOOSE.template.md`. The route is in `bti/editor/picks_api.py`.
"""
from __future__ import annotations

from . import retry, tighten_job
from .inputs import AutoError
from .job import ACTION, KIND, active_job, escalate, overview, start

__all__ = ["start", "escalate", "overview", "active_job", "AutoError", "KIND", "ACTION", "retry", "tighten_job"]
