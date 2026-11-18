"""Canned provider for tests and for trying the page without a key. No network.

It reads the prompt it is given (the same text a real model gets) and answers in the layouts the parsers read.
Owner notes can steer it, which is how the page and the tests exercise the retry, cancel and failure paths:
  [mock:bad c02]        the first answer for chapter c02 has markup in it; the retry answer is clean
  [mock:alwaysbad c02]  every answer for chapter c02 has markup in it (the job fails after its retry)
  [mock:badoutline]     the first outline answer cannot be read; the retry is fine
  [mock:slow]           the call takes ~10 seconds (cancel and timeout can be tried)
  [mock:ratelimit]      the call fails with a rate-limit error
"""
from __future__ import annotations

import re
import time

from . import ProviderError

CALLS: list[dict] = []           # what the mock was asked, for tests (prompts only, never keys)
_CANNED: list[str] = []
DELAY = 0.05


def set_canned(answers: list[str]) -> None:
    global _CANNED
    _CANNED = list(answers)


def clear_canned() -> None:
    global _CANNED
    _CANNED = []


def _sleep(seconds: float, cancel) -> None:
    end = time.time() + seconds
    while time.time() < end:
        if cancel is not None and cancel.is_set():
            raise ProviderError("cancelled", "cancelled")
        time.sleep(0.05)


def _clean(s: str) -> str:
    s = re.sub(r"[\[\]<>|*#`{}]", "", s)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[;:—–]", ",", s)
    return re.sub(r"\s+", " ", s).strip()


def _first_sentence(t: str, limit: int = 230) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", t.strip())
    s = (m.group(1) if m else t.strip())
    return _clean(s)[:limit].rstrip(" ,") + ("" if s.endswith((".", "!", "?")) else ".")


