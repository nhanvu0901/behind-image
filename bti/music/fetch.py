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
    performer = _plain(_value(meta, "Artist"))
    if not performer:
        raise ValueError("performer is absent from the file metadata")
    filename_title = urllib.parse.unquote(urllib.parse.urlparse(source).path.rsplit("/", 1)[-1]).removeprefix("File:").replace("_", " ")
    title = re.sub(r"\.[^.]+$", "", filename_title) or seed["title"]
    composer = seed["composer"]
    credit = "%s — %s; performed by %s" % (title, composer, performer)
    return {"id": ident, "file": filename, "title": title, "composer": composer,
            "composed": seed["composed"], "period": seed["period"], "forces": seed["forces"],
            "duration": duration, "loudness": loudness, "performer": performer, "license": label,
            "source": source, "credit": credit}


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


def fetch(limit, root, max_bytes, max_downloads=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rows = library.read(root)
    known = {r.get("source") for r in rows}
    added = 0
    downloads = 0
    max_downloads = max_downloads if max_downloads is not None else limit * 3
    seeds = sorted(seed_plan(), key=lambda row: "instrumental" not in row["forces"])
    for seed in seeds:
        if added >= limit or downloads >= max_downloads:
            break
        try:
            pages = candidates(seed)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                print("Commons rate limit reached; try again later")
                break
            print("search failed for %s: %s" % (seed["query"], exc))
            continue
        except (OSError, ValueError) as exc:
            print("search failed for %s: %s" % (seed["query"], exc))
            break
        for page in pages:
            if downloads >= max_downloads:
                break
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            ok, reason = licence(meta)
            title = page.get("title", "unknown")
            if not ok:
                print("refused %s: %s" % (title, reason))
                continue
            if not _matches(page, seed):
                print("refused %s: filename does not identify the composer and work" % title)
                continue
            if not str(info.get("mime", "")).startswith("audio/") or info.get("size", max_bytes + 1) > max_bytes:
                print("refused %s: not audio or too large" % title)
                continue
            source = info.get("descriptionurl", "")
            if source in known or not source.startswith("https://commons.wikimedia.org/"):
                continue
            ident = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
            filename = ident + ".opus"
            dest = root / filename
            if dest.exists():
                print("refused %s: output file already exists" % title)
                continue
            try:
                # Temporary files stay in the selected library and are removed individually.
                with tempfile.NamedTemporaryFile(dir=root, prefix=".fetch-", delete=False) as f:
                    raw = Path(f.name)
                with tempfile.NamedTemporaryFile(dir=root, prefix=".fetch-", suffix=".opus", delete=False) as f:
                    converted = Path(f.name)
                try:
                    downloads += 1
                    _download(info.get("url", ""), raw, max_bytes)
                    duration, loudness = _convert(raw, converted)
                    record = build_record(seed, ident, filename, meta, source, duration, loudness)
                    converted.replace(dest)
                    try:
                        library.write(rows + [record], root)
                    except Exception:
                        dest.unlink()
                        raise
                finally:
                    raw.unlink(missing_ok=True)
                    converted.unlink(missing_ok=True)
                rows.append(record)
                known.add(source)
                added += 1
                print("added %s (%s, %.1f LUFS)" % (title, reason, loudness))
                break
            except Exception as exc:
                print("refused %s: %s" % (title, exc))
    print("added %d recording(s)" % added)
    return added


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--directory", type=Path, default=None)
    parser.add_argument("--max-mb", type=int, default=20)
    parser.add_argument("--max-downloads", type=int, default=None)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.max_mb < 1 or (args.max_downloads is not None and args.max_downloads < 1):
        parser.error("limits must be positive")
    fetch(args.limit, args.directory or library.directory(), args.max_mb * 1024 * 1024, args.max_downloads)


if __name__ == "__main__":
    main()
