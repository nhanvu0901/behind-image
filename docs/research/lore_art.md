# Fandom lore told over still artwork: niche report (2026-11-12)

## Scorecard

| Niche | DEMAND | SMALL-CHANNEL PROOF | COMPETITION | RISK | FIT | DEPTH | Viral mechanism |
|---|---|---|---|---|---|---|---|
| SCP Foundation | 4 | 1 | 2 | 4 | 3 | 5 | "Object that kills you if you look at it": a forbidden rule plus a twist, in a classified-file style |
| Star Wars lore (told from comic panels) | 4 | 1 | 2 | 2 | 5 | 5 | "Why did Vader/Yoda/the Empire do X?": a fan question answered with a moment nobody saw on screen |
| FromSoft game lore (Elden Ring, Souls) | 5 | 1 | 2 | 3 | 3 | 4 | "Who is this NPC you killed?": a sad backstory reveal about something the viewer already met |
| Horror (cryptids, folklore, Lovecraft, creepypasta) | 3 | 1 | 1 | 3 | 3 | 5 | Fear plus "is it real?" |
| Dune / ASOIAF / Witcher | 3 | 1 | 3 | 2 | 3 | 3 | Release-date spikes: Dune: Part Three on 18 Dec 2026 [21] |
| Warhammer 40k | 2 | 1 | 2 | 1 | 3 | 5 | Grimdark absurdity, but the audience is in long-form "sleep lore" |
| Tolkien / LOTR | 2 | 1 | 3 | 2 | 2 | 4 | Hidden backstory of famous characters |
| D&D monsters | 2 (ESTIMATED, not measured) | 1 | 3 | 3 | 2 | 4 | "This monster eats your memories" |

**Small-channel proof:** no candidate had any. I found no lore channel under 5k subscribers, started in late 2025 or 2026, that gets 10k+ views per Short. The one 2026 breakout I found, LoreLabzz (joined 2 Feb 2026, 81.5M views), turned out to make science/curiosity videos, not lore.

## Key evidence

- **Elden Ring.** VaatiVidya's 21 Shorts posted in 2026 have a median of **930k** views (range 422k to 3.62M) with the "Who is X in Elden Ring? | Lore Shorts" format [1]. He has 3.34M subscribers and uses in-game footage.
- **Star Wars.** Star Wars Apprentice (217k subs): the latest 30 Shorts have a median of **34.5k** views and a top of 288k [2]. Hooks are "Why…" questions. Its monthly views fell from 5.76M (May) to 1.26M (Oct 2026), so the niche is cooling.
- **SCP.** SCP Explained has 2.49M subs and 6.3M views in the last 28 days, but none of its last 48 uploads is a Short [9]. SCP live-action and animated films reach 16 to 31M views (lifetime counts) [23]. Viewers expect motion, so stills are a weaker fit here.
- **Warhammer 40k.** Shorts on big lore channels get 2.1k to 11.6k views [4]. The top 19 videos on the #warhammer40klore hashtag page are all long-form, and at least 4 of them put "(No AI)" in the title [5].
- **Tolkien.** Shorts from Tolkien channels get roughly 6k to 38k views, and most of them are merchandise or event clips, not lore [13][14][15].

## Art sources and trouble

- **SCP.** Article text is CC BY-SA 3.0. The wiki only allows CC BY, CC BY-SA, CC0 or public-domain images, and each article credits them in a License Box at the bottom [11]. Videos must carry the CC BY-SA notice, and the original SCP-173 image is barred from commercial use [10]. The wiki admins say no one can hold exclusive SCP rights, even with A24 distributing *V/H/S: SCP* in 2027 [12].
- **Warhammer 40k.** Games Workshop bans fan animations and bans fan sites from copying official artwork [8]. YouTube removed The Remembrancer from its Partner Program (no ad revenue) on 18 Dec 2025 under the "Inauthentic Content" policy. It cited "readings of others' materials … slideshows with minimal narrative" and reversed the decision on 9 Jan 2026 [6]. In February 2026, a hobby news site reported that YouTube's AI flags were hitting real lore creators [7]. **Avoid.**
- **Tolkien.** The well-known art (Alan Lee, John Howe, Ted Nasmith) and the film stills are all copyrighted, and the Tolkien estate sues. **Avoid.**
- **Game publishers.** FromSoftware allows money from YouTube's partner program [16], CD Projekt allows ad-funded fan videos [17], and Wizards of the Coast allows ad revenue but is unclear on artwork [18].
- **Horror.** Most of Lovecraft's fiction is public domain in the US [19]. Creepypasta stories belong to their authors, and the niche is flooded with AI art [20]. **Avoid** creepypasta. Cryptids and folklore over public-domain engravings remain an option.
- **Comic adaptations.** Dune, The Witcher and ASOIAF all have graphic-novel adaptations, so our current comic pipeline can serve them as one-off videos timed to a release.

## Best 3 bets

