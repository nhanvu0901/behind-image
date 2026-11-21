"""Chạy tự động: walk a project from wherever it stands to a finished video, by itself, inside the limits the owner set.

    bti/auto_run/loop.py      the loop (the rule is in its docstring): read the state, take the first allowed advancing action, follow its job
    bti/auto_run/checks.py    the quality bar before a gate: which warnings stop the run
    bti/auto_run/reasons.py   every way a run ends, with its sentence (Vietnamese for the owner, English for an agent)
    bti/auto_run/runlog.py    the run log in the project folder (auto_runs/<run id>.json) and the list of runs
    bti/auto_run/job.py       the run as a long job of the shared runner (kind `auto`)
    bti/auto_run/api.py       POST /api/projects/{pid}/auto/run, GET .../auto/runs and .../auto/runs/{run_id}

The switch the owner turns on is `projects/<pid>/auto.json` (bti/auto.py); the routes are mounted by bti/editor/auto_api.py.
"""
