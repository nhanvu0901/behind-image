# D_report: why Grimframe Shorts get far fewer views (data agent, 2026-11-12)

**Correction:** `@grimframe` is not our channel. It is an unrelated anime/ASMR edit channel (47 subs). Our channel is **`@Grimframe-l9e`** (`UCuTyuJ7O4Os1tqt9KJDdwiA`, 69 subs, 65 Shorts). Side note: `config.py` defaults `CHANNEL_HANDLE` to `@grimframe`. Only the outro card shows it, and the card is off by default.

## Headline (measured)

| Channel | Subs | Shorts/wk (Oct 1–Nov 11) | Median views, newest 30 (p25–p75) | Median views, aged 4–21 d (n) | Share ≥10k (4–21 d) | Max (newest 30) | Like/view | Comments/view |
|---|---:|---:|---|---|---:|---:|---:|---:|
| **Grimframe** | **69** | **3.0** | **1,629** (1,365–2,028) | **1,692** (6) | **0%** | 8,216 | **1.93%** | ~0 |
| ComicCandid | 39,300 | 6.3 | 10,998 (6,246–20,500) | 15,108 (22) | 59% | 31,000 | 2.75% | 0.018% |
| Comic_Escape | 271,000 | 7.0 | 23,000 (12,938–31,000) | 23,274 (18) | 78% | 321,849 | 4.31% | 0.048% |
| GiyeSears | 78,400 | ≥4.0* | 26,812 (13,124–53,750) | 16,567 (13) | 85% | 2,300,000 | 3.62% | 0.032% |
| ComicsUnlocked | 689,000 | 4.8 | 30,002 (21,000–33,435) | 30,005 (13) | 92% | 791,433 | 3.62% | 0.042% |
| comiczyt | 156,000 | 7.0 | 146,602 (77,294–384,912) | 134,187 (18) | 100% | 990,000 | 4.08% | 0.040% |

\*GiyeSears dates are known only back to Oct 7, so its rate is a lower bound. Engagement counts only videos with ≥300 views and full metadata (n=29–45 per channel).

| Median views at age | Grimframe | CC | CE | GS | CU | CZ |
|---|---:|---:|---:|---:|---:|---:|
| 0–1.5 d | 1,311 (n=1) | 10,351 | 5,221 | 3,049 | 5,002 | 24,479 |
| 3.5–7 d | 5,462 (n=2) | 15,928 | 23,955 | 14,907 | 28,888 | 124,313 |
| 7–14 d | 1,541 (n=3) | 15,216 | 14,177 | 16,602 | 28,558 | 122,938 |

## Findings

1. **Our views stop at 1–3k; their floor sits at our ceiling.** (High, measured.)
   - 82% of our newest 40 Shorts have 1k–3k views, and none of our 65 reached 10k.
   - Spread (p90/p10): 2.6 for us vs 9–737 for competitors.
   - Each competitor's lowest video in its newest 30 has 3.0k–23k views, so none fall under 3k.
   - Our best video (8,216) is below every competitor's 4–21 d median.
   - Inferred: each video gets one first test batch and rarely earns more.

2. **The outcome is set within about 72 hours.** (High for competitors, n=24–37 per channel; low for us, one snapshot.)
   - Competitor videos aged 3–7 days on Nov 3 grew 1.00–1.27× by Nov 12; those older than 7 days grew 1.00–1.03×.
   - Our 23-hour-old video is already in the band (1,311).

3. **The channel-size gap is huge, but it does not explain everything.** (Medium.)
   - Subscribers: 570–10,000× ours. Per-video views: 6.5–90× ours.
   - Our median video gets 24× our subscriber count (theirs 0.04–0.94×). Our audience is almost entirely non-subscriber feed traffic.
   - Among the 5 competitors, subscribers barely predict views per video (Spearman ρ≈0.5, n=5). ComicCandid has 39k subs and still gets 7–9× our views.
   - Inferred: first-batch performance matters more than size, but this data cannot prove it.

4. **Characters and franchise do not explain the gap.** (Medium–high; title regex over 1,500 competitor and 65 of our titles.)
   - A-tier character in the title: 58.5% for us vs 59.9% for them. Named character: 98.5% vs 79%. What-If/2099/variant framing: 7.7% vs 7.5%.
   - Within competitor channels, A-tier titles do no better: median 1.00× vs 1.00× the channel median (n=898/602). Batman, Spider-Man and Superman are slightly under-represented among breakouts (videos ≥5× their channel median), with lift 0.65–0.93.
   - The one strong signal is **The Boys/Homelander**: n=35, median 12.5× the channel median, lift 4.6, on all 5 channels. Invincible (1.6) and Green Lantern (1.5) come next.
   - We have no Boys or Invincible videos. Our Green Lantern "Mogo" video is our #2 (7,460).

