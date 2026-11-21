"""Configuration of the voice stage: `config/voice.json` (the stage's own numbers), per-project settings, and the machine
paths read from `config/server.json` (written by CORE; one block per platform).

Nothing here holds a path of another machine: the Python of the voice worker, the worker script, the reference voice and the
aligner all come from `config/server.json`. The keys read (all optional; a missing one means "not installed here"):

    {"windows": {"voice":   {"python": "...", "worker": "...", "reference": "...",
                             "exaggeration": 0.35, "cfg_weight": 0.5, "temperature": 0.7, "device": "cpu"},
                 "aligner": {"python": "...", "model_dir": "..."}},
     "default": {...}}
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VOICE_CONFIG = REPO_ROOT / "config" / "voice.json"
SERVER_CONFIG = REPO_ROOT / "config" / "server.json"

TEMPO_KEYS = ("tempo",)
# The two silences a project may set for itself (`voice/settings.json`, keys `lead` and `title`), in seconds: the silence before the first
# word and the silence that holds the channel-name beat. A project without its own value uses `silence.lead` / `silence.title`.
LEAD_RANGE = (0.2, 15.0)
TITLE_RANGE = (3.0, 30.0)
SILENCE_RANGES = {"lead": LEAD_RANGE, "title": TITLE_RANGE}
DEFAULT_SYNTH = {"exaggeration": 0.35, "cfg_weight": 0.5, "temperature": 0.7, "device": "cpu"}

_BUILTIN = {
    "silence": {"sentence": 0.20, "beat": 0.45, "chapter": 1.0, "card": 3.2, "card_length": 2.8, "title": 6.2, "lead": 0.35, "tail": 2.5},
    "intro": {"lead": 5.0, "title": 10.2},
    "new_project_tempo": 1.1,
    "tempo": 1.0, "tempo_range": [1.0, 1.2],
    "pad": {"enabled": True, "level_db": -24, "duck": 0.37, "chord_seconds": 10},
    "chunk": {"min_chars": 40, "max_chars": 280},
    "target_minutes": 18, "max_part_minutes": 25,
    "estimate": {"load_seconds": 120, "seconds_per_character": 0.55, "chars_per_audio_second": 15.0},
    "fade_ms": 8, "loudness": {"i": -15, "tp": -1.5, "lra": 11}, "aac_bitrate": "192k", "provider": "chatterbox",
    "aligner": {"provider": "auto", "model_en": "small.en", "model": "small", "margin": 0.15, "match_floor": 0.6},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_voice_config(path: Path | None = None, override: dict | None = None) -> dict:
    """`config/voice.json` over the built-in defaults, then `override` (tests). A missing or unreadable file means defaults."""
    cfg = copy.deepcopy(_BUILTIN)
    p = Path(path) if path else VOICE_CONFIG
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg = _merge(cfg, data)
    except (OSError, ValueError):
        pass
    return _merge(cfg, override or {}) if override else cfg


def platform_block() -> str:
    return "windows" if sys.platform == "win32" else "default"


def load_server_config(path: Path | None = None) -> dict:
    """The block of `config/server.json` for this platform ({} when the file or the block is missing)."""
    p = Path(path) if path else SERVER_CONFIG
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    block = data.get(platform_block())
    if not isinstance(block, dict):
        block = data.get("default") if isinstance(data.get("default"), dict) else {}
    return block


def _first(d: dict, names: tuple[str, ...]):
    for n in names:
        if d.get(n) not in (None, ""):
            return d[n]
    return None


def voice_worker(server: dict) -> dict | None:
    """The comic voice worker as `{python, worker, reference, exaggeration, cfg_weight, temperature, device}`, or None when the
    machine has none configured."""
    v = _first(server or {}, ("voice", "comic_voice", "voice_worker"))
    if not isinstance(v, dict):
        return None
    python = _first(v, ("python", "venv_python"))
    worker = _first(v, ("worker", "worker_script"))
    ref = _first(v, ("reference", "reference_voice", "ref"))
    if not (python and worker and ref):
        return None
    out = {"python": str(python), "worker": str(worker), "reference": str(ref)}
    for k, dflt in DEFAULT_SYNTH.items():
        out[k] = v.get(k, dflt)
    return out


def aligner_config(server: dict) -> dict | None:
    """The aligner as `{python, model_dir}` or None when it is not installed on this machine."""
    a = _first(server or {}, ("aligner", "align"))
    if not isinstance(a, dict):
        return None
    python = _first(a, ("python", "venv_python"))
    if not python:
        return None
    return {"python": str(python), "model_dir": str(_first(a, ("model_dir", "cache", "model_cache")) or ""),
            "model": str(a.get("model") or "")}


# ---------------------------------------------------------------- per-project settings
def clamp_tempo(v, cfg: dict) -> float:
    lo, hi = cfg.get("tempo_range", [1.0, 1.2])
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = cfg.get("tempo", 1.0)
    if x != x:
        x = cfg.get("tempo", 1.0)
    return round(min(max(x, lo), hi), 3)


def _in_range(v, rng) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and rng[0] <= v <= rng[1]


def silence_settings(saved: dict | None, cfg: dict) -> dict:
    """The two per-project silences in force: `{"lead", "title", "own": {"lead": bool, "title": bool}, "default": {"lead", "title"},
    "intro": {"lead", "title"}}`. A project's own value (a number in its range) wins; otherwise the value is `silence.lead` /
    `silence.title` of the voice config, exactly as before the project could choose, so a project that never set one keeps its
    timing and its `assemble_sig`. `intro` is what a project the app creates gets written at creation."""
    s = saved if isinstance(saved, dict) else {}
    out: dict = {"own": {}, "default": {}, "intro": {}}
    for k, rng in SILENCE_RANGES.items():
        dflt = float(cfg["silence"][k])
        own = _in_range(s.get(k), rng)
        out[k] = float(s[k]) if own else dflt
        out["own"][k] = own
        out["default"][k] = dflt
        out["intro"][k] = float((cfg.get("intro") or {}).get(k, dflt))
    return out


def silenced(cfg: dict, saved: dict | None) -> dict:
    """`cfg` with the project's own `lead` and `title` in `silence` (the same object when the project has none)."""
    sil = silence_settings(saved, cfg)
    if not any(sil["own"].values()):
        return cfg
    out = dict(cfg)
    out["silence"] = {**cfg["silence"], "lead": sil["lead"], "title": sil["title"]}
    return out


def project_settings(saved: dict | None, cfg: dict) -> dict:
    """What the owner can change per project: `tempo` and `pad` (on/off). Everything else is in config files."""
    s = saved if isinstance(saved, dict) else {}
    pad = s.get("pad")
    return {"tempo": clamp_tempo(s.get("tempo", cfg.get("tempo", 1.0)), cfg),
            "pad": bool(cfg["pad"].get("enabled", True)) if not isinstance(pad, bool) else pad}
