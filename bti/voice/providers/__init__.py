"""Synthesis providers. A provider speaks a list of chunks into `dest_dir/<chunk id>.wav` (24 kHz mono 16-bit) and reports, per
chunk id, `{"ok": True, "sec": float}` or `{"ok": False, "error": str}`:

    provider.synth(chunks, dest_dir, ctx, workdir) -> dict[str, dict]

`chatterbox` runs the comic voice worker as a child process (real, server only); `fake` writes short tones whose length follows
the text (tests)."""
from __future__ import annotations

from ..errors import VoiceError


def resolve(name: str, server: dict | None):
    """The provider called `name`. `chatterbox` needs a configured worker, else VoiceError `voice_not_configured`."""
    if name == "fake":
        from .fake import FakeProvider
        return FakeProvider()
    if name == "chatterbox":
        from .chatterbox import ChatterboxProvider
        from ..config import voice_worker
        w = voice_worker(server or {})
        if w is None:
            raise VoiceError("voice_not_configured", "no voice worker is configured on this machine (config/server.json)")
        return ChatterboxProvider(w)
    raise VoiceError("voice_not_configured", f"unknown voice provider {name!r}", 422)
