# Moving mock-ups: map looks and explanatory components (2026-11-18)

The page the owner saw and chose from (published copy: https://claude.ai/artifact/4wzXjkrX7UPkeftVaYSNJN).
`components.html` is a page fragment: to open it locally, serve this folder (`python3 -m http.server`) and wrap the file in a
plain HTML document, or read its script: every scene is one function whose `update(t)` holds the exact timings, sizes and
colours. Scenes: `plate` (map look A, chosen), `relief` and `paper` (looks B and C, not chosen), `labels`, `timeline`,
`number`, `tree`, `states`, `doclit`.

`geo.js`, `relief.jpg` and `landmask.png` were made by `prep_geo.py` from Natural Earth data (public domain):
land and countries at 1:50m through the `world-atlas` package, shaded relief `SR_LR` at 1:10m.
The painting is a reduced copy of the Arnolfini Portrait reproduction the sample project uses.
The build contract that follows from the owner's choice: `docs/design/2026-11-18-explainer-components.md`.
