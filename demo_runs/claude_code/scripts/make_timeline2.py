import json, os
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(f"{H}/v2/timing2.json")); shots = json.load(open(f"{H}/v2/shots_final.json"))
ctx = json.load(open(f"{H}/assets/context/context_images.json"))
src = {"arnolfini_commons": {"url": "https://commons.wikimedia.org/wiki/File:Van_Eyck_-_Arnolfini_Portrait.jpg", "licence": "Public domain", "author": "Jan van Eyck", "size": "4386x6000"},
       "paele_commons": {"url": "https://commons.wikimedia.org/wiki/File:Jan_van_Eyck_069.jpg", "licence": "Public domain", "author": "Jan van Eyck", "size": "4169x3249"}}
key2name = {"A": "arnolfini_commons", "V": "paele_commons"}
for k, v in ctx.items():
    src[k] = {"url": v["page"], "download_url": v["download_url"], "licence": v["licence"], "author": v["author"], "size": "%dx%d" % tuple(v["actual_size"])}
words = [(w["s"], w["w"]) for b in T["beats"] for w in b["words"]]
out = []
for s in shots:
    img = s.get("image", ""); k = key2name.get(img, img)
    nar = " ".join(w for t, w in words if s["t0"] - 1e-6 <= t < s["t1"])
    out.append({"start": round(s["t0"], 3), "end": round(s["t1"], 3), "duration_s": round(s["t1"] - s["t0"], 2), "effect": s["effect"], "catalogue_ids": s["ids"], "image": k,
                "image_source": src.get(k, {"note": "generated in code (no external image)"}), "parameters": s["params"], "synced_phrase": s.get("words", ""), "narration_words": nar})
d = {"final_demo": {"duration_s": T["end"], "resolution": "1920x1080", "fps": 30, "atempo": T["atempo"], "wpm_first_to_last_incl_pauses_and_cards": T["wpm_first_to_last_incl_pauses_and_cards"],
     "wpm_speech_only": T["wpm_speech_only"], "words": T["words"], "alignment": T["alignment"], "cards": T["cards"], "shots": out},
     "sources": src, "music": "numpy-synthesised pad + low-passed noise room tone generated on the server by v2/server/audio_job2.py; no external file", "voice": {"engine": "local Chatterbox via stages.stage_4.chatterbox_tts.synthesize", "reference": "machiavelli_ref.wav", "settings": "exaggeration 0.35, cfg_weight 0.5, temperature 0.7 (module default), seed 42", "jobs": 3}}
json.dump(d, open(f"{H}/timeline.json", "w"), indent=1, ensure_ascii=False)
print("timeline.json", len(out), "shots")
