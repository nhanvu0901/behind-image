"""A fake `agy` that speaks the stream-json protocol. Behaviour is set by the file `mode` next to this script.

It reads one NDJSON `user` line per turn from stdin, writes its work into out/ (the working directory is the workspace), emits
init / step_update / result events, and loops until stdin closes. Modes: ok, repair (writes a bad file first, fixes it on the
second turn), bad (never fixes), slow (sleeps forever, with a child), tamper (changes a file in the project), error, auth, exits
(leaves after the first turn), noresult."""
import json
import os
import subprocess
import sys
import time

here = os.path.dirname(os.path.abspath(__file__))
mode = open(os.path.join(here, "mode")).read().strip()
args = sys.argv[1:]
if args[:1] == ["--help"]:
    print("Usage: agy\n  --input-format  x\n  --output-format  x\n  --dangerously-skip-permissions  x\n  --model  x")
    sys.exit(0)
cfg = json.load(open(os.path.join(here, "cfg.json")))
open(os.path.join(here, "calls.jsonl"), "a").write(json.dumps({"argv": args, "cwd": os.getcwd(), "env": sorted(os.environ)}) + "\n")


def emit(ev):
    print(json.dumps(ev), flush=True)


def result(status="SUCCESS", **kw):
    r = {"conversation_id": "conv-1", "status": status, "response": "done", "num_turns": 1}
    r.update(kw)
    emit({"event": "result", "result": r})


def write_specs(good=True):
    os.makedirs("out", exist_ok=True)
    for cid, sp in cfg["specs"].items():
        sp = json.loads(json.dumps(sp))
        if not good:
            sp["shots"][1]["technique"] = "NOPE-9"
        open(os.path.join("out", cid + ".json"), "w").write(json.dumps(sp))
    open(os.path.join("out", "notes.md"), "w").write("Fake agent summary\n")


turn = 0
if mode == "exits":                      # the turn counter survives the process: every restart is the next turn
    tf = os.path.join(here, "turns")
    turn = int(open(tf).read()) if os.path.exists(tf) else 0
emit({"event": "init", "conversation_id": "conv-1", "init": {"tools": ["view_file"]}})
for line in sys.stdin:
    msg = json.loads(line)
    assert msg["event"] == "user"
    turn += 1
    open(os.path.join(here, "prompts.jsonl"), "a").write(json.dumps(msg["message"]["content"]) + "\n")
    for i in range(3):
        emit({"event": "step_update", "step_update": {"step_index": turn * 10 + i, "state": "DONE", "step_type": "view_file"}})
    if mode == "ok":
        write_specs(True)
        result()
    elif mode == "repair":
        write_specs(turn >= 2)
        result()
    elif mode == "bad":
        write_specs(False)
        result()
    elif mode == "tamper":
        write_specs(True)
        open(cfg["victim"], "a").write("x")
        result()
    elif mode == "error":
        result("ERROR", response="", error="something broke")
        sys.exit(1)
    elif mode == "auth":
        sys.stderr.write("authentication required\n")
        sys.exit(1)
    elif mode == "noresult":
        sys.exit(0)
    elif mode == "exits":
        open(os.path.join(here, "turns"), "w").write(str(turn))
        write_specs(turn >= 2)
        result()
        sys.exit(0)
    elif mode == "slow":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        open(os.path.join(here, "pids"), "w").write("%d %d" % (os.getpid(), child.pid))
        write_specs(True)
        time.sleep(120)