5. **Titles don't separate winners, but ours are longer.** (Medium.)
   - Competitors' top and bottom quartiles differ by ≤4 points on every feature: question 9.6% vs 12.8%, emoji 19% vs 20%, CAPS 23.5% vs 24.3%, 5.95 vs 5.91 words.
   - Our titles average 8.4 words / 50 characters. Competitors' channel averages are 5.0–6.75 words / 31–39 characters.
   - We use more How/Why/What openers (26%; 40% of the newest 20) and more numbered lists (26% vs 7%).

6. **Fewer likes and almost no comments.** (Medium.)
   - Like/view: 1.93% for us (IQR 1.4–2.5, n=38) vs 2.75–4.31%.
   - Comments are about zero on most of our videos. They get 2–5 per 10k views.
   - Our like rate is up from 1.69% (Jul–Aug) to 2.50% (Oct–Nov).
   - Subscribers like more, so this is not a pure quality signal.

7. **Lower and uneven cadence.** (Measured; effect per video unknown.)
   - We post 3.0/wk vs 4.0–7.0.
   - Gaps with no uploads: 47 days (Aug 2–Sep 18) and 12 days (Oct 17–29).
   - Six-week total views: 41.5k for us vs 0.56M–17.4M. Cadence explains at most about 2× of total views, not the per-video gap.

8. **Duration and the mascot don't explain it.** (Duration: high. Mascot: low, n=5.)
   - Duration: our median is 48 s (IQR 42–56), inside the 44–54 s range of the three short-format competitors. Pooled competitor views are flat across length buckets (0.98–1.03×).
   - Mascot: the 5 mascot-era uploads (Nov 7–11) have a median of 1,931 (1,638 without the 8.2k outlier). The 10 before have 1,585 (1,541). Like/view 2.68% vs 2.50%.
   - Too small a sample to detect anything under about 2×.

**Since July:** median rose from 1,150 to 1,629 and the top video from 5,900 to 8,216. Still 0% of videos reached 10k. Cadence fell from ~5 to 3 per week. Competitors' recent medians are also far below their all-time medians (CU 30k vs 236k, CC 11k vs 28k), so 10–30k per video is the realistic level in this niche today.

**Metadata hygiene (low confidence it matters):**
- Tags: none on our videos; competitors use them on 73–100% (3 of 5 channels).
- Descriptions: ours are empty (median 0 characters); competitors' carry hashtags on 53–100%.

## What the data cannot tell us
- Retention, average view duration, swipe-away rate, impressions and traffic sources. These are the real ranking inputs and need YouTube Studio.
- Whether the first test-batch size depends on subscribers. No same-size channel was refreshed; in July, ComicCut (404 subs) had a 4,750 median and VillainHubs (860 subs) 2,900.
- Any causal effect of the mascot, cadence or titles. Everything here is correlational.
- Story and visual quality (the forensics agent's job), or whether The Boys effect is seasonal.
- Exact views for competitor videos without full metadata: flat listing counts are rounded to 2 significant figures.

## Raw data (`/private/tmp/claude-501/-Users-nhanvu-Documents-code-comic-book-pipeline/5ea9df33-4e6f-4fab-bcf2-4af854ff5d43/scratchpad/view_gap/data/`)
- **Our channel:**
  - `ours/listing.json`: 65 Shorts, flat listing.
  - `ours/meta/<id>.json`: full metadata for the newest 40.
  - `ours/sample.json`, `ours/video/*.mp4` (8 videos, 608×1080, AV1) and `ours/READY`.
  - `ours/listing_snapshot2.json`: second listing, rounded counts, about 30 min later.
- **Captions:** `ours/subs/` is empty. The caption endpoint returned HTTP 429 twice, so I stopped.
- **Competitors:**
  - `comp/listing/<Channel>.json`: full /shorts tabs with subscriber counts.
  - `comp/meta/<id>.json`: newest 15 per channel plus the 10 samples.
  - `comp/sample_growth.txt`: Nov 3 → Nov 12 views for the 10 samples.
- **Wrong channel:** `probe/wrong_at_grimframe_listing.json`.
- **Analysis:** `scripts/analyze.py` writes `analysis.txt` and `analysis.json`. The fetch scripts are in `scripts/`.