1. **SCP Foundation.** It has the cleanest rights, with legal text and legal art. It has thousands of entries and a film-driven buzz cycle heading into 2027.
2. **Star Wars lore from comic panels.** It runs on our engine as it is today and has measured demand of about 35k per Short. The risk is the same Disney/Marvel panel risk we already carry.
3. **FromSoft lore.** It has the highest demand we measured, but it needs game screenshots, and VaatiVidya owns the format.

**Avoid:** Warhammer 40k (Games Workshop rules, demonetizations, an audience hostile to AI, weak Shorts), Tolkien (rights, weak Shorts), creepypasta (author copyright, AI-slop saturation), and D&D (unclear art rights, thin Shorts demand).

## SCP: the first 10 videos

1. SCP-096 "Shy Guy"
2. SCP-682, the lizard the Foundation can't kill
3. SCP-3008, the infinite IKEA
4. SCP-049 "Plague Doctor"
5. SCP-106 "Old Man"
6. SCP-999, the tickle monster
7. SCP-055, the anti-meme
8. SCP-3000 "Anantashesha"
9. SCP-5000 "Why?"
10. SCP-2317 "A Door to Another World"

## What the engine lacks for SCP

- **An image source adapter for SCP wiki articles.** It should collect each image plus its License Box credit, and auto-build the description's attribution block (license notice, article author, image credits).
- **Locally rendered "classified file" cards** with redaction bars and the containment class. Most articles have only 0 to 2 images, but a video needs 6 to 10 visuals.
- **A single-image mode that skips the Magi/OCR steps.** Most of this already exists: landscape images get contain+blur.
- **A script rule: analysis, never a reading of the article.** "Readings of others' materials" is YouTube's own example of inauthentic content [6].
- **A banlist for the original SCP-173 image.**

## Sources

All accessed 2026-11-12. MEASURED means I fetched the numbers myself (via vidIQ or yt-dlp); REPORTED means a named source says so.

1. MEASURED via vidIQ: https://vidiq.com/youtube-stats/channel/@vaatividya/videos/
2. MEASURED with yt-dlp: https://www.youtube.com/@starwarsapprentice/shorts ; monthly views via vidIQ: https://vidiq.com/youtube-stats/channel/UCGOJYqJWvVslBYRYzm3rCUw
3. (not cited above) MEASURED via vidIQ: Star Wars Theory's two 2026 Shorts got 84k and 93k views. https://vidiq.com/youtube-stats/channel/@starwarstheory/videos/
4. MEASURED via vidIQ: https://vidiq.com/youtube-stats/channel/@theremembrancer/videos/ and https://vidiq.com/youtube-stats/channel/@40ktheories/videos/
5. MEASURED with yt-dlp: https://www.youtube.com/hashtag/warhammer40klore
6. REPORTED, Wargamer, 2026-01-10: https://www.wargamer.com/warhammer-40k/the-remembrancer-demonetized-and-reinstated
7. REPORTED, Spikeybits, 2026-02-12 (search snippet only; the page returned 403): https://spikeybits.com/another-40k-youtuber-gets-hit-but-not-by-games-workshop
8. REPORTED, PC Gamer (2021 guidelines): https://pcgamer.com/games-workshop-is-trying-to-shut-down-fan-animations
9. MEASURED via vidIQ: https://vidiq.com/youtube-stats/channel/UC8JfkMtNAp44vmzdtnL4wow
10. https://scp-wiki.wikidot.com/licensing-guide
11. https://scp-wiki.wikidot.com/image-use-policy
12. REPORTED, Plagiarism Today, 2026-09-14: https://www.plagiarismtoday.com/2026/09/14/when-hollywood-comes-for-creative-commons-stories/
13. MEASURED via vidIQ: https://vidiq.com/youtube-stats/channel/@nerdoftherings/videos/
14. MEASURED with yt-dlp: https://www.youtube.com/@InDeepGeek/shorts (only 3 Shorts)
15. MEASURED via vidIQ: https://vidiq.com/youtube-stats/channel/@menofthewest/videos/ (no Shorts)
16. REPORTED: https://automaton-media.com/en/news/20220221-9875/
17. https://cdprojektred.com/fan-content/
18. https://company.wizards.com/en/legal/fancontentpolicy
19. https://www.gutenberg.org/ebooks/68283
20. REPORTED by a vendor, July 2026: https://virlo.ai/agents/horror-storytelling-gn4j9q
21. REPORTED: https://www.pulse.bot/movies/video/dune-part-3-official-trailer-breakdown-easter-eggs-messiah-plot-points-and-things-you-missed-03d2f451-6083-40ac-a8e3-c78121a8abb2
22. (not cited above) REPORTED: YouTube's inauthentic-content examples include "multiple slideshow presentations with identical narration". https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/
23. MEASURED with yt-dlp `ytsearch40:"SCP foundation #shorts"` (lifetime counts, upload dates not shown).

**yt-dlp use:** all 6 calls were spent. Three of them (two YouTube searches and one hashtag page) returned no Shorts. YouTube search results and hashtag pages do not list Shorts, so those calls could not measure Shorts demand.