def _paras(user: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^\[([A-Z]{3}-\d{2,3})\](?: \(quotation\))? (.+)$", user, re.M)]


def _mock_outline(user: str, retry: bool) -> str:
    paras = _paras(user)
    if "[mock:badoutline]" in user and not retry:
        return "I could not work out a structure for this one. Sorry.\n\nHere are some thoughts about the painting."
    target = 2000
    m = re.search(r"add up to about (\d+) words", user)
    if m:
        target = int(m.group(1))
    if not paras:
        paras = [("PAY-01", "The picture rewards a long look.")]
    title = (re.search(r"^Title: (.+)$", user, re.M) or [0, "the painting"])[1]
    details = re.findall(r"^(D\d+) (.+?)  \[", user, re.M)
    chap_titles = ["COLD OPEN", "THE MERCHANT CITY", "THE ROOM", "THE MIRROR", "TWO READINGS", "CLOSING"]
    n = len(chap_titles)
    chunk = max(1, len(paras) // 8)
    facts, certs = [], ["established", "likely", "disputed", "established"]
    for i in range(8):
        sel = paras[(i * chunk) % len(paras):][:2] or paras[:1]
        ids = ", ".join(p[0] for p in sel)
        cert = certs[i % 4]
        line = f"f{i + 1:02d} | {cert} | {ids} | {_first_sentence(sel[0][1])}"
        if cert == "disputed":
            line += f" | conflict: the sources frame this differently ({sel[0][0]} against {sel[-1][0]})"
        facts.append(line)
    budgets = [round(target * x) for x in (0.10, 0.17, 0.18, 0.20, 0.20, 0.15)]
    L = ["Here is the outline.", "", "```", "OUTLINE", "", f"THESIS: What is {title} really showing, and how much of it can the sources prove?", "",
         "HOOKS", f"h1: Look at the mirror on the back wall of {title}, and ask who is standing in it.",
         "h2: Most people call this a wedding portrait, but almost nothing in the room says so.",
         "h3: A painter signed his name above a mirror as if he were a witness.", "HOOK CHOICE: h1", "", "FACTS"] + facts + ["", "CHAPTERS"]
    for i, t in enumerate(chap_titles):
        role = "cold_open" if i == 0 else "closing" if i == n - 1 else "chapter"
        fs = ", ".join(f"f{(i + k) % 8 + 1:02d}" for k in range(2))
        show = "; ".join(filter(None, [details[i][0] if i < len(details) else "", "the whole painting" if i in (0, n - 1) else "a detail of the room"]))
        L += [f"## c{i + 1:02d} {t}", f"ROLE: {role}", f"CARD: {'no' if i == 0 else 'yes'}", f"BUDGET: {budgets[i]}",
              f"PURPOSE: {'Open on a puzzle the viewer can see' if i == 0 else 'Close on what the sources allow' if i == n - 1 else 'Carry the argument by one object at a time'}.",
              f"FACTS: {fs}", f"SHOW: {show}", ""]
    L += [f"TARGET WORDS: {target}", "```", "", "Word count: n/a"]
    return "\n".join(L)


def _chapter_beats(cid: str, title: str, budget: int, claims: list[str], bad: bool) -> list[str]:
    out, words = [], 0
    pool = claims or ["The picture rewards a long look."]
    i = 0
    while words < budget:
        c = pool[i % len(pool)]
        joins = ["Look closely and you will see it. ", "Here the sources help us, though they do not agree on everything. ",
                 "That detail is small, but it carries a lot of weight, and it is worth slowing down for. ",
                 "Now move your eye across the panel, and notice how the room holds its objects in place. "]
        text = joins[i % len(joins)] + c + " So the question becomes what a viewer in the fourteen thirties would have made of it."
        out.append(text)
        words += len(text.split())
        i += 1
    if bad and out:
        out[0] = "[PAUSE] **" + out[0] + "** <b>"
    return out


def _mock_script(user: str, retry: bool) -> str:
    sec = user.split("THE APPROVED OUTLINE", 1)[-1].split("YOUR TASK", 1)[0]
    from ..parse import parse_outline
    o = parse_outline(sec).outline
    m = re.search(r"Chapters to write now: ([\w, ]+)", user)
    want = [x.strip() for x in m.group(1).split(",")] if m else [c.id for c in (o.chapters if o else [])]
    facts = {f.id: f for f in (o.facts if o else [])}
    out = ["Sure, here is the narration.", "", "HOOK OPTIONS", "1. Look at the mirror.", "2. A wedding?", "", "FINAL SCRIPT", ""]
    for c in (o.chapters if o else []):
        if c.id not in want:
            continue
        bad = (f"[mock:alwaysbad {c.id}]" in user) or (f"[mock:bad {c.id}]" in user and not retry)
        claims = [facts[f].claim for f in c.facts if f in facts]
        out.append(f"## {c.id} {c.title}")
        for k, t in enumerate(_chapter_beats(c.id, c.title, c.word_budget, claims, bad)):
            fs = ", ".join(c.facts[k % max(1, len(c.facts)):][:2]) if c.facts else ""
            show = (c.show[k % len(c.show)] if c.show else "the whole painting")
            out += [t, f">> facts: {fs} | show: {show}", ""]
    out += ["WORD COUNT: n/a"]
    return "\n".join(out)


def complete(spec: dict, system: str, user: str, *, timeout: float = 60, on_progress=None, cancel=None) -> str:
    from ..prompting import RETRY_MARK
    CALLS.append({"model": spec.get("id"), "user_len": len(user), "retry": RETRY_MARK in user,
                  "user": user})
    if len(CALLS) > 200:
        del CALLS[:100]
    if cancel is not None and cancel.is_set():
        raise ProviderError("cancelled", "cancelled")
    if "[mock:ratelimit]" in user:
        raise ProviderError("rate_limit", "rate limit or quota reached (mock)")
    _sleep(10 if "[mock:slow]" in user else DELAY, cancel)
    if _CANNED:
        ans = _CANNED.pop(0)
        if on_progress:
            on_progress(1.0)
        return ans
    retry = RETRY_MARK in user
    if "PHASE: outline" in user[:40]:
        text = _mock_outline(user, retry)
    elif "PHASE: script" in user[:40]:
        text = _mock_script(user, retry)
    else:
        text = "mock response"
    if on_progress:
        on_progress(1.0)
    return text
