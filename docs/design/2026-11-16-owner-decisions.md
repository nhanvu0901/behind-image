# Owner decisions, 2026-11-16

Answers given by the owner to the fourteen design questions. They override earlier documents (`PLAN.md`, and the licence rule in the editor design) where they differ.

| # | Topic | Decision |
|---|---|---|
| 1 | Unit of a video | One painting per video. All books in `books/` are preprocessed so that the same painting in several books is merged into one dossier. |
| 2 | Formats | 16:9 only. Later: a skill that cuts a highlight of a finished video into a Short. |
| 3 | Voice and look | The comic channel's narrator voice. A new visual identity for this channel, not a copy of the reference channel. |
| 4 | Sources rule | Copyright is not to be a blocking concern. No "two sources" rule as a legal gate. |
| 5 | Artworks still in copyright | Make them. |
| 6 | CC BY-SA images | Allowed. |
| 7 | Extra media sources | Stock video (Pexels, Pixabay), YouTube clips under a Creative Commons licence, and OpenStreetMap maps are allowed. |
| 8 | Review points and cadence | The owner confirms: the narration; what is on each scene; added scenes; cuts to the narration. Target: two videos a week. The script step works like the comic pipeline: the system returns an outline ("dàn ý"), the owner pastes it into Gemini, and pastes the whole narration back. |
| 9 | How the model runs | A button in the UI writes the narration, with a dropdown to choose the model, so the owner does not have to copy and paste. **The model is reached by spawning the Antigravity CLI (`agy`, headless) under the owner's subscription, not through the Gemini API.** Copy and paste stays available as a second path. Both paths must produce the same narration data. |
| – | Keys | This project uses the same `.env` as the comic pipeline. It was copied to the project root on 2026-11-16 at the owner's instruction and is git-ignored. Code reads only the variables this project needs. |
| 10 | Technique freedom | An agent drafting a storyboard may use all 71 techniques. |
| 11 | You.com | Used to find more images and video for scenes, above all context and background scenes that today show a single image. |
| 12 | Music | No preference. |
| 13 | Server schedule | Fine as proposed. |
| 14 | Version control | Yes. Done: the repository was initialised and committed on 2026-11-16. |

## What changes in the build

- **Licence gate becomes advisory.** It still reads and records the licence, author and source of every asset, because the video description needs the credits and the owner should see what each asset is. But it warns instead of blocking. An asset with a rejected or unknown licence can be imported; it is flagged in the project.
- **Rights estimates in the library are information only.** They never hide or block an artwork.
- **The library becomes artwork-centred.** The entry point is the list of paintings, each merged across books, not the list of books.
- **The script step is a copy-and-paste loop,** modelled on the comic pipeline: export an outline and prompt, import the pasted narration, validate it, and split it into beats.
- **Scene enrichment:** You.com research proposes extra visuals for beats that have too few. The owner picks from them.
- **A new style pack** will sit beside `style/gae/`, with its own fonts and card designs.
