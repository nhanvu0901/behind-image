"""Build docs/PAINTINGS.md: one row per artwork of the library, with what the pipeline needs to queue it.

Run from the repository root:  python3 -I tools/paintings_table.py [--check] [path/to/index.json]
Reads only: library/artworks.json, library/dossiers/*/dossier.json. The research columns (YouTube coverage, the Commons
reproduction, the note) come from NOTES below: the findings of the research of 2026-11-19 (worker `nextpaint`), matched to
artworks by words of the title and the artist. `--check` prints the matches instead of writing the file.

With the path of a copy of the server's `output/index.json` (the index of the output folders, see bti/output/index.py) the table marks each artwork of the index
as `done` (its folder holds the finished video) or `in-progress` with what the index says (the project, the step, the length), instead of the fixed list PROJECTS below.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(".")
LIB = ROOT / "library"
OUT = ROOT / "docs" / "PAINTINGS.md"
TODAY = "2026-11-19"
MIN_WORDS = 1500
GROVIER = "grovier_nws"
GROVIER_NOT_USABLE = {54}                      # review.json: work 54 is not usable, the other 56 are "restored"

# projects that exist on the server on 2026-11-19 (artwork key -> text)
PROJECTS = {
    "eyck-the-arnolfini-portrait": "arnolfini-opus (being made), arnolfini-live (rendered, old pipeline)",
    "munch-the-scream": "scream (pictures approved, draft not started)",
}

INDEX_MODE = False                              # set by `main` when an index.json was given: PROJECTS then comes from it


def projects_from_index(doc: dict) -> dict[str, tuple[str, str]]:
    """{artwork key: (status, text)} from `output/index.json`: `done` when the folder holds the finished video, else `in-progress`."""
    out: dict[str, tuple[str, str]] = {}
    for r in (doc.get("folders") or []) if isinstance(doc, dict) else []:
        if not isinstance(r, dict) or not r.get("key"):
            continue
        done = r.get("status") == "done"
        bits = [str(r.get("project") or "")]
        if done:
            sec = r.get("length_seconds")
            bits.append("video %d:%02d" % (int(sec) // 60, int(sec) % 60) if isinstance(sec, (int, float)) else "video")
        else:
            bits.append("at step: %s" % (r.get("step") or "not started"))
        if r.get("out_of_date"):
            bits.append("out of date: " + ", ".join(r["out_of_date"]))
        if r.get("last_run"):
            bits.append(str(r["last_run"])[:10])
        out[r["key"]] = ("done" if done else "in-progress", "%s (%s)" % (bits[0], ", ".join(b for b in bits[1:] if b)))
    return out


# status, youtube, reproduction, note; matched by (title words, artist word). First match wins.
# status: recommended-N | runner-up | considered | covered | covered-assumed | not-flat
R = "recommended"
# the same painting under two keys (one per book): merge them in the library before a project is made (POST /api/library/artworks/merge)
SAME = [["goes-the-portinari-altar", "goes-portinari-altarpiece"], ["veronese-the-marriage-at-cana", "veronese-the-wedding-at-cana"], ["greco-the-burial-of-count-orgaz", "greco-the-burial-of-the-count"], ["courbet-the-studio", "courbet-the-artist-s-studio"], ["repin-zaporogian-cossacks-composing-a-letter", "repin-reply-of-the-zaporozhian-cossacks"]]
NOTES: list[tuple[str, str, dict]] = [
    ("arnolfini", "eyck", dict(status="in-progress", yt="heavy: Great Art Explained 780k", repro="3840x5253 as saved by the app (Commons original 4386x6000)", note="")),
    ("scream", "munch", dict(status="in-progress", yt="heavy: Great Art Explained 1.03 million", repro="not checked", note="")),
    ("fortune teller", "tour", dict(status=R + "-1", yt="small: top 3,893 views, no large channel", repro="3806x3148 (Commons, Google Art Project)",
        note="Smuggled out of France in 1960; a scholar called it a forgery and found the word MERDE woven into a scarf (removed in 1982). The forgery claim is a minority view.")),
    ("battle of issus", "altdorfer", dict(status=R + "-2", yt="small: Smarthistory 4:44 with 29k, the rest under 5k", repro="4592x6000 (Commons, Google Art Project)",
        note="Troop numbers on the banners (300,000 against 32,000), a map of the Mediterranean behind the battle, hung in Napoleon's bathroom. Best fit for the map and number components.")),
    ("body of st mark", "tintoretto", dict(status=R + "-3", yt="none found for this painting; clips up to 7k", repro="7720x9600 (Commons)",
        note="Venice had its saint stolen from Egypt, hidden under pork; the doctor who paid is painted beside the saint; trimmed in 1807, a pyre overpainted until 1949.")),
    ("leopold wilhelm", "teniers", dict(status=R + "-4", yt="none found beyond a one-hour lecture with 2.8k", repro="6558x4885 (Commons, Google Art Project)",
        note="A painting of exactly 50 paintings and their road from Venice through Charles I to Vienna. Which version (Vienna, Prado, others) must be confirmed; our text names only about eight of the 50.")),
    ("garden of paradise", "", dict(status=R + "-5", yt="small: 6.3k (German), nothing in English", repro="4752x3643 (Commons); deepest zoom of all, 115 px per cm",
        note="Postcard-sized panel hiding a small devil, a dead dragon and ten nameable birds. Less story, few components.")),
    ("venus", "velazquez", dict(status="runner-up", yt="medium: a 43-minute documentary with 34k, a clip with 15k", repro="6162x4226 (Commons)",
        note="Slashed with a knife in 1914; the blurred face in the mirror; the Inquisition's fine for such pictures.")),
    ("cana", "veronese", dict(status="runner-up", yt="small: about eight videos, 13k to 33k", repro="10068x6742 (Commons), but the canvas is 9.9 m wide: shallow zoom",
        note="Two books. The three great painters as the musicians; the 1573 trial; taken by Napoleon.")),
    ("magi", "gozzoli", dict(status="runner-up", yt="small: travel clips up to 14k", repro="no complete flat image; part photographs about 5000 px",
        note="Two books. The Medici as the Magi; the painter's own portrait signed on his cap. A fresco on three walls.")),
    ("morozova", "surikov", dict(status="runner-up", yt="small in English (1k to 3k), Russian up to 35k", repro="4696x2446 (Commons), canvas 5.9 m wide: shallow zoom",
        note="A noblewoman dragged to prison in 1672 raising two fingers.")),
    ("relic", "carpaccio", dict(status="runner-up", yt="almost none: clips under 1.7k", repro="4326x4068 (Commons)",
        note="Venice in 1494 as a snapshot: the wooden Rialto bridge, the chimneys, the crowd. Lower drama.")),
    ("steel mill", "menzel", dict(status="considered", yt="small: best English video 6.3k", repro="6016x4000 (Commons)", note="Fewer hidden details.")),
    ("belshazzar", "rembrandt", dict(status="considered", yt="small: National Gallery 15.6k", repro="not checked", note="The Hebrew writing on the wall; an X-ray shows overpainting.")),
    ("eligius", "christus", dict(status="considered", yt="small: 15k to 16k", repro="not checked", note="")),
    ("procris", "piero", dict(status="considered", yt="small: National Gallery film 36k", repro="not checked", note="")),
    ("portinari", "goes", dict(status="considered", yt="small: Smarthistory 48.6k", repro="not checked", note="Two books.")),
    ("sardanapal", "delacroix", dict(status="considered", yt="small: all under 15k", repro="not checked", note="Read only by its headings.")),
    ("sunday afternoon", "rivera", dict(status="considered", yt="medium: Spanish up to 68k, Sotheby's 42k", repro="not checked", note="A hotel hid it for seven years.")),
    ("john the baptist", "manuel", dict(status="considered", yt="not checked", repro="1256x1641 (Commons): too small for close-ups", note="Signed with a dagger.")),
    ("draught of fishes", "witz", dict(status="considered", yt="not checked", repro="2920x2568 (Commons): small", note="")),
    ("qingming", "zhang", dict(status="covered", yt="heavy: Chinese explainers 0.3 to 1.7 million, English animation 182k", repro="Commons' large file is the Qing court copy, not the Song original", note="")),
    ("cossacks", "repin", dict(status="covered", yt="heavy: 803k, 375k, 315k", repro="not checked", note="")),
    ("mona lisa", "vinci", dict(status="covered", yt="heavy: Great Art Explained 2.4 million", repro="not checked", note="")),
    ("birth of venus", "botticelli", dict(status="covered", yt="heavy: Great Art Explained 1.25 million", repro="not checked", note="")),
    ("earthly delights", "bosch", dict(status="covered", yt="heavy: 3.87 million", repro="not checked", note="")),
    ("wave", "hokusai", dict(status="covered", yt="heavy: Great Art Explained 4.52 million", repro="not checked", note="")),
    ("nighthawks", "hopper", dict(status="covered", yt="heavy: 3.68 million", repro="not checked", note="")),
    ("water lil", "monet", dict(status="covered", yt="heavy: 2.04 million", repro="not checked", note="")),
    ("kiss", "klimt", dict(status="covered", yt="heavy: 1.87 million", repro="not checked", note="")),
    ("guernica", "picasso", dict(status="covered", yt="heavy: 1.52 million", repro="not checked", note="")),
    ("persistence", "dali", dict(status="covered", yt="heavy: Great Art Explained on Dali 2.06 million", repro="not checked", note="")),
    ("meninas", "velazquez", dict(status="covered", yt="heavy: 521k", repro="not checked", note="")),
    ("medusa", "gericault", dict(status="covered", yt="heavy: 557k", repro="not checked", note="")),
    ("ambassadors", "holbein", dict(status="covered", yt="heavy: 193k", repro="not checked", note="")),
    ("study after", "bacon", dict(status="covered", yt="heavy: Great Art Explained 156k", repro="not checked", note="")),
    ("saturn", "goya", dict(status="covered", yt="heavy: 1.0 million", repro="not checked", note="")),
    ("black paintings", "goya", dict(status="covered", yt="heavy: 435k", repro="not checked", note="")),
    ("third of may", "goya", dict(status="covered", yt="heavy: Smarthistory 601k", repro="not checked", note="")),
    ("school of athens", "raphael", dict(status="covered", yt="heavy: 660k", repro="not checked", note="")),
    ("gonzaga", "mantegna", dict(status="covered", yt="heavy: 100k and 72k", repro="not checked", note="")),
    ("emmaus", "caravaggio", dict(status="covered", yt="heavy: Smarthistory 85k, a National Gallery film 2.6 million", repro="not checked", note="")),
    ("conjur", "bosch", dict(status="covered-assumed", yt="probably heavy (107k and 152k seen, not verified)", repro="not checked", note="")),
    ("starry night", "gogh", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("pearl earring", "vermeer", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("thorn", "kahlo", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("rain", "turner", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("nightmare", "fuseli", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("demoiselles", "picasso", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("marat", "david", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("coronation", "david", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("venus of urbino", "titian", dict(status="covered-assumed", yt="assumed heavy, not measured", repro="not checked", note="")),
    ("bayeux", "", dict(status="not-flat", yt="not checked", repro="not checked", note="Embroidery, 70 m long.")),
    ("ecstasy", "bernini", dict(status="not-flat", yt="not checked", repro="not checked", note="Sculpture.")),
    ("kiss", "rodin", dict(status="not-flat", yt="not checked", repro="not checked", note="Sculpture.")),
    ("piet", "michelangelo", dict(status="not-flat", yt="not checked", repro="not checked", note="Sculpture.")),
    ("sistine", "michelangelo", dict(status="not-flat", yt="not checked", repro="not checked", note="Ceiling fresco.")),
    ("maman", "bourgeois", dict(status="not-flat", yt="not checked", repro="not checked", note="Sculpture.")),
    ("", "anatsui", dict(status="not-flat", yt="not checked", repro="not checked", note="Hanging sculpture.")),
    ("", "julien", dict(status="not-flat", yt="not checked", repro="not checked", note="Film installation.")),
    ("", "houghton", dict(status="not-flat", yt="not checked", repro="not checked", note="Not a flat painting.")),
    # dedicated videos of Great Art Explained already downloaded (research_media/great-art-explained, views when downloaded)
    ("hunters in the snow", "bruegel", dict(status="covered", yt="heavy: Great Art Explained 177k", repro="not checked", note="")),
    ("last supper", "vinci", dict(status="covered", yt="heavy: Great Art Explained 1.08 million", repro="not checked", note="")),
    ("wanderer", "friedrich", dict(status="covered", yt="heavy: Great Art Explained 319k", repro="not checked", note="")),
    ("ivan the terrible", "repin", dict(status="covered", yt="heavy: Great Art Explained 192k", repro="not checked", note="")),
    ("crossing the alps", "david", dict(status="covered", yt="heavy: Great Art Explained 165k", repro="not checked", note="")),
    ("milkmaid", "vermeer", dict(status="covered", yt="heavy: Great Art Explained 1.42 million", repro="not checked", note="")),
    ("taking of christ", "caravaggio", dict(status="covered", yt="heavy: Great Art Explained 826k", repro="not checked", note="")),
    ("two fridas", "kahlo", dict(status="covered", yt="heavy: Great Art Explained 1.86 million", repro="not checked", note="")),
    ("madame x", "sargent", dict(status="covered", yt="heavy: Great Art Explained 1.08 million", repro="not checked", note="")),
    ("potato eaters", "gogh", dict(status="covered", yt="heavy: Great Art Explained 187k", repro="not checked", note="")),
    ("ancient of days", "blake", dict(status="covered", yt="heavy: Great Art Explained 240k", repro="not checked", note="")),
    ("red studio", "matisse", dict(status="covered", yt="heavy: Great Art Explained 223k", repro="not checked", note="")),
    ("seagram", "rothko", dict(status="covered", yt="heavy: Great Art Explained 1.62 million", repro="not checked", note="")),
    ("marilyn", "warhol", dict(status="covered", yt="heavy: Great Art Explained 712k", repro="not checked", note="")),
    ("", "seurat", dict(status="covered", yt="heavy: Great Art Explained on Seurat 527k", repro="not checked", note="")),
    ("folly", "bronzino", dict(status="covered", yt="a Great Art Explained video exists (16k when downloaded)", repro="not checked", note="")),
    ("dawn horse", "carrington", dict(status="covered", yt="Great Art Explained 97k", repro="not checked", note="")),
    ("bugatti", "lempicka", dict(status="covered", yt="heavy: Great Art Explained 142k", repro="not checked", note="")),
    ("wheatfield", "gogh", dict(status="covered", yt="heavy: Great Art Explained on Van Gogh's last painting 498k", repro="not checked", note="")),
    ("apollo and daphne", "bernini", dict(status="not-flat", yt="heavy: Great Art Explained 600k", repro="not checked", note="Sculpture.")),
    ("thinker", "rodin", dict(status="not-flat", yt="heavy: Great Art Explained 725k", repro="not checked", note="Sculpture.")),
    ("david", "michelangelo", dict(status="not-flat", yt="heavy: Great Art Explained 4.9 million", repro="not checked", note="Sculpture.")),
    ("spiral jetty", "", dict(status="not-flat", yt="heavy: Great Art Explained 324k", repro="not checked", note="Earthwork.")),
]


def plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def load() -> list[dict]:
    arts = json.loads((LIB / "artworks.json").read_text(encoding="utf-8"))
    rows = []
    for key, a in arts.items():
        f = LIB / "dossiers" / key / "dossier.json"
        d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        words = {"normal": 0, "restored": 0, "low": 0}
        books = []
        for s in d.get("sources") or []:
            trust = s.get("trust") or "normal"
            if s.get("book_id") == GROVIER:
                trust = "low" if int(s.get("n") or 0) in GROVIER_NOT_USABLE else "restored"
            words[trust if trust in words else "low"] += int(s.get("words") or 0)
            if s.get("book_id") not in books:
                books.append(s.get("book_id"))
        imgs = d.get("images") or []
        rows.append({
            "key": key, "title": a.get("title") or "", "artist": a.get("artist") or "", "year": str(a.get("year") or ""),
            "kind": d.get("kind") or "artwork", "books": books, "words": words, "total": sum(words.values()),
            "images": len(imgs), "rights": (d.get("rights") or {}).get("status") or "",
            "works": a.get("works") or [],
        })
    return rows


def annotate(rows: list[dict]) -> dict[int, list[str]]:
    used: dict[int, list[str]] = {}
    for r in rows:
        t, ar = plain(r["title"]), plain(r["artist"])
        r["note"] = None
        for i, (tw, aw, n) in enumerate(NOTES):
            if (not tw or plain(tw) in t) and (not aw or plain(aw) in ar) and (tw or aw):
                if r["kind"] != "artwork":
                    continue
                r["note"] = n
                used.setdefault(i, []).append(r["key"])
                break
    return used


def status_of(r: dict) -> str:
    if r["kind"] != "artwork":
        return "theme"
    if r["key"] in PROJECTS:
        return PROJECT_STATUS.get(r["key"], "in-progress")
    if r["note"] and not (INDEX_MODE and r["note"]["status"] == "in-progress"):     # with an index, only the index says what is in progress
        return r["note"]["status"]
    if r["total"] >= MIN_WORDS or len(r["books"]) >= 2:
        return "candidate"
    return "thin-text"


PROJECT_STATUS: dict[str, str] = {}              # artwork key -> `done` | `in-progress` (filled from an index.json)
ORDER = ["done", "in-progress", "recommended-1", "recommended-2", "recommended-3", "recommended-4", "recommended-5", "runner-up", "considered", "candidate",
         "covered", "covered-assumed", "not-flat", "thin-text", "theme"]


def cell(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).replace("|", "/").strip()


def main(argv: list[str] | None = None) -> int:
    global PROJECTS, INDEX_MODE
    argv = list(sys.argv[1:] if argv is None else argv)
    paths = [a for a in argv if not a.startswith("--")]
    if paths:
        doc = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        found = projects_from_index(doc)
        PROJECTS = {k: v[1] for k, v in found.items()}
        PROJECT_STATUS.update({k: v[0] for k, v in found.items()})
        INDEX_MODE = True
    rows = load()
    used = annotate(rows)
    if "--check" in argv:
        for i, (tw, aw, n) in enumerate(NOTES):
            print(("OK  " if len(used.get(i, [])) == 1 else "MANY" if i in used else "NONE"), "%-22s %-14s %-16s" % (tw, aw, n["status"]), used.get(i, []))
        return 0
    for r in rows:
        r["status"] = status_of(r)
    rows.sort(key=lambda r: (ORDER.index(r["status"]), -r["words"]["normal"], -r["total"], r["key"]))
    count = {}
    for r in rows:
        count[r["status"]] = count.get(r["status"], 0) + 1
    twin = {}
    for a, b in SAME:
        twin[a], twin[b] = b, a
    L = []
    L.append("# The paintings of the library, as a queue for the pipeline")
    L.append("")
    L.append(f"Generated on {TODAY} by `tools/paintings_table.py` from `library/artworks.json` and `library/dossiers/`{' and an `output/index.json`' if INDEX_MODE else ''} ({len(rows)} entries: "
             f"{sum(1 for r in rows if r['kind'] == 'artwork')} artworks and {sum(1 for r in rows if r['kind'] != 'artwork')} themed chapters). "
             "Do not edit the table by hand: change the script's notes and run it again.")
    L.append("")
    L.append("## How to read it")
    L.append("")
    L.append("- **key**: the artwork key of the library; a project is created from it (`POST /api/library/projects` with `artwork_key`).")
    L.append("- **status**: where the artwork stands as a subject for a video.")
    if INDEX_MODE:
        L.append("  - `done`: the output folder of the artwork holds the finished video (from the `output/index.json` this table was made with).")
        L.append("  - `in-progress`: a project exists and its output folder has no finished video yet (the project column says where it stands).")
    else:
        L.append("  - `in-progress`: a project exists.")
    L.append("  - `recommended-1` to `recommended-5`, `runner-up`: the ranking of the research of 2026-11-19 (interesting story, little coverage on YouTube, a large reproduction).")
    L.append("  - `considered`: looked at in that research, not shortlisted.")
    L.append(f"  - `candidate`: enough text for a twelve-minute script ({MIN_WORDS:,} words of source text or more, or two books or more); YouTube and the reproduction are not checked yet.")
    L.append("  - `covered`: a large dedicated video exists on YouTube (measured); `covered-assumed`: very famous, assumed covered, not measured.")
    L.append("  - `not-flat`: not a flat painting (sculpture, embroidery, ceiling, installation): the pipeline's camera moves do not fit.")
    L.append(f"  - `thin-text`: one book and under {MIN_WORDS:,} words: not enough for a long video.")
    L.append("  - `theme`: a themed chapter of a book, not one artwork.")
    L.append("- **words N / R / L**: words of source text by trust: normal / restored (the reviewed text of the machine-translated book, usable for ideas and readings, not for hard facts) / low (not used for facts).")
    L.append("- **img**: pictures of the artwork found in the books. **rights**: the library's own estimate (`pd_likely` public domain likely, and so on); copyright is not a blocker for the owner.")
    L.append("- **YouTube** and **reproduction**: from web searches and the Wikimedia Commons file data on 2026-11-19; `not checked` means nobody looked. Views are what the search pages showed that day.")
    L.append("- %d paintings are in the library under two keys, one per book (the note says which): merge the pair in the library (`POST /api/library/artworks/merge`) before a project is made, so that both books feed it." % len(SAME))
    L.append("- The app saves a Wikimedia image at most 3,840 pixels wide, so a very large canvas zooms less deep than a small panel with the same file size.")
    L.append("")
    L.append("## Counts")
    L.append("")
    L.append("| status | artworks |")
    L.append("|---|---|")
    for s in ORDER:
        if s in count:
            L.append(f"| `{s}` | {count[s]} |")
    L.append("")
    L.append("## The table")
    L.append("")
    L.append("| # | status | key | title | artist | year | books | words N / R / L | img | rights | project | YouTube | reproduction | note |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        n = r["note"] or {}
        w = r["words"]
        L.append("| " + " | ".join(cell(x) for x in [
            i, "`%s`" % r["status"], "`%s`" % r["key"], r["title"], r["artist"], r["year"], ", ".join(b for b in r["books"] if b),
            "%d / %d / %d" % (w["normal"], w["restored"], w["low"]), r["images"], r["rights"], PROJECTS.get(r["key"], ""),
            n.get("yt", "not checked") if r["kind"] == "artwork" else "", n.get("repro", "not checked") if r["kind"] == "artwork" else "",
            " ".join(x for x in [n.get("note", ""), ("Same painting as `%s`: merge the two first." % twin[r["key"]]) if r["key"] in twin else ""] if x),
        ]) + " |")
    L.append("")
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("wrote", OUT, "rows", len(rows), "counts", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
