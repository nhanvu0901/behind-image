"""Step 3 of the pipeline: the voice. From an approved narration to `audio/mix.m4a`, `audio/voice.wav` and `timing.json`.

The rest of the app sees two things: `bti.editor.voice_api.router` and `state(project_dir)`."""
from __future__ import annotations

from .errors import VoiceError
from .status import describe, state

__all__ = ["state", "describe", "VoiceError"]
