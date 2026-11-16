import os, sys, json, time
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
REPO = r"D:\code\comic-book-pipeline"
sys.path.insert(0, REPO)
os.environ["CHATTERBOX_VENV"] = r"D:\code\comic-book-pipeline\.venv-chatterbox"
from stages.stage_4.chatterbox_tts import synthesize, _chunks
W = r"D:\bench\claude_code"
beats = json.load(open(os.path.join(W, "beats_text.json"), encoding="utf8"))
text = " ".join(b["text"] for b in beats)
chunks = _chunks(text)
assert chunks == [b["text"] for b in beats], "chunking differs from beats"
t0 = time.time()
r = synthesize(text, voice_id=r"D:\code\comic-book-pipeline\assets\voices\machiavelli_ref.wav",
               exaggeration=0.35, cfg_weight=0.5, seed=42, log=lambda m: print(m, flush=True))
open(os.path.join(W, "voice_raw.wav"), "wb").write(r.wav_bytes)
json.dump({"sample_rate": r.sample_rate, "word_timestamps": r.word_timestamps, "chunks": chunks,
           "seconds": time.time() - t0}, open(os.path.join(W, "voice_raw_words.json"), "w"), indent=1)
print("TTS_OK", len(r.wav_bytes), "bytes", round(time.time() - t0, 1), "s", flush=True)
