import os,sys,json,subprocess,numpy as np
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.environ["HF_HOME"]=os.path.join(HERE,"hf_cache")
g=sys.argv[1]; V=os.path.join(HERE,"v2","voice"); out=os.path.join(V,f"whisper_J{g}.json")
from faster_whisper import WhisperModel
m=WhisperModel("small.en",device="cpu",compute_type="int8",download_root=os.path.join(HERE,"hf_cache"),cpu_threads=6)
raw=subprocess.run(["ffmpeg","-v","error","-i",os.path.join(V,f"voice_J{g}.wav"),"-ac","1","-ar","16000","-f","f32le","-"],capture_output=True).stdout
segs,_=m.transcribe(np.frombuffer(raw,np.float32),language="en",word_timestamps=True,beam_size=5,condition_on_previous_text=False)
w=[{"w":x.word.strip(),"s":x.start,"e":x.end} for s in segs for x in s.words]
json.dump(w,open(out,"w")); print(g,len(w),"words")
