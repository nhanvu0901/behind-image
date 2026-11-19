"""The output folder: one clean folder per painting, `output/<artwork key>/`, with the finished video at its root and everything worth keeping in a fixed place.

    output/
      INDEX.md, index.json            every folder below: painting, state, last run, length, path
      <artwork key>/                  (a project made without a library artwork: its project id)
        final.mp4                     the video (appears when the export is done)
        state.json                    machine-readable (schema `bti.output/1`)
        README.md                     one page a person reads
        1_sources/  2_script/  3_voice/  4_pictures/  5_storyboard/  6_export/  log/

The app fills it as a project moves through its steps (`publish.sync`, called by `hooks`); the working folder `projects/<id>/` stays what the app works in, and nothing in the app reads a
document back from here. Cleaning the working folder's caches after a successful export is `clean.py`. The words a person reads are Vietnamese (`words.py`).

    paths.py    where the folder is and what the parts are called       facts.py    what the project says about itself (read-only)
    parts.py    the writer of each part                                  render.py   the readable documents (Markdown)
    publish.py  `sync`, the one function that decides and writes         readme.py   README.md
    hooks.py    how the app calls it, with one line each                 index.py    INDEX.md and index.json
    clean.py    the cache paths and their removal                        sheets.py   the regions sheet and the contact sheets
    shotwords.py  the plain sentence of a shot (twin of shotsentence.js)   times.py    when each shot starts
"""
