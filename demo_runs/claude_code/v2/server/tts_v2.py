import os, sys, json, time
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"; sys.dont_write_bytecode = True
sys.path.insert(0, r"D:\code\comic-book-pipeline")
os.environ["CHATTERBOX_VENV"] = r"D:\code\comic-book-pipeline\.venv-chatterbox"
from stages.stage_4.chatterbox_tts import synthesize, _chunks
W = r"D:\bench\claude_code"; g = sys.argv[1]
d = json.load(open(os.path.join(W, "beats_v2.json"), encoding="utf8"))[g]
assert _chunks(d["text"]) == d["beats"], "chunking differs from beat list"
print("beats", len(d["beats"]), flush=True)
t0 = time.time()
r = synthesize(d["text"], voice_id=r"D:\code\comic-book-pipeline\assets\voices\machiavelli_ref.wav", exaggeration=0.35, cfg_weight=0.5, seed=42, log=lambda m: print(m, flush=True))
open(os.path.join(W, "voice_J%s.wav" % g), "wb").write(r.wav_bytes)
json.dump({"sample_rate": r.sample_rate, "word_timestamps": r.word_timestamps, "beats": d["beats"], "seconds": time.time() - t0}, open(os.path.join(W, "voice_J%s_words.json" % g), "w"))
print("TTS_OK", round(time.time() - t0, 1), "s", flush=True)
