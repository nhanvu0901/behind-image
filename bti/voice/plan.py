"""The plan of a voice run: the chunks of the narration as it is NOW, the settings, and the signatures that say what is fresh."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from bti.script import store

from . import files
from .chunks import Chunk, build_chunks
from .config import load_voice_config, project_settings
from .errors import VoiceError


@dataclass
class Plan:
    chunks: list[Chunk]
    narration: object
    settings: dict                      # {tempo, pad}
    table: dict
    seeds: dict
    provider: str
    settings_sig: str                   # what makes a chunk's audio (voice settings, provider)
    assemble_sig: str                   # what makes the mix and the timing
    text_hash: str                      # the spoken text of the whole narration
    cfg: dict = field(default_factory=dict)

    def by_id(self) -> dict[str, Chunk]:
        return {c.id: c for c in self.chunks}


def _sha(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def settings_signature(provider: str, worker: dict | None) -> str:
    """Everything outside the text that changes how a chunk sounds."""
    w = worker or {}
    ref = Path(str(w.get("reference") or "")).name
    return "|".join([provider, ref, str(w.get("exaggeration", "")), str(w.get("cfg_weight", "")), str(w.get("temperature", ""))])


def assemble_signature(chunks: list[Chunk], narration, settings: dict, cfg: dict) -> str:
    struct = [[c.id, c.beat, c.chapter, round(c.gap, 3), len(c.written)] for c in chunks]
    chapters = [[c.id, c.title, bool(c.card)] for c in narration.chapters]
    return _sha(files.canonical({"chunks": struct, "chapters": chapters, "tempo": settings["tempo"], "pad": settings["pad"],
                                 "padcfg": cfg["pad"], "tail": cfg["silence"]["tail"], "fade": cfg["fade_ms"],
                                 "loud": cfg["loudness"], "aac": cfg["aac_bitrate"]}))


def load_approved_narration(pdir: Path, *, need_approval: bool = True):
    """The narration of the project. VoiceError `narration_missing` / `narration_not_approved`."""
    n = store.load_narration(pdir)
    if n is None:
        raise VoiceError("narration_missing", "the project has no narration yet")
    if need_approval:
        o = store.load_outline(pdir)
        if not store.narration_approval(n, o)["approved"]:
            raise VoiceError("narration_not_approved", "the narration is not approved")
    return n


def make_plan(pdir: Path, *, cfg: dict | None = None, provider: str, worker: dict | None = None, narration=None,
              need_approval: bool = True) -> Plan:
    cfg = cfg or load_voice_config()
    n = narration if narration is not None else load_approved_narration(pdir, need_approval=need_approval)
    manifest = files.read_manifest(pdir) or {}
    seeds = manifest.get("seeds") if isinstance(manifest.get("seeds"), dict) else {}
    table = files.read_pronounce(pdir)
    settings = project_settings(files.read_settings(pdir), cfg)
    sig = settings_signature(provider, worker)
    chunks = build_chunks(n, table, cfg, sig, seeds)
    if not chunks:
        raise VoiceError("nothing_to_say", "the narration has no sentence to speak")
    text_hash = _sha("\n".join(f"{c.beat}:{c.th}" for c in chunks))
    return Plan(chunks, n, settings, table, seeds, provider, sig, assemble_signature(chunks, n, settings, cfg), text_hash, cfg)
