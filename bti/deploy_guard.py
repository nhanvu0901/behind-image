"""Coordinate job registration with the server deploy lock."""
from pathlib import Path


class DeployBusy(Exception):
    """A deploy is holding the lock; retry after it finishes."""


def active() -> bool:
    return (Path(__file__).resolve().parents[1] / "run" / "deploy.lock").is_dir()
