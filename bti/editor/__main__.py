"""python -m bti.editor [--host 127.0.0.1] [--port 8560]"""
import argparse

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8560)
    a = ap.parse_args()
    if a.port == 8550:
        raise SystemExit("port 8550 belongs to the comic UI")
    uvicorn.run("bti.editor.app:create_app", factory=True, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
