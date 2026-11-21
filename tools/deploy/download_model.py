r"""Run ON the server with .venv-align: downloads a faster-whisper model into the project cache (no model is loaded).
Exact command (cmd.exe):
  set HF_HOME=D:\code\behind-the-image\cache\hf&& set HF_HUB_DISABLE_TELEMETRY=1&& D:\code\behind-the-image\.venv-align\Scripts\python.exe D:\code\behind-the-image\tools\deploy\download_model.py small.en
"""
import os
import sys

name = sys.argv[1] if len(sys.argv) > 1 else "small.en"
cache = os.path.join(os.environ["HF_HOME"], "hub")
from faster_whisper.utils import download_model

print(download_model(name, cache_dir=cache))
