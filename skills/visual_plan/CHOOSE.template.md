# Choose pictures

Read `inputs/wants.json` and look at each candidate sheet. For each wanted subject choose the candidate that actually shows it, preferring a picture from the period; reject pictures that only resemble it. Return `out/choice.json` as an object keyed by wanted id: `{"w1":{"pick":1,"caption":"A concise English description","shows":["cast-id"],"period":"then"}}`. Use the candidate number, or `null` if none is suitable. A caption is at most 60 characters, describes the picture, and is not a file or source name. `shows` names the cast subjects actually visible; `period` is then, later, today, or null. Do not invent identities or dates. When nothing is suitable, the plan's fallback will be used and the owner will see the search wordings tried.

Run {{CHECK_CMD}} and fix every ERROR. REPORT entries need your judgment.

If `tighten/inputs/regions.json` exists, inspect each enlarged region (its `cutout` path is relative to `tighten/`) and place a tight box around the one thing it shows. Write `out/tighten.json` as `{"schema":"bti.picks.tighten/1","regions":[{"name":"REGION","action":"tight","box":[x0,y0,x1,y1],"thing":"description of the thing","confirmed":false,"reason":"Lý do."}]}`. Use the coordinates of that region's enlarged image. Run the check to make the review sheets, inspect them under `tighten/look/`, set `confirmed` to true only when the box fits, and check again. If the object is absent, use `action: "drop"` and explain why.

Reuse the regions from the plan. New regions must be added during planning, and the check reports if the total would exceed 80.
