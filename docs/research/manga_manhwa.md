# Manga / manhwa / webtoon / anime niche (research 2026-11-12)

## Scorecard

| Candidate | DEMAND | SMALL-CHANNEL PROOF | COMPETITION | RISK | FIT | DEPTH | Viral mechanism |
|---|---|---|---|---|---|---|---|
| A. Manga-panel explainers / power-scaling / "who would win" / Q&A | 4 | 2 | 2 | 3 | 5 | 5 | A fan sees their favourite character in a fight or debate and stays for the verdict, then argues in the comments |
| B. Horror-manga one-shot recaps (Ito, Umezu, Hino and others) | 3 (ESTIMATED) | 1 | 4 | 3 | 5 | 4 | Dread builds through the story and the twist lands in the last 10 seconds, so viewers finish and rewatch |
| C. Manhwa/webtoon recap Shorts (60 s "weakest to strongest" teaser) | 3 | 2 | 2 | 2 | 4 | 5 | The trope hook ("everyone laughed at his useless skill...") gives an instant power-fantasy promise |
| D. Manhwa long-form recap (1-36 h) | 5 | 2 | 1 | 2 | 2 | 5 | Binge-watching a whole series in one sitting |
| E. Weekly chapter / spoiler videos (One Piece, Kagurabachi) | 4 | 1 | 1 | 1 | 2 | 3 | Fear of missing out on this week's chapter |
| F. Anime-clip "moment" Shorts (no narration) | 5 | 4 | 2 | 1 | 2 | 5 | A caption-bait hook plus a visual payoff |
| G. Manga vs anime differences | 2 (no data found) | 1 | 3 | 2 | 4 | 4 | "You missed this if you only watched the anime" |

