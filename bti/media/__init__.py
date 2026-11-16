"""bti.media: licence-clear media search, vetting and import, plus research.

The editor backend calls the facade in `bti.media.api` only.
"""
from .licence import check_licence, check_text  # noqa: F401
