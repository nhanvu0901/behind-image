# Shared brief for the niche-research agents (2026-11-12)

## Who we are
One person runs a pipeline that makes faceless narrated short videos. What the engine does today:
1. downloads a comic issue as page images;
2. finds the panels (Magi model) and reads the speech bubbles (OCR);
3. writes a 45-60 second narration from researched facts (LLM), in a "spoken text" style;
4. shows a review screen where one still image OR one video clip is picked for every narration beat;
5. voices it with a free local TTS voice clone (Chatterbox) and gets word timings;
6. renders 1080x1920: stills with pan/zoom per beat, optional clips cut from YouTube videos, music synced to a reference track. Captions are added by hand in CapCut.
Variants that already exist: Q&A across several comics; 30-50 s single-moment videos; movie/TV "screen Q&A" built from clips; "comic vs show" comparisons; a sister art-history pipeline that uses public-domain museum images; a long-form mode. Output capacity: about one video per day. Compute: a Mac and a Windows PC without a strong GPU. The owner also runs faceless philosophy channels (Carl Jung, Machiavelli) made from stock clips.

## Where we stand
English comic-book Shorts channel: 69 subscribers, 65 Shorts, median 1.6k views, best 8.2k. Big competitors in the same niche get medians of 11k-147k. Small channels in the niche split: some sit at 1.1-1.5k like us, some reach 6-12k medians.

## The question
Which OTHER niches or adjacent formats could this same engine serve with a real chance of going viral on short video (YouTube Shorts first; TikTok, Instagram Reels and Facebook Reels count too)?

## Scorecard (use exactly these columns so reports can be merged)
Score every candidate niche 1-5 on:
- DEMAND: measured views on recent Shorts in the niche.
- SMALL-CHANNEL PROOF: a channel under about 5k subscribers, started in 2026 or late 2025, that gets 10k+ views per Short. Name it, with numbers. 5 = several such channels; 1 = none found.
- COMPETITION: 5 = few capable channels, 1 = saturated.
- RISK: 5 = safe. Consider source rights, Content ID claims, takedowns, and YouTube's "inauthentic / reused content" monetization policy.
- FIT: 5 = our engine works with a small adapter; 1 = a different product.
- DEPTH: 5 = hundreds of stories available, 1 = a handful.
Then one line: the viral mechanism (why a stranger stops scrolling and finishes it).

## Evidence rules
- Every number needs a source URL and a date. Mark each as MEASURED (you fetched it), REPORTED (a named source says so) or ESTIMATED.
- If you cannot find small-channel proof, say so. Never invent a channel, a number or a quote.
- Prefer 2026 data. Shorts advice from before 2025 is often outdated.

## Tools and limits
- Use WebSearch and WebFetch as the main tools.
- `~/.local/bin/yt-dlp` may be used for at most 6 light calls in total (flat listing of a channel's /shorts tab, which returns view counts, e.g. `yt-dlp --flat-playlist -J --playlist-end 30 --sleep-requests 2 "https://www.youtube.com/@handle/shorts"`). Run them one at a time. Never request captions or download videos. Stop using yt-dlp at the first HTTP 429 or "confirm you're not a bot".
- No paid APIs. Do not modify the repo at /Users/nhanvu/Documents/code/comic-book-pipeline (read-only).
- Write your report where your task says, max 600 words plus the scorecard table. Final message to the orchestrator: under 250 words.
