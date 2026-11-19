"""A bench for the agents: sample requests for each model step, run several times on a COPY of a sample project, counted against pass criteria a program checks.

    python -m bti.evals list [--step S] [--criteria]
    python -m bti.evals run --step S --agent ID --repeat 3 [--case NAME ...] [--yes-cost] [--url URL] ...
    python -m bti.evals compare RUN_A RUN_B
    python -m bti.evals show RUN

Why: an agent that does the same task several times does not give the same result, so one good run proves little. A run of the bench answers "how many of
three tries passed, and which criterion failed most" for every case; `compare` shows what changed when a prompt or a model did.

    bti/evals/cases.py      a case is a small JSON file (evals/cases/<step>/<name>.json): the step, the sample project, the request, the criteria
    bti/evals/criteria.py   the criteria kinds: functions on what the agent made (documents read through the app's API)
    bti/evals/samples.py    the copy of a sample project a run works on (never a project of the owner), and its starting state
    bti/evals/driver.py     one driver per step: the calls an agent makes through the API, and the outputs the criteria read
    bti/evals/runner.py     the run: cases x repeats, recorded
    bti/evals/report.py     the run file (JSON), the summary table (Markdown), `compare`
    bti/evals/cli.py        the command

Real model calls happen only when somebody starts a run against a running app with real agents: the command says how many calls it is about to make and needs
`--yes-cost` to go on. The tests use the fake agents of the test launchers.
"""
