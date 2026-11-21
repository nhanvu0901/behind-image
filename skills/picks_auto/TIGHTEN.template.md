# Task: tighten existing detail boxes of the main painting (second look)

You are working on **{{TITLE}}** by {{ARTIST}}, {{YEAR}} (`images/main.jpg`).
This project already has **{{N_REGIONS}} non-tight regions** on the main painting ({{REGION_LIST}}). Your job is the **second look**: inspect each region's full-resolution gridded cut-out and give a tight pixel box around the ONE thing it represents, or mark `drop` if the thing is not there, then verify your tight boxes on the check sheets.

- You have at most **{{MAX_STEPS}} steps** and **{{MAX_MINUTES}} minutes**. Plan your steps: read `inputs/regions.json` (1), open each cut-out `images/d_<NAME>.jpg` (1 each), write `out/tighten.json` (1), run `{{CHECK_CMD}}` to create `look/check_*.jpg` (or any `wider` cut-outs), open every `look/check_*.jpg` sheet, confirm or adjust once in `out/tighten.json`, and run `{{CHECK_CMD}}` until `0 error(s)`.

## 1. Rules

1. **Work only inside this folder.** Only `out/tighten.json` is read back.
2. **Do not convert cut-out coordinates to full-painting coordinates.** Write coordinates in each cut-out's **own pixels** using its 100-px yellow grid along the top and left edges; the program converts them.
3. **Edges touch the thing itself — NO air.** Do not include surrounding objects just because the old box was wide.
4. **Add `thing` (2 to 8 English words)** when a region's `thing` is empty or unclear, naming the ONE object using words from the lines in `inputs/regions.json`. Keep Vietnamese only in `reason`.
5. **Never confirm a box you have not checked on `look/check_*.jpg`.**

## 2. Files

| File | What it is |
|---|---|
| `inputs/regions.json` | Each non-tight region: `name`, existing `label`, existing `thing` (if any), `lines` and `line_texts` (the narration lines using it), `cutout` (`images/d_<NAME>.jpg`), `cutout_size` `[w, h]`. |
| `images/d_<NAME>.jpg` | Cut from the **full-resolution stored painting** (+15% margin, inside the painted surface), scaled so long side is 1,024 px, with a 100-px grid in cut-out pixels. |
| `images/main.jpg` | Scaled overview of the whole painting for context. |
| `out/tighten.json` | Your output file (`schema`: `bti.picks.tighten/1`). |

## 3. Format (`bti.picks.tighten/1`) and workflow

```json
{"schema": "bti.picks.tighten/1",
 "regions": [
   {"name": "CHAIR_SAINT", "action": "tight", "box": [298, 162, 398, 392],
    "thing": "carved woman standing on a dragon", "confirmed": true,
    "reason": "Khung ôm sát tượng nhỏ khắc trên thành ghế."},
   {"name": "GHOST", "action": "drop",
    "reason": "Không tìm thấy chi tiết này trong vùng tranh cũ."}]}
```

- First pass: set `action: "tight"` with `[x0, y0, x1, y1]` (cut-out pixels), `wider` (once, with Vietnamese `reason` if clipped at the cut-out edge -> look at `look/d_<NAME>_wider.jpg`), or `drop` (with Vietnamese `reason`). Do NOT set `confirmed: true` yet.
- Run `{{CHECK_CMD}}`. It writes clean (no-grid) green-box check sheets to `look/check_1.jpg`, ... (6 regions per sheet).
- Open every `look/check_*.jpg`, inspect each green rectangle, set `"confirmed": true` (or give a corrected `box` **once** with `"confirmed": true`, or `drop`), and run `{{CHECK_CMD}}` until `0 error(s)`.
