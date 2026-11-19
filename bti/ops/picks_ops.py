"""The operations of the picks document (`projects/<pid>/picks.json`, schema `bti.picks/1`, step 4).

The field names are the ones the document uses: `beat` (a narration line, `b0003`), `asset` (a key of `assets`), `region`,
`role`, `note`, `status`. A line shows its pictures in order; a line with none shows the main picture again (status `skip`).
Every operation checks its own fields against the document as the earlier operations of the batch left it.
"""
from __future__ import annotations

from bti.picks import doc as pdoc
from bti.picks import service as psvc

from . import schemacheck as S
from .registry import op

ROLES = list(pdoc.ROLES)
SOURCES = list(psvc.SOURCES) + ["book"]
SOURCE_VI = {"commons": "Wikimedia Commons", "met": "Bảo tàng Metropolitan", "pexels": "Pexels", "pixabay": "Pixabay",
             "osm": "OpenStreetMap", "book": "sách của dự án"}

_REF_PATTERN = r"^\$[A-Za-z][A-Za-z0-9_]{0,31}$"
BEAT = S.string("A narration line (beat) id, such as b0003.", pattern=r"^b\d{1,8}$", hint="the letter b followed by digits, like b0003")
ASSET = S.string("An asset key of the picks document (such as A12), or a $ref made by an import earlier in the batch.",
                 pattern=r"^(\$[A-Za-z][A-Za-z0-9_]{0,31}|[A-Za-z0-9][A-Za-z0-9_.-]{0,39})$",
                 hint="an asset key like A12, or a $name made by an earlier import")
REGION = S.string("A region name of the asset (letters, digits, spaces, _ . -).", pattern=r"^[A-Za-z0-9_][A-Za-z0-9_ .-]{0,39}$",
                  hint="up to 40 letters, digits, spaces, _ . -")
