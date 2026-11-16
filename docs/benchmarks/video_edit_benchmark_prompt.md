# Video-editing benchmark: Great Art Explained–style episode (The Arnolfini Portrait)

You are one of three AI agents (Claude Code, Codex, Antigravity) doing this same task independently. The results will be compared side by side.

> **Revision v2 (2026-11-14).** Two changes from v1:
> 1. The main video is now a **long-form episode of at least 10 minutes, with no upper limit.** The v1 limits of 60–90 s and 160–220 words are removed.
> 2. **Subtitles are no longer burned into the video.** Deliver `subtitles.srt` as a sidecar file.
>
> Sections 3, 4, 5, 6B, 6C, 7 and 8 are updated to match. A technique reel already delivered under v1 does not need to be re-rendered.

## 0. What this test is for

This is a research test of what YOU can do in video editing, not only a request for one video. The owner wants to find out which editing techniques, animations, transitions and effects you can build in code, how well you build them, and how long they take.

- **Match the reference.** Reproduce the editing of the YouTube channel Great Art Explained as closely as you can. The goal is that a viewer cannot tell your edit apart from the channel's own. That means the same kinds of camera moves at the same speeds, the same transitions, highlights, annotations and layouts, the same text placement, and the same cut rhythm.
- **Try everything.** Attempt as many of the channel's catalogued techniques as you can (section 6D), and report honestly which ones you could not do and why.
- **Internal only.** Nothing from this test will be uploaded.

## 1. Topic and source material

- **Artwork:** The Arnolfini Portrait (1434), Jan van Eyck.
- **Source book:** `/Users/nhanvu/Documents/code/behind-the-image/books/_OceanofPDF.com_Great_Art_Explained_-_James_Payne.pdf`, chapter 2 (pages 23–35).
- **Comparison work:** Virgin and Child with Canon van der Paele (1434), Jan van Eyck.

## 2. Reference data about the channel (already on disk; do not download anything)

Everything about the channel is already on disk. Do NOT download any video, audio, thumbnail or transcript from YouTube or anywhere else. Use only these files. Paths are relative to `/Users/nhanvu/Documents/code/behind-the-image/`.

| # | File | What it gives you |
|---|---|---|
| 1 | `docs/research/great-art-explained/NARRATION_ANALYSIS.md` | Narrative voice, wording, structure. Read first. |
| 2 | `docs/research/great-art-explained/SYNCHRONIZATION_ANALYSIS.md` | How visuals land on the spoken words. Read first. |
| 3 | `docs/research/great-art-explained/corpus/EFFECTS_CATALOG.md` | The inventory of the channel's visual techniques. Each has a record ID (CAM-01 … SHORT-05), a timestamped example and a link to a short local clip. **This is your checklist.** (Written in Vietnamese; the IDs, timestamps and links are what matter.) |
| 4 | `docs/research/great-art-explained/corpus/visual-b/T15Kv6dtYO0.md` | Analysis of the channel's own Arnolfini episode. |
| 5 | `research_media/great-art-explained/T15Kv6dtYO0.mp4` | **The channel's own Arnolfini episode** (local copy, about 15.7 min). Study it frame by frame with ffmpeg/ffprobe. Contact sheets are in `research_media/great-art-explained/analysis-b/T15Kv6dtYO0/`. |
| 6 | `research_media/great-art-explained/effect-excerpts/*.mp4` | About 10-second clips, each isolating one effect: push-in, pull-back, pan-up, zoom-and-shift, dissolve, slide-in/out, panel opening, spotlight, figure reveal, circle draw, projection rays, diagram light, scrolling text, layered relative motion, and more. |
| 7 | `docs/research/great-art-explained/video-study.md`, `scene-sync/*.md`, `narration/*.md` | Further studies of the channel's editing, sync and narration. |
| 8 | The other local MP4s in `research_media/great-art-explained/` | Their contact sheets are in `analysis-a/`, `analysis-b/` and `analysis-shorts/`. |

**Measure, don't guess.** For each technique you reproduce, write down the numbers you measured in the reference and the numbers you used. Example: "push-in from 100% to 118% over 6.2 s, ease-in-out; dissolve 0.8 s; spotlight dims the surround to about 35% brightness over 0.5 s". Things to measure in `T15Kv6dtYO0.mp4`:
- where the cuts fall
- how long holds last
- the speed and easing of camera moves
- how a vertical painting is framed in 16:9
- where text sits and how it appears
- how highlights fade in and out

## 3. Rules

### Isolation