## Evidence (all retrieved 2026-11-12)
- **D is alive and huge (MEASURED, yt-dlp search "manhwa recap shorts").** 40 results, mostly 1-5 h videos. Examples: Manhwa Fresh at 1.74M views (36 h video), Frieren Manhwa at 1.06M, Mamoru Manhwa at 1.11M. Dozens of look-alike channels appear in that one result set.
- **D Shorts tab (MEASURED, partial).** yt-dlp returned no Shorts listing for Manhwa Fresh. A Shorts-filtered search returned only 2 tutorials. I found no proof that Shorts feed the long-form channels.
- **C (REPORTED, vidIQ).** QuickComick, a narrated manhwa/manga panel channel created June 2024, has 5.97M views from 53 videos but only 22.7k views in the last 28 days: https://vidiq.com/youtube-stats/channel/UCvw3EKYhrHxIYdVwbVbSabg . Two narrated-panel Shorts channels that web search surfaced no longer resolve on YouTube (MEASURED): @PanelPuls3 returns 404 and UChwNkZhSYqpiwIEKQ1eJvbA returns "channel does not exist". The cause is unknown. New 2026 manhwa channels on Vling sit at 259-1.3k subscribers (REPORTED, https://vling.net/en/channel/UCCyd73C6UpSLsV4u59eSC7A/channel-info).
- **F small-channel proof.** GoodShortsVideoAnime was created 2026-07-04. In August it gained 1.59k subscribers and 3.51M views while under 5k subscribers (REPORTED, https://vidiq.com/youtube-stats/channel/@gsvanime/). The median of its last 30 Shorts is 181k views (MEASURED). It posts raw anime clips with no narration.
- **A demand.** Lord Aizen (power-scaling) had 2.76M subscribers in July 2025 (REPORTED, vidIQ). Manga And Anime gained 33k subscribers in 28 days (REPORTED, https://vidiq.com/youtube-stats/channel/@animeeandmanga/). Neither is a small channel.
- **E.** The Spanish spoiler channel RayXaX gets 37-104k views per chapter video (REPORTED, speakrj, 2026-04-05).
- **Audience size.** Manga is close to 57% of US graphic-novel sales, an unreconciled secondary figure (REPORTED, https://icv2.com/articles/news/view/61573/). WEBTOON has 156.9M MAU in Q2 2026 (REPORTED, ANN 2026-08-31). The audience is clearly larger and younger than the Western-comics audience. TTS voices look tolerated: most long-form recap channels sound synthetic (ESTIMATED; there is no audience survey). But the niche is far more saturated than Western comics.

## Copyright
- **KADOKAWA v. YouTube, N.D. Cal., 2026-07-17.** The court rejected fair use for narrated anime-recap channels (500k+ subscribers) because they "describe and narrate" without transforming the work. It ordered YouTube to unmask the creators. The case is on appeal (https://torrentfreak.com/court-rejects-fair-use-claim-orders-youtube-to-unmask-anime-recap-channels/, 2026-08-14). This is the single biggest risk to pure recaps (C, D, F).
- **Kakao.** Kakao is a Google Trusted Copyright Removal Program member (bulk takedowns) and names YouTube as a channel for translated webtoons (https://newsroom.kakaoent.com/news/kakao-entertainments-ongoing-efforts-to-stamp-out-illegal-content-piracy-achieves-significant-industry-milestone/). Recaps mostly use fan-translated scans, so they carry a double exposure.
- **Shueisha.** A Japanese court made YouTube help shut down spoiler videos (Shogakukan, 2018). Japan has also arrested manga leakers (2024). The 2021 mass strikes were sent by a third party (Shueisha denied them). I found no 2025-26 Shueisha YouTube strike wave.
- **Anime footage.** Crunchyroll recruits for Content ID and TCRP roles (Xataka 2026). A Short over 1 minute that carries a Content ID claim is blocked (https://support.google.com/youtube/answer/13053317).
- **Monetization policy.** Since 2025-07-15, YouTube's "inauthentic content" policy names near-identical narrated slideshows, which is the template of the recap channels.

## Webtoon strips vs pages (for our engine)
Webtoons are 800 px-wide strips cut into arbitrary slices. The slices often split panels, and panels are separated by blank space rather than borders. Reading order is simply top to bottom, and panels are already portrait, so a slow vertical pan is the native 9:16 grammar. The adapter would stitch the slices and then cut at blank rows; `gutter_split.py` is a start. Magi is not needed there. Manga, in contrast, is Magi-native but reads right to left. `sort_western_reading_order` is left-to-right only, so a right-to-left mode is required.

## Verdict
- **Best 3:** A (fits our Q&A/explore_answer mode, and commentary across many chapters is the most transformative and safest format), B (fits recap mode, 20-40-page one-shots, low competition), C (strip-native, but saturated and risky).
- **Avoid:** E (Shueisha and leak legal heat, no small channels), F (Content ID plus the KADOKAWA ruling, and not our product), D (saturated and mass-produced; flagged as inauthentic).

## Best bet: A. The first 10 videos
1. Every character who has touched Gojo's Infinity
2. Gear 5: the Nika clues Oda planted before chapter 1044
3. Sukuna's barrier-less Domain explained
4. Strongest Haki users ranked by on-panel feats
5. Every time Makima's control was shown on panel
6. Kagurabachi: what each enchanted blade does
7. The Brand of Sacrifice: what it really does (Berserk)
8. Sung Jinwoo vs Gojo: feats compared
9. What happened to the Founding Titan's power after the Rumbling
10. Each Hashira's strongest technique, manga-only details

## What the engine lacks
- a right-to-left reading-order switch;
- a manga page source (`download.py` reads only batcave.biz; official MangaPlus/VIZ can't be scraped, and scan sites add risk);
- Fandom-wiki fact grounding per series (Stage 1 already uses Fandom, so this is mostly config);
- black-and-white framing and upscaling;
- a webtoon strip slicer (for C);
- burned-in captions;
- a licence check: Magi v3 is "academic-research license" per `panel_detect.py`, which matters for a monetized channel.
