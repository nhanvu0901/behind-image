"""Build a voice-keyed music mix; picture streams are never touched here."""
from __future__ import annotations


def mix_command(ffmpeg, voice, cues, out, duration):
    """Cues are (recording path, resolved cue) pairs, already validated."""
    if not cues:
        raise ValueError("a music mix needs at least one cue")
    cmd = [*ffmpeg, "-y", "-v", "error", "-nostdin", "-i", str(voice)]
    for path, _ in cues:
        cmd.extend(["-i", str(path)])
    filters = ["[0:a]apad=whole_dur=%.6f,atrim=duration=%.6f,asplit=2[voice][key]" % (duration, duration)]
    tracks = []
    for i, (_, cue) in enumerate(cues, 1):
        length = cue["end"] - cue["start"]
        track = ("[%d:a]atrim=start=%.6f:duration=%.6f,asetpts=PTS-STARTPTS,volume=%.3fdB" %
                 (i, cue["offset"], length, cue["level_db"]))
        if cue["fade_in"]:
            track += ",afade=t=in:st=0:d=%.6f" % cue["fade_in"]
        if cue["fade_out"]:
            track += ",afade=t=out:st=%.6f:d=%.6f" % (length - cue["fade_out"], cue["fade_out"])
        track += ",adelay=%d:all=1[m%d]" % (round(cue["start"] * 1000), i)
        filters.append(track)
        tracks.append("[m%d]" % i)
    filters.append("".join(tracks) + "amix=inputs=%d:duration=longest:normalize=0[music]" % len(tracks))
    filters.append("[music][key]sidechaincompress=threshold=0.005:ratio=8:attack=30:release=500[duck]")
    filters.append("[voice][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    cmd.extend(["-filter_complex", ";".join(filters), "-map", "[out]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "%.6f" % duration, str(out)])
    return cmd