- **Mac workspace:** `/Users/nhanvu/Documents/code/behind-the-image/demo_runs/<agent>/`, where `<agent>` is `claude_code`, `codex` or `antigravity`. Put all scripts, extracted assets, intermediate files and deliverables here.
- **Windows workspace:** `D:\bench\<agent>\` (section 4).
- **Nothing else:** do not modify any other file, any git repository, or anything outside these two folders.

### Copyright

- **Script.** Write it yourself. Do not use any sentence from the book, and never more than 5 consecutive words from it. Use the book only for its facts and its argument.
- **The channel's videos are reference only.** Your output must contain none of the channel's frames, audio, music, voice, on-screen text, logo or name. The title card shows the painting title, artist and year, not "Great Art Explained".
- **Images.** The paintings themselves are public domain.
  - Use the images you extract from the PDF.
  - If Wikimedia Commons has a higher-resolution public-domain image of the same painting, you may use it instead. Log its URL and licence in `timeline.json`. Downloading from Commons is allowed; downloading from YouTube is not.
  - A 10-minute episode needs context and comparison images, as the channel's own episode does. Examples: other works by Van Eyck, the later portrait of Giovanni Arnolfini, works the chapter names (the Ghent Altarpiece, Dürer's Self-Portrait of 1500, Las Meninas), tomb effigies with dogs, and views of Bruges. You may download these from Wikimedia Commons, with these licence rules:
    - Public domain and CC0 are preferred.
    - CC BY and CC BY-SA are allowed only with the author and licence logged.
    - Reject NC, ND, unknown or missing licences.
    - Log every image's URL, author and licence in `timeline.json`.
- **Background music** must be a royalty-free or CC0 file, or generated locally. Log its source.
  - The server has ACE-Step music environments (`.venv-acestep`, `.venv-acestep-directml`) inside the comic repo. Use them only if you can run them read-only, and treat that as a heavy job (section 4).

### Paid APIs

Do not call any paid API.

## 4. Where to run: the Windows server

Do ALL TTS and ALL video rendering on the Windows server. PDF extraction, planning and QA may run on the Mac.

> **The server is PRODUCTION for our comic channel.** Breaking it is the worst possible outcome of this test. When unsure, stop and ask the human.

### Connection

- **Host:** `ssh winbox-cmd` (Tailscale, preferred) or `ssh winbox-lan` (LAN). Key authentication is already set up. The machine runs Windows 11 with OpenSSH; the default shell is `cmd.exe`; the host name is DESKTOP-4V6D49N.
- **Retries:** port 22 times out now and then. Wrap every ssh and scp call in a retry loop of 3–5 tries with a growing wait.
- **File copies:** use scp, e.g. `scp -r ./assets winbox-cmd:D:/bench/<agent>/`, and copy results back the same way. If the `D:/...` form fails, try `/D:/...`.

### What you may touch

- **Read-only: `D:\code\comic-book-pipeline`** (the repo, `.venv`, `.venv-chatterbox`, `assets\voices`). You may run its Python interpreters and import its modules. You must NOT:
  - edit, create or delete anything in it
  - run git commands that change it (`pull`, `checkout`, `stash`, `reset`, etc.)
  - `pip install` into its venvs
  - open or print its `.env`
- **Write only in `D:\bench\<agent>\`.** Create it.
- **Other agents:** do not touch their folders.

### Tools on the server (checked 2026-11-14)

- **ffmpeg 8.1 full build** is on PATH and includes libass, so burning in subtitles works there. The Mac's ffmpeg lacks a filter, which is another reason to render on the server.
- **`D:\code\comic-book-pipeline\.venv\Scripts\python.exe`** has numpy, scipy, OpenCV (`cv2`) and Pillow.
- **Not installed:** moviepy, PyMuPDF, faster-whisper, whisper, pyloudnorm. To get them, create your own venv and pip install into it:
  ```
  D:\code\comic-book-pipeline\.venv\Scripts\python.exe -m venv D:\bench\<agent>\venv
  ```
  The server's DNS often drops lookups, so retry pip on network errors.
- **Hardware:** 16 CPU threads, about 30 GB RAM, **no NVIDIA GPU** (torch is CPU-only). Chatterbox and renders run on the CPU and are slow. Render a short low-resolution preview before the full render.

### Running long jobs (TTS, renders)

- **Launching.** A process started with `start /b` or PowerShell `Start-Process` is KILLED when the ssh session closes. What works:
  1. Put the job in a `.bat` that changes directory, sets environment variables, runs the command, sends stdout and stderr to a log file, and ends with `echo EXIT=%ERRORLEVEL%`.
  2. Launch it with a small `.ps1` that runs:
     ```powershell
     Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='cmd.exe /c D:\bench\<agent>\job.bat'; CurrentDirectory='D:\bench\<agent>'}
     ```
  3. Check the log with short ssh calls:
     ```
     powershell -NoProfile -Command "Get-Content D:\bench\<agent>\job.log -Tail 20"
     ```
- **Quoting.** Do not push complicated quoting through ssh. Copy a script file over with scp and run that.
- **Missing commands.** The server has no `wmic` and no `tail`. To list processes, use a `.ps1` with `Get-CimInstance Win32_Process`.
- **Running `.bat` files.** Never edit a `.bat` while it is running; cmd re-reads it by byte offset.
- **No desktop.** The ssh session has none (session 0), so do not open GUI apps or file viewers.

### One heavy job at a time

This applies across all three agents and production. Two heavy jobs at once exhaust the memory: Chatterbox has died with `The paging file is too small (os error 1455)` when another job overlapped it. A heavy job is Chatterbox TTS, any full render, or any model load.

1. **Take the lock.** Run `mkdir D:\bench\_heavy.lock`. This is atomic: it fails if the folder already exists. If it succeeds, write `owner.txt` inside it with your agent name and the start time.
2. **Wait if it's held.** If the lock already exists, wait and retry every 60 s. If it is older than 60 minutes, stop and tell the human. Never delete another agent's lock.
3. **Check production.** Before starting, make sure no production TTS or render job is running. That means no process whose command line contains `_chatterbox_worker`, `stages.stage_4` or `stages.stage_5`, and no `ffmpeg` running outside `D:\bench`. The production web UI on port 8550 runs all the time; that process itself is fine.
4. **Check memory.** Before loading Chatterbox, `(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory` should be above about 12,000,000 (the value is in KB).
5. **Release the lock.** Delete the lock folder as soon as your job ends, including when it fails.
6. **Keep each heavy job under about 30 minutes.** A 10-minute episode needs roughly 45–60 minutes of Chatterbox time and 20–30 minutes of rendering on this CPU.
   - Split long work into several jobs, for example one TTS job per chapter and one render job per chapter, followed by a concat.
   - Release the lock between jobs so production and the other agents get a turn.
   - Write the expected end time into `owner.txt`.

## 5. Voice: our comic channel's narrator

Use the same narrator voice as our comic pipeline. That voice is local Chatterbox cloning the reference file `D:\code\comic-book-pipeline\assets\voices\machiavelli_ref.wav`, which is the pipeline's default. Do not use any other TTS or voice.

### Settings

- **Chatterbox:** `exaggeration=0.35`, `cfg_weight=0.5`, `temperature 0.7`, `seed=42`. These are the pipeline's defaults.
- **Tempo:** the pipeline then speeds the voice up with ffmpeg `atempo` (1.10 for long-form). Tune `atempo` between 1.00 and 1.20 so the narration lands at 135–145 words per minute. Report the final value.

### How to call it

1. Read `D:\code\comic-book-pipeline\stages\stage_4\chatterbox_tts.py` first. The same file is on the Mac at `/Users/nhanvu/Documents/code/comic-book-pipeline/stages/stage_4/chatterbox_tts.py`. The server checkout is on `main` at `0283b5b`.
2. From a script in your bench folder, using `D:\code\comic-book-pipeline\.venv\Scripts\python.exe`:
   - put `D:\code\comic-book-pipeline` on `sys.path`
   - set `CHATTERBOX_VENV=D:\code\comic-book-pipeline\.venv-chatterbox`
   - call:
     ```python
     from stages.stage_4.chatterbox_tts import synthesize
     r = synthesize(text, voice_id=r"D:\code\comic-book-pipeline\assets\voices\machiavelli_ref.wav",
                    exaggeration=0.35, cfg_weight=0.5, seed=42)
     # r.wav_bytes, r.sample_rate, r.word_timestamps
     ```
   - write the WAV into your bench folder.
3. Importing the pipeline loads its `.env` into your process. That is fine, but never print environment variables.
4. Run `git -C D:\code\comic-book-pipeline status --short` before and after your TTS run, to prove you left nothing behind in the repo. This is a read-only command.
5. If Chatterbox fails twice, stop and report the error. Do not switch to another voice.

### Timing for sync

Chatterbox gives no real word timestamps; its word times are estimates.
- **Exact beat times:** `synthesize()` already makes one chunk per sentence, and each chunk's start in the joined WAV is exact. You can batch many beats into one call and recover the beat starts from the chunk boundaries; check that the chunking matches your beats. Alternatively, synthesize each beat as a separate call, but each call reloads the model.
- **Exact word times:** if you need when a particular word is spoken (for example the moment a spotlight appears), run forced alignment, such as faster-whisper with word timestamps installed in your own venv on CPU.
- Report which method you used.

## 6. Steps

### A. Extraction (Mac)

- Write a Python script using PyMuPDF that extracts:
  - the text of chapter 2 (pages 23–35)
  - all 8 embedded images at their original resolution, each linked to its caption, in a `manifest.json`
- The full painting (page 35) is vertical and the video is 16:9 (1920x1080). Check how the channel frames a vertical painting in 16:9 in `T15Kv6dtYO0.mp4` and do the same: a dark museum-gallery backdrop, a blurred ambient fill, or a moving pan/crop. No raw black bars, no stretching.

### B. Script

Write an original long-form voiceover script in the channel's style. Read `NARRATION_ANALYSIS.md`, `narration/language-style.md` and `narration/structure-longform.md` first.

- **Length:** at least 10 minutes of finished video, with no upper limit. That means at least about 1,400 words read at 135–145 words per minute. The chapter supports roughly 10–15 minutes.
- **Sources:** facts come from the book chapter. You may add facts from public reference pages, such as the National Gallery's page on the painting or Wikipedia. List every page you used in `sources.md`. No paid APIs.
- **Style** (from the narration research):
  - Lead the eye through three layers: what we see, what the sources say, how it can be read.
  - Vary sentence length. Mix longer sentences that build up context with short ones that land a point. The channel's median sentence is about 17 words, and about a quarter of its sentences run over 25 words.
  - Mark how certain each claim is, and include at least one competing reading or limit. The chapter itself says no painting has a single meaning.
  - Anchor history in objects in the painting.
- **Structure:** a cold open, a title card, then chapters with chapter cards. The channel's own Arnolfini episode uses cards such as "FASHIONS AND FABRICS". A suggested outline, following the book's sections:
  1. **Cold open (about the first 45–60 s):** challenge the popular myth. Most people think this is a wedding portrait of a pregnant bride; it is probably neither. Say why the painting has puzzled historians.
  2. **Bruges and Van Eyck:**
     - Bruges as a trading hub and the new merchant class.
     - The Arnolfinis came from Lucca.
     - Van Eyck became court painter to Philip the Good in 1425 and settled in Bruges in 1431; he finished the Ghent Altarpiece in 1432.
     - A Van Eyck portrait was the ultimate status symbol.
  3. **The Arnolfinis:**
     - Giovanni di Nicolao Arnolfini and Costanza Trenta married in 1426. They have no recorded children. Costanza died in 1433.
     - This is one of the earliest secular double portraits.
     - Read it as a marriage picture versus a memorial.
     - The dog and the medieval tomb effigies.
     - Posthumous portraits by Titian, Holbein and Bronzino.
  4. **Fashion and fabrics (the Arnolfini "brand"):**
     - The green dress is a fertility pose, not a pregnancy.
     - The dye was costly, and the miniver lining took up to 2,000 squirrel pelts.
     - Costanza is restrained with blue.
     - Giovanni wears plum and black, a plaited straw hat, and a silk-velvet tabard lined with pine marten. Note his soft boots and the muddy pattens.
  5. **The room sets the scene:**
     - The bed in a reception room, not a bedroom.
     - The settle, with gargoyles above the joined hands.
     - St Martha and her brush.
     - The rug, with the split-screen comparison with Virgin and Child with Canon van der Paele (1434).
     - The amber rosary.
     - The crown glass, and the orange that casts a shadow and is reflected in the window.
  6. **The mirror:**
     - It is convex and impossibly large.
     - It shows the couple from behind and two visitors; one may be Van Eyck himself.
     - The mirror as a symbol of purity.
     - Ten Passion roundels surround it, and every scene after Christ's death sits on Costanza's side.
  7. **The alchemist:**
     - The clues for a memorial reading, stated alongside their limits.
     - Mourning dress.
     - Giovanni's tentative grasp of her hand, as if she is slipping away.
     - Van Eyck's thin oil glazes.
     - His influence, from Dürer to Velázquez and the Pre-Raphaelites.
  8. **Closing:** pull back to the full painting, a memorial of a love that transcends death, and return to the opening question.

### C. The main video: `final_demo.mp4` (long-form, 10+ minutes)

Edit and render it in code on the server (Python with OpenCV, Pillow or NumPy, plus ffmpeg; moviepy only if you install it in your own venv), synced to your audio timing. Render in chapters within the 30-minute heavy-job limit (section 4), then concatenate.

It must show all of these:
1. **Title card in the opening:** a blurred-artwork background with clean typography showing the painting title, the artist and the year (1434). It may follow the cold open, as the channel does. Add **chapter cards** between chapters.
2. **Smooth virtual camera motion:** pan and zoom with no jitter. Avoid the integer-rounding jitter of ffmpeg `zoompan`; use supersampling or sub-pixel affine warping instead.
3. **Spotlight / highlight overlay:** dim the rest of the canvas while the target detail (the mirror, the joined hands) stays bright, starting at the moment the narrator names it.
4. **Split-screen comparison with labels:** The Arnolfini Portrait beside Virgin and Child with Canon van der Paele (or a detail crop of it), with clean, readable captions at the bottom.
5. **Audio polish:**
   - mix the voice with subtle, low-volume background music or room tone
   - normalise to -16 to -14 LUFS integrated, true peak at or below -1 dBTP
   - **do NOT burn subtitles into the picture.** Provide `subtitles.srt` as a sidecar file. Muxing it as a soft subtitle track (mov_text) is optional. With no subtitles on screen, labels and captions can sit where the channel puts them.

Beyond these, use every other catalogued technique wherever the channel itself would use it at that point in the story. Long-form pacing matters: the channel holds one image across several sentences and does not cut once per sentence, so match its measured holds and camera speeds rather than compressing them.

### D. The technique reel: `technique_reel.mp4`

This is the core of the research.

- **Format:** 1920x1080, 30 fps.
- **Content:** one segment of 4–8 s for each `EFFECTS_CATALOG.md` record you can build, applied to the Arnolfini or Van der Paele images. Put a small corner label on each segment, e.g. `CAM-01 Push-in`. Labels appear in the reel only, never in `final_demo.mp4`.
- **Order:** by record ID.
- **Missing material:** for a record that needs material you don't have (interview footage, city footage, real objects), either build a stand-in and say so, or skip it and explain why in the report.

## 7. Deliverables (in the Mac folder `demo_runs/<agent>/`)

1. **`final_demo.mp4`:** at least 10 minutes long; 1920x1080, 30 fps, H.264 + AAC; no burned-in subtitles.
2. **`technique_reel.mp4`.**
3. **`timeline.json`:** one entry per shot, with:
   - start and end time
   - the effect and its catalogue record ID
   - the image used, with source and licence
   - the parameters (zoom from/to, pan path, easing, duration)
   - the narration words the shot is synced to
4. **`script.txt`, `subtitles.srt` (sidecar) and `sources.md`.**
5. **Contact sheets:**
   - `contact_sheet_NN.jpg`: one frame every 10 s of `final_demo.mp4`, with timestamps burned in, in pages of about 40 tiles.
   - `reference_compare.jpg`: for at least 10 shots, your frame next to the closest matching moment in `T15Kv6dtYO0.mp4`, both labelled with timestamps.
6. **`capabilities_report.md`,** the main research output:
   - **Catalogue table:** one row for every record in `EFFECTS_CATALOG.md`, with:
     - status (done / partial / not done)
     - method and libraries used
     - the parameters measured in the reference next to yours
     - where it appears in your videos (timestamp)
     - a quality self-rating from 1 to 5
     - for partial or not done: what blocked you and what it would take
   - **Extras:** techniques you can do that are not in the catalogue.
   - **Timing:**
     - time spent per phase (extraction, script, TTS, editing code, rendering, QA)
     - render time per minute of output on the server
     - every problem you hit with the server
   - **Audio and sync:**
     - TTS settings and the final `atempo`
     - how visuals were synced to speech
     - measured loudness and true peak

## 8. Self-QA before you finish

- **Look at your contact sheets.** Open every `contact_sheet_NN.jpg` and `reference_compare.jpg` and inspect them yourself. Check for:
  - no burned-in subtitles
  - no cropped heads or faces
  - no overlapping labels or captions
  - no black or frozen frames
  - no raw black bars
  - no stretched images
- **Measure the output.**
  - ffprobe: resolution, frame rate, codecs, and a duration of at least 10 minutes
  - loudness: ffmpeg `ebur128` or `loudnorm` in print mode
  - jitter: for example, the frame-to-frame motion spread on one camera-move shot
  - sync: every highlight starts within ±0.25 s of the word it illustrates
- **Run vmetrics.** If it applies to 16:9 video, run `/Users/nhanvu/Documents/code/behind-the-image/tools/vmetrics.py`.
- **Clean up.** Leave `D:\bench\<agent>\` in place, release the heavy-job lock, and confirm `git -C D:\code\comic-book-pipeline status --short` is the same as when you started.
- **Final report to the human:**
  - the path to `final_demo.mp4`
  - duration, loudness and true peak
  - the TTS settings
  - the sync method
  - the done / partial / not-done counts from `capabilities_report.md`
  - anything you could not do
