"""Build a local library from Wikimedia Commons recordings with unambiguous free recording licences.

Run explicitly: python -m bti.music.fetch --limit 3. Network is never used on import.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import library

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "BehindTheImageMusicLibrary/1.0 (Wikimedia Commons public API)"}


def _value(meta, key):
    obj = meta.get(key, {})
    return str(obj.get("value", "")) if isinstance(obj, dict) else ""


def _plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", s))).strip()


def licence(meta):
    """Return (accepted, reason or licence); contradictory or ambiguous metadata is refused."""
    short = _plain(_value(meta, "LicenseShortName")).casefold().strip()
    url = _plain(_value(meta, "LicenseUrl")).lower().rstrip("/")
    terms = _plain(_value(meta, "UsageTerms")).casefold()
    combined = " ".join((short, url, terms))
    if re.search(r"attribution|cc\s*by|/licenses/|share.?alike|all rights reserved", combined):
        return False, "the recording licence requires attribution/share-alike or restricts reuse"
    if short in ("cc0", "cc zero", "cc0 1.0") and (not url or url in ("https://creativecommons.org/publicdomain/zero/1.0", "http://creativecommons.org/publicdomain/zero/1.0")):
        return True, "CC0"
    if short in ("public domain", "pd", "public domain mark") and (not url or url in ("https://creativecommons.org/publicdomain/mark/1.0", "http://creativecommons.org/publicdomain/mark/1.0", "https://creativecommons.org/publicdomain/zero/1.0", "http://creativecommons.org/publicdomain/zero/1.0")):
        return True, "Public domain"
    return False, "the file's recording licence is missing, ambiguous, or not CC0/public domain"


def seed_plan():
    data = json.loads(Path(__file__).with_name("seeds.json").read_text(encoding="utf-8"))
    return [{"period": period, "composed": entry["composed"], "forces": entry["forces"],
             "composer": composer, "title": title, "query": composer + " " + title}
            for period, entry in data.items() for composer, title in entry["works"]]


def build_record(seed, ident, filename, meta, source, duration, loudness):
    ok, label = licence(meta)
    if not ok:
        raise ValueError(label)
    performer = _plain(_value(meta, "Performer"))
    composer_name = seed["composer"]
    if not performer and composer_name:
        description = _plain(_value(meta, "ImageDescription"))
        surname = re.escape(composer_name.split()[-1])
        match = re.match(r"^([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .'-]{2,80}?)\s+-\s*" + surname + r"(?:\s|[-,:])", description, re.I)
        if match:
            performer = match.group(1).strip()
    if performer.casefold() in {composer_name.casefold(), composer_name.split()[-1].casefold() if composer_name else ""}:
        performer = ""
    filename_title = urllib.parse.unquote(urllib.parse.urlparse(source).path.rsplit("/", 1)[-1]).removeprefix("File:").replace("_", " ")
    title = re.sub(r"\.[^.]+$", "", filename_title) or seed["title"]
    composer = seed["composer"]
    credit = title + (" — " + composer if composer else "")
    if performer:
        credit += "; performed by " + performer
    record = {"id": ident, "file": filename, "title": title, "composer": composer,
            "composed": seed["composed"], "period": seed["period"], "forces": seed["forces"],
            "duration": duration, "loudness": loudness, "license": label,
            "source": source, "credit": credit}
    if performer:
        record["performer"] = performer
    return record


def _json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def candidates(seed):
    params = {"action": "query", "format": "json", "formatversion": "2", "generator": "search",
              "gsrsearch": seed["query"], "gsrnamespace": "6", "gsrlimit": "10", "prop": "imageinfo",
              "iiprop": "url|mime|size|extmetadata"}
    result = _json(API + "?" + urllib.parse.urlencode(params))
    return result.get("query", {}).get("pages", [])


def _matches(page, seed):
    # The Commons search engine may return unrelated works. Require the composer's surname and
    # every significant title word in the file name; uncertain candidates remain for manual review.
    name = _plain(page.get("title", "")).casefold()
    surname = seed["composer"].split()[-1].casefold()
    words = [x for x in re.findall(r"[^\W_]+", seed["title"].casefold()) if len(x) > 3 or x.isdigit()]
    name_words = set(re.findall(r"[^\W_]+", name))
    return surname in name_words and bool(words) and all(w in name_words for w in words)


def _download(url, destination, limit):
    if not url.startswith("https://upload.wikimedia.org/"):
        raise ValueError("recording URL is not a Wikimedia upload")
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        with destination.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError("recording exceeds the download size limit")
                out.write(chunk)


def _convert(source, destination):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source), "-vn", "-c:a", "libopus", "-b:a", "96k", str(destination)], check=True)
    data = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(destination)], check=True, capture_output=True, text=True)
    duration = float(json.loads(data.stdout)["format"]["duration"])
    measured = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(destination), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"], check=True, capture_output=True, text=True)
    values = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", measured.stderr)
    if not values or duration <= 0 or float(values[-1]) <= -70:
        raise ValueError("could not measure recording loudness")
    return round(duration, 3), float(values[-1])


CATEGORIES = [
    ("Category:Audio files of the Open Goldberg Variations", "Johann Sebastian Bach", "baroque", "piano or harpsichord"),
    ("Category:Audio files of Open Well-Tempered Clavier, Book 1", "Johann Sebastian Bach", "baroque", "piano"),
    ("Category:Musopen", "", "", "unknown"),
    ("Category:Musopen Kickstarter Project", "", "", "unknown"),
    ("Category:Audio files of music by Frédéric Chopin", "Frédéric Chopin", "romantic", "unknown"),
    ("Category:Audio files of music by Claude Debussy", "Claude Debussy", "modern", "unknown"),
    ("Category:Audio files of music by Erik Satie", "Erik Satie", "modern", "unknown"),
    ("Category:Audio files of music by Ludwig van Beethoven", "Ludwig van Beethoven", "classical", "unknown"),
]


def _retry_delay(exc):
    value = exc.headers.get("Retry-After") if exc.headers else None
    if value:
        try:
            return max(1, float(value))
        except ValueError:
            try:
                return max(1, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                pass
    return 60


def _retry(call):
    failures = 0
    while True:
        try:
            return call()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503):
                raise
            delay = max(_retry_delay(exc), min(300, 5 * 2 ** min(failures, 6)))
            failures += 1
            print("Commons rate limit; waiting %.0f seconds" % delay, flush=True)
            time.sleep(delay)


def _category_page(category, continuation):
    params = {"action": "query", "format": "json", "formatversion": "2", "generator": "categorymembers",
              "gcmtitle": category, "gcmtype": "file|subcat", "gcmlimit": "50", "prop": "imageinfo",
              "iiprop": "url|mime|size|extmetadata", "maxlag": "5", **continuation}
    while True:
        result = _retry(lambda: _json(API + "?" + urllib.parse.urlencode(params)))
        error = result.get("error", {})
        if error.get("code") != "maxlag":
            if error:
                raise ValueError("Commons API: " + str(error))
            return result
        delay = max(5, float(error.get("lag", 5)))
        print("Commons maxlag; waiting %.0f seconds" % delay, flush=True)
        time.sleep(delay)


def _save_state(root, state):
    from bti.script.store import write_json_atomic
    write_json_atomic(root / "fetch-state.json", state)


def fetch(limit, root, max_bytes, max_downloads=None, *, categories=None, max_total_bytes=500*1024*1024):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rows = library.read(root)
    known = {r.get("source") for r in rows}
    entries = categories if categories is not None else CATEGORIES
    entries = [(entry, "", "", "unknown") if isinstance(entry, str) else tuple(entry) for entry in entries]
    state_path = root / "fetch-state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"queue": [{"category": c, "composer": composer, "period": period, "forces": forces,
                            "continue": {}, "depth": 0} for c, composer, period, forces in entries],
                 "pending": [], "seen": [x[0] for x in entries], "bytes": 0}
    # Checkpoints can outlive the catalogue's category descriptions.
    category_forces = {category: forces for category, _, _, forces in entries}
    for item in [*state["queue"], *state["pending"]]:
        if item["category"] in category_forces:
            item["forces"] = category_forces[item["category"]]
    added = downloads = 0
    max_downloads = max_downloads if max_downloads is not None else limit * 5
    while (state["queue"] or state["pending"]) and added < limit and downloads < max_downloads:
        if not state["pending"]:
            item = state["queue"][0]
            print("category: " + item["category"], flush=True)
            try:
                result = _category_page(item["category"], item["continue"])
            except (OSError, ValueError) as exc:
                print("category failed: %s" % exc, flush=True)
                _save_state(root, state)
                break
            time.sleep(1)
            pages = result.get("query", {}).get("pages", [])
            for page in pages:
                if page.get("ns") == 14 and item["depth"] < 2 and page.get("title") not in state["seen"]:
                    state["seen"].append(page["title"])
                    state["queue"].append({**item, "category": page["title"], "continue": {}, "depth": item["depth"] + 1})
                elif page.get("ns", 6) == 6:
                    state["pending"].append({"page": page, "category": item["category"], "composer": item["composer"],
                                             "period": item["period"], "forces": item["forces"]})
            continuation = result.get("continue")
            if continuation:
                item["continue"] = continuation
            else:
                state["queue"].pop(0)
            _save_state(root, state)
            continue
        pending = state["pending"][0]
        page = pending["page"]
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        title, source = page.get("title", "unknown"), info.get("descriptionurl", "")
        ok, reason = licence(meta)
        size = info.get("size", max_bytes + 1)
        mime = info.get("mime", "")
        if (not ok or not (mime.startswith("audio/") or mime == "application/ogg") or
            not isinstance(size, int) or size > max_bytes or not source.startswith("https://commons.wikimedia.org/") or source in known):
            print("skipped %s: %s" % (title, reason if not ok else "known, not audio, missing source, or too large"), flush=True)
        elif state["bytes"] + size > max_total_bytes:
            print("download byte limit reached; checkpoint saved", flush=True)
            break
        else:
            ident = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
            filename, dest = ident + ".opus", root / (ident + ".opus")
            if dest.exists():
                print("skipped %s: output file already exists" % title, flush=True)
            else:
                raw = converted = None
                try:
                    with tempfile.NamedTemporaryFile(dir=root, prefix=".fetch-", delete=False) as f:
                        raw = Path(f.name)
                    with tempfile.NamedTemporaryFile(dir=root, prefix=".fetch-", suffix=".opus", delete=False) as f:
                        converted = Path(f.name)
                    downloads += 1
                    state["bytes"] += size
                    _save_state(root, state)
                    _retry(lambda: _download(info.get("url", ""), raw, max_bytes))
                    time.sleep(5)
                    duration, loudness = _convert(raw, converted)
                    composer = _plain(_value(meta, "Composer")) or pending["composer"]
                    seed = {"title": title, "composer": composer, "composed": "", "period": pending["period"], "forces": pending["forces"]}
                    record = build_record(seed, ident, filename, meta, source, duration, loudness)
                    record["category"] = pending["category"]
                    converted.replace(dest)
                    try:
                        library.write(rows + [record], root)
                    except Exception:
                        dest.unlink()
                        raise
                    rows.append(record)
                    known.add(source)
                    added += 1
                    print("added %s (%s, %.1f LUFS)" % (title, reason, loudness), flush=True)
                except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                    print("refused %s: %s" % (title, exc), flush=True)
                finally:
                    if raw is not None:
                        raw.unlink(missing_ok=True)
                    if converted is not None:
                        converted.unlink(missing_ok=True)
        state["pending"].pop(0)
        _save_state(root, state)
    print("added %d recording(s); downloaded %.1f MB" % (added, state["bytes"] / 1024**2), flush=True)
    return added


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--directory", type=Path, default=None)
    parser.add_argument("--max-mb", type=int, default=20)
    parser.add_argument("--max-downloads", type=int, default=None)
    parser.add_argument("--max-total-mb", type=int, default=500)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.max_mb < 1 or args.max_total_mb < 1 or (args.max_downloads is not None and args.max_downloads < 1):
        parser.error("limits must be positive")
    fetch(args.limit, args.directory or library.directory(), args.max_mb * 1024 * 1024, args.max_downloads, max_total_bytes=args.max_total_mb * 1024 * 1024)


if __name__ == "__main__":
    main()