NOTE = S.string("A short note (up to 400 characters).", max_length=400)
REF = S.string("A name for the asset this operation brings in; later operations of the batch write it as $name.",
               pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$", hint="a name of letters, digits and _, starting with a letter")
ITEM = S.plain_object({
    "asset": ASSET,
    "region": S.string("A region of that asset to show, or null for the whole picture.", pattern=REGION["pattern"], nullable=True,
                       hint=REGION["x-hint"]),
    "role": S.string("What the picture is for.", enum=ROLES),
    "note": NOTE}, required=["asset"], title="a picture item {asset, region?, role?, note?}")


# ---------------------------------------------------------------- helpers
def _pic(ctx, key: str) -> str:
    return ctx.pic(key)


def _asset(ctx, value, field: str) -> str:
    key = ctx.resolve(value, "asset", field)
    if key not in ctx.doc["assets"]:
        ctx.bad(field, "no asset %r in the picks" % str(key)[:40], allowed=sorted(ctx.doc["assets"]), code="unknown_asset")
    return key


def _beat(ctx, value, field: str = "beat") -> str:
    f = ctx.facts
    if f.present and value not in f.beat_set:
        ctx.bad(field, "no beat %r in the narration" % str(value)[:20], allowed=f.beat_ids, code="unknown_beat")
    ctx.in_scope(value, field, "beat")
    return value


def _entry(ctx, bid: str) -> dict:
    return ctx.doc["beats"].setdefault(bid, {"items": [], "status": "todo", "note": ""})


def _item(ctx, it: dict, base: str) -> dict:
    key = _asset(ctx, it["asset"], base + "asset")
    a = ctx.doc["assets"][key]
    region = it.get("region") or None
    if region is not None:
        regs = a.get("regions") or {}
        if region not in regs:
            ctx.bad(base + "region", "no region %r on asset %r" % (region, key), allowed=sorted(regs), code="unknown_region")
    role = it.get("role") or ("video" if a.get("kind") == "video" else "detail")
    return {"asset": key, "region": region, "role": role, "note": it.get("note") or ""}


def _say_beat(ctx, bid: str, variant: str = "default", **vars) -> None:
    ctx.say({"beat": bid}, ctx.facts.beat_time(bid), variant, n=ctx.facts.beat_no(bid), **vars)


# ---------------------------------------------------------------- operations
@op("picks", "set_main",
    summary="Choose the main picture (the whole painting) of the video.",
    schema=S.obj("set_main", ["asset"], {"asset": ASSET}),
    example={"op": "set_main", "asset": "B"},
    sentences="Tranh chính: đổi sang {pic}")
def set_main(ctx, o):
    ctx.whole_document("set_main")
    key = _asset(ctx, o["asset"], "asset")
    if ctx.doc["assets"][key].get("kind") == "video":
        ctx.bad("asset", "a video cannot be the main picture", code="video_not_main")
    ctx.touch("main")
    ctx.doc["main_asset"] = key
    ctx.say({"asset": key}, pic=_pic(ctx, key))


@op("picks", "set_region",
    summary="Set (add or replace) a named region of an asset: a point, with an optional radius, in pixels of the stored picture.",
    schema=S.obj("set_region", ["asset", "region", "x", "y"], {
        "asset": ASSET, "region": REGION,
        "x": S.number("Centre, pixels from the left edge of the picture."),
        "y": S.number("Centre, pixels from the top edge of the picture."),
        "rx": S.number("Horizontal radius in pixels; leave out for a point.", exclusive_minimum=0),
        "ry": S.number("Vertical radius in pixels; leave out for a point.", exclusive_minimum=0),
        "label": S.string("What the region shows, up to 80 characters.", max_length=80)}),
    example={"op": "set_region", "asset": "A", "region": "MIRROR", "x": 700, "y": 420, "rx": 120, "ry": 120, "label": "The mirror"},
    sentences="Vùng {region} của {pic}: đã đặt")
def set_region(ctx, o):
    ctx.whole_document("set_region")
    key = _asset(ctx, o["asset"], "asset")
    a = ctx.doc["assets"][key]
    w, h = int(a.get("width") or 0), int(a.get("height") or 0)
    if w and not 0 <= o["x"] <= w:
        ctx.bad("x", "must be between 0 and %d (the width of the stored picture)" % w)
    if h and not 0 <= o["y"] <= h:
        ctx.bad("y", "must be between 0 and %d (the height of the stored picture)" % h)
    regions = a.get("regions") or {}
    if o["region"] not in regions and len(regions) >= 60:
        ctx.bad("region", "an asset has at most 60 regions")
    rr = pdoc._region({k: o[k] for k in ("x", "y", "rx", "ry", "label") if k in o})
    ctx.touch("regions:" + key)
    a.setdefault("regions", {})[o["region"]] = rr
    ctx.say({"asset": key}, region=o["region"], pic=_pic(ctx, key))


@op("picks", "remove_region",
    summary="Remove a named region of an asset (the pictures of a line that use it must be changed in the same batch, before this operation).",
    schema=S.obj("remove_region", ["asset", "region"], {"asset": ASSET, "region": REGION}),
    example={"op": "remove_region", "asset": "A", "region": "HANDS"},
    sentences="Vùng {region} của {pic}: đã bỏ")
def remove_region(ctx, o):
    ctx.whole_document("remove_region")
    key = _asset(ctx, o["asset"], "asset")
    regions = ctx.doc["assets"][key].get("regions") or {}
    if o["region"] not in regions:
        ctx.bad("region", "no region %r on asset %r" % (o["region"], key), allowed=sorted(regions), code="unknown_region")
    ctx.touch("regions:" + key)
    del ctx.doc["assets"][key]["regions"][o["region"]]
    ctx.say({"asset": key}, region=o["region"], pic=_pic(ctx, key))


@op("picks", "set_picks",
    summary="Replace all the pictures of one narration line (use skip_beat to show the main picture instead).",
    schema=S.obj("set_picks", ["beat", "items"], {
        "beat": BEAT,
        "items": S.array(ITEM, "The pictures of the line, in the order they are shown (1 to %d)." % pdoc.MAX_ITEMS, min_items=1,
                         max_items=pdoc.MAX_ITEMS),
        "reason": S.string("Why these pictures; kept as the note of the line (up to 400 characters).", max_length=400)}),
    example={"op": "set_picks", "beat": "b0003", "items": [{"asset": "B"}, {"asset": "A", "region": "HEAD", "role": "detail"}],
             "reason": "Both pictures show the room."},
    sentences="Đoạn {n}: thay {k} hình")
def set_picks(ctx, o):
    bid = _beat(ctx, o["beat"])
    items = [_item(ctx, it, "items[%d]." % n) for n, it in enumerate(o["items"])]
    ctx.touch("beat:" + bid)
    b = _entry(ctx, bid)
    b["items"], b["status"] = items, "picked"
    if "reason" in o:
        b["note"] = o["reason"]
    _say_beat(ctx, bid, k=len(items))


@op("picks", "add_pick",
    summary="Add one picture to a narration line, at the end or at a position.",
    schema=S.obj("add_pick", ["beat", "asset"], {
        "beat": BEAT, "asset": ASSET,
        "region": ITEM["properties"]["region"], "role": ITEM["properties"]["role"], "note": NOTE,
        "position": S.integer("Where to put it among the pictures of the line, counting from 0; leave out to add it last.", minimum=0)}),
    example={"op": "add_pick", "beat": "b0004", "asset": "B", "role": "context"},
    sentences="Đoạn {n}: thêm {pic}")
def add_pick(ctx, o):
    bid = _beat(ctx, o["beat"])
    item = _item(ctx, o, "")
    ctx.touch("beat:" + bid)
    b = _entry(ctx, bid)
    if len(b["items"]) >= pdoc.MAX_ITEMS:
        ctx.bad("beat", "a line shows at most %d pictures" % pdoc.MAX_ITEMS)
    pos = o.get("position")
    if pos is not None and pos > len(b["items"]):
        ctx.bad("position", "must be between 0 and %d (the line has %d picture%s)" % (len(b["items"]), len(b["items"]),
                                                                                       "" if len(b["items"]) == 1 else "s"))
    b["items"].insert(len(b["items"]) if pos is None else int(pos), item)
    b["status"] = "picked"
    _say_beat(ctx, bid, pic=_pic(ctx, item["asset"]))


@op("picks", "remove_pick",
    summary="Remove one picture of a narration line, by its position among the pictures of the line (counting from 0, as the earlier operations of the batch left them).",
    schema=S.obj("remove_pick", ["beat", "index"], {
        "beat": BEAT, "index": S.integer("Position of the picture in the line, counting from 0.", minimum=0)}),
    example={"op": "remove_pick", "beat": "b0001", "index": 0},
    sentences="Đoạn {n}: bỏ {pic}")
def remove_pick(ctx, o):
    bid = _beat(ctx, o["beat"])
    items = (ctx.doc["beats"].get(bid) or {}).get("items") or []
    idx = int(o["index"])
    if idx >= len(items):
        ctx.bad("index", "the line has %d picture%s: the index must be between 0 and %d" % (len(items), "" if len(items) == 1 else "s", len(items) - 1)
                if items else "the line has no picture to remove")
    ctx.touch("beat:" + bid)
    b = _entry(ctx, bid)
    gone = b["items"].pop(idx)
    if not b["items"] and b.get("status") == "picked":
        b["status"] = "todo"
    _say_beat(ctx, bid, pic=_pic(ctx, gone["asset"]))


@op("picks", "skip_beat",
    summary="Make a narration line show the main picture again (it keeps no pictures of its own).",
    schema=S.obj("skip_beat", ["beat"], {
        "beat": BEAT, "reason": S.string("Why; kept as the note of the line (up to 400 characters).", max_length=400)}),
    example={"op": "skip_beat", "beat": "b0003", "reason": "The main picture says it all."},
    sentences="Đoạn {n}: dùng lại tranh chính")
def skip_beat(ctx, o):
    bid = _beat(ctx, o["beat"])
    ctx.touch("beat:" + bid)
    b = _entry(ctx, bid)
    b["items"], b["status"] = [], "skip"
    if "reason" in o:
        b["note"] = o["reason"]
    _say_beat(ctx, bid)


@op("picks", "import",
    summary="Bring one found picture into the project (the same sources and code path as POST .../picks/import and .../picks/import-book-image). "
            "Imports run first, before anything is written; a dry run only checks the shape. Videos are cut by the long job, not here.",
    schema=S.obj("import", ["source", "source_id"], {
        "source": S.string("Where the picture is found: a picture source, or `book` for a picture of the project's books.", enum=SOURCES),
        "source_id": S.string("The id the search gave (or, for `book`, the source_id of GET .../picks/book-images).", min_length=1,
                              max_length=300),
        "as_main": S.boolean("Also make it the main picture."),
        "ref": REF}),
    example={"op": "import", "source": "commons", "source_id": "File:Jan van Eyck - The Arnolfini Portrait - Google Art Project.jpg",
             "ref": "found"},
    sentences={"default": "Nhập hình từ {source}", "main": "Nhập hình từ {source} và đặt làm tranh chính"})
def import_(ctx, o):
    as_main = bool(o.get("as_main"))
    if as_main:
        ctx.whole_document("import with as_main")
    if ctx.dry_run:
        key = "dry_%d" % ctx.index
        while key in ctx.doc["assets"]:
            key += "_"
        asset = {"file": "media/dry_run_%d" % ctx.index, "kind": "image", "title": "", "artist": "", "year": "", "width": 0, "height": 0,
                 "credit": {"flag": None}, "regions": {}}
        ctx.placeholders.add(key)
    else:
        got = ctx.fetched.get(ctx.index)
        if got is None:
            ctx.fail("import_failed", "ops[%d]: the picture was not fetched before the batch was applied" % ctx.index)
        key, asset = got["asset_key"], got["asset"]
        if as_main and asset.get("kind") == "video":
            ctx.bad("as_main", "a video cannot be the main picture", code="video_not_main")
    existed = key in ctx.doc["assets"]
    ctx.touch("asset:" + key)
    ctx.touch("regions:" + key)
    if as_main:
        ctx.touch("main")
    psvc.register_into(ctx.doc, key, asset, as_main)
    ctx.imported.add(key)
    if not existed:
        ctx.created["assets"].append(key)
    ctx.define_ref(o.get("ref"), "asset", key)
    ctx.say({"asset": None if ctx.dry_run else key}, variant="main" if as_main else "default", source=SOURCE_VI[o["source"]])
