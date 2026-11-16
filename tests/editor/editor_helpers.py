import copy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PID = "demo_stub"


def editable(state):
    """The resolved doc, as the page would send it back (derived keys included on purpose)."""
    return copy.deepcopy(state["storyboard"])
