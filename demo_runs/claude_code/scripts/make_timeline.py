"""timeline.json: final_demo shots + beats/words + reel segments + sources/licences + audio info."""
import json, os
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(f"{H}/timing.json"))
shots = json.load(open(f"{H}/ref/final_shots.json"))
reel = json.load(open(f"{H}/ref/server/technique_reel_segments.json")) if os.path.exists(f"{H}/ref/server/technique_reel_segments.json") else json.load(open(f"{H}/ref/reel_plan.json"))
import sys; sys.path.insert(0, f"{H}/scripts")
from cap_rows import R
audio = json.load(open(f"{H}/ref/server/audio_stats.json")) if os.path.exists(f"{H}/ref/server/audio_stats.json") else {}
sources = {
 "arnolfini_commons": {"file": "assets/commons/arnolfini_commons.jpg", "size": "4386x6000", "url": "https://commons.wikimedia.org/wiki/File:Van_Eyck_-_Arnolfini_Portrait.jpg",
                       "download_url": "https://upload.wikimedia.org/wikipedia/commons/3/33/Van_Eyck_-_Arnolfini_Portrait.jpg", "licence": "Public domain (Wikimedia Commons: {{PD-Art}}, painting 1434)", "downloaded_with": "curl, generic User-Agent"},
 "paele_commons": {"file": "assets/commons/paele_commons.jpg", "size": "4169x3249", "url": "https://commons.wikimedia.org/wiki/File:Jan_van_Eyck_069.jpg",
                   "download_url": "https://upload.wikimedia.org/wikipedia/commons/f/fd/Jan_van_Eyck_069.jpg", "licence": "Public domain (Wikimedia Commons, painting 1434)", "downloaded_with": "curl, generic User-Agent"},
 "pdf_images": {"files": "assets/pdf_images/*.jpeg (8 images, p23,25,26,29,30,31,32,35)", "licence": "Public-domain paintings extracted from the supplied book PDF (used in reel only: CMP-05 print-vs-scan, p25..); see manifest.json"},
 "music": {"source": "numpy-synthesised pad generated locally by server/audio_job.py, no external files", "licence": "n/a (generated)"},
 "voice": {"engine": "local Chatterbox via stages.stage_4.chatterbox_tts.synthesize", "reference": "assets/voices/machiavelli_ref.wav", "settings": "exaggeration 0.35, cfg_weight 0.5, temperature 0.7 (module default), seed 42", "atempo": T["atempo"]},
}
out = {"final_demo": {"duration_s": T["end"], "resolution": "1920x1080", "fps": 30, "title_card_s": T["title"], "atempo": T["atempo"],
        "speech_rate_wpm_first_to_last_incl_pauses": T["wpm_first_to_last_incl_pauses"],
        "shots": shots,
        "beats": {k: {"start": v["start"], "end": v["end"], "text": " ".join(w["w"] for w in v["words"]),
                      "words": [{"w": w["w"], "start": w["s"], "end": w["e"], "alignment": w["src"]} for w in v["words"]]} for k, v in T["beats"].items()},
        "audio": audio},
       "technique_reel": {"resolution": "1920x1080", "fps": 30, "segments": [dict(s, status=R[s["id"]][0], method=R[s["id"]][1], reference=R[s["id"]][2], used=R[s["id"]][3]) for s in reel]},
       "sources": sources}
json.dump(out, open(f"{H}/timeline.json", "w"), indent=1)
print("timeline.json written", len(shots), "shots", len(reel), "segments")
