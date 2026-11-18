import os
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
