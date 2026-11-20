# Channel identity "Raking Light": opening, channel-name beat and chapter marks, in two selectable styles

Date: 2026-11-18. Status: approved by the owner as moving mock-ups; this file is the build contract.
Evidence behind every rule: `docs/design/research/R9_titles_in_real_videos.md` (frames of 11 reference videos and 8 other films).
The approved mock-ups (moving, with sound): `docs/design/2026-11-18-d13-identity-mock.html` (its picture and sound files are
not in the repository; read its script for the exact curves: clips `rakingOpen`, `rakingMark`, `rakingBrand`, `dimOpen`, `dimMark`).

## 1. What the owner decided
- The channel is called **Raking Light**.
- The first mock-ups (title card, chapter card) were rejected: "look really AI and look rather slide than actual human video".
- Of four moving treatments the owner kept two: **A "Vệt sáng quét"** (raking pass) and **C "Tối lại, hiện tên"** (dim and name).
  Their words: "save A and C have option for me to choose between this two for agent as well when render video".
- So: both styles are built. Which one a video uses is a choice **per video**, made by the owner on the page or by an agent
  through the API, and it can be changed at any time before the export. Default for a new video: `raking` (my call, A carries the name).

## 2. The rules both styles obey (from R9)
1. A film never starts with a title card. It opens cold on the moving picture. The painting's name comes later, small.
2. Text sits on the picture. No panel, card, strip, box, rule or flat colour ground. No giant numeral, no kicker line.
3. A chapter mark is ONE line "N. Title" (title case, number then words), cap height about 4.5 % of the frame height,
   about 3 seconds, on the first picture of the next chapter in a changed state (dark or dimmed), released at the end.
4. Only the channel name is large (cap height 7 to 8 % of the frame height), once, after the hook, followed by a hard cut.
5. Text never slides, types or scales. It fades (0.3 to 1.0 s) or is revealed by the light.
6. The narration is silent during a mark and during the channel-name beat (the voice step already leaves these gaps).
7. Typeface: EB Garamond (regular, italic, medium), free under the OFL, bundled with the project. Not the reference channel's
   faces. Normal tracking in sentences; wide tracking only for capitals (the channel name, the small-caps line).

## 3. What the viewer sees
Times are seconds from the start of the element. They are the **nominal** timeline. When the shot or overlay that carries an
element is shorter than the nominal length, every time value is scaled by (actual length / nominal length); an element is never
shorter than 1.5 s (validation error below that).

### Style `raking` (A)
- **Opening** (overlay on the first shot, nominal 9.0 s): black for 0.4 s; the picture rises to 10 % brightness by 1.2 s; from
  1.5 s to 7.5 s a band of light (14 % of the frame width, soft edges, edge tilted 10 degrees) travels from right to left; inside
  the band the picture is at 100 % with a slight warm tint; behind the band it stays at 45 %; ahead of it at 10 %; from 7.5 s to
  9.0 s the whole picture rises to 100 %. The camera move of the shot is not changed.
- **Label** (overlay, nominal 4.5 s, starts 6.2 s into the video): two lines bottom left, left margin 4 % of the width, block
  between 84 % and 92 % of the height: the title in italic (cap height 3 %), then "Artist, year" (cap height 2.3 %). Fades in
  0.5 s, out 0.5 s. No strip behind it; a soft shadow keeps it readable.
- **Channel-name beat** (its own shot, nominal 5.0 s): the picture that was on screen dims to 12 % in 0.6 s; a band sweeps left
  to right from 0.6 s to 3.0 s; the words RAKING LIGHT (capitals, cap height 8 %, tracking about +25 %, centred at 42 % of the
  height) are revealed along the band's path and stay; the picture behind the band settles at 26 %. Hard cut at the end.
- **Chapter mark** (its own shot, nominal 3.2 s): hard cut to the first picture of the chapter at 12 %; from 0.1 s to 2.1 s a
  band (18 % of the width) sweeps left to right; the line "N. Title" (centred, 50 % of the height) is revealed by the band and
  stays; behind the band the picture is at 55 %; from 2.5 s the picture rises to 100 % in 0.7 s and the text fades out in 0.4 s.

### Style `dim` (C)
- **Opening** (overlay, nominal 5.0 s, starts 7.0 s into the video): the frame dims to 45 % in 1.0 s; the title in italic (cap
  height 5 %) fades in over 0.8 s centred at 78 % of the height; 0.4 s later "ARTIST · YEAR" in small capitals (cap height 2.2 %,
  tracking +14 %) at 85.5 %; hold; in the last 1.0 s the text fades and the brightness returns. No separate label.
- **Channel-name beat** (own shot, nominal 4.0 s): the picture dims to 25 % in 0.8 s; RAKING LIGHT (capitals, cap height 7 %,
  tracking +25 %, centred at 46 %) fades in over 1.0 s, holds, fades out in the last 0.6 s. Hard cut at the end.
- **Chapter mark** (own shot, nominal 3.0 s, entered by a 0.75 s dissolve): the picture of the new chapter is shown dimmed to
  40 % (ramp 0.6 s); "N. Title" fades in from 0.3 s to 0.7 s (centred, 50 %); from 2.4 s the text fades out in 0.4 s and the
  picture returns to 100 % by the end.

## 4. Engine: seven new techniques (family `ID`)
All follow the existing interfaces of `bti/engine` (`BaseRenderer`, `OverlayRenderer`), are described in
`style/gae/techniques.json` with `label_vi`, defaults, `min`/`max` for every number, and get a preview like every technique.
The numbers below are defaults; names may be adapted to the registry's conventions, the behaviour may not.

| id | kind | slots | what it draws | main params (default) |
|---|---|---|---|---|
| `ID-OPEN-01` | overlay | none | raking reveal of the shot under it | `floor` 0.10, `wake` 0.45, `black_s` 0.4, `rise_s` 0.8, `sweep_start_s` 1.5, `sweep_s` 6.0, `direction` `rtl`, `band_width_pct` 14, `feather` 0.4, `angle_deg` 10, `release_s` 1.5, `warm` 0.14 |
| `ID-LABEL-01` | overlay | none | two-line artwork label without a strip | `title`, `artist_year`, `x_pct` 4, `bottom_pct` 92, `title_cap_pct` 3.0, `second_cap_pct` 2.3, `fade_in_s` 0.5, `fade_out_s` 0.5, `shadow` true |
| `ID-OPEN-02` | overlay | none | dim and name | `title`, `sub`, `dim` 0.45, `ramp_in_s` 1.0, `ramp_out_s` 1.0, `title_cap_pct` 5.0, `title_y_pct` 78, `sub_cap_pct` 2.2, `sub_y_pct` 85.5, `sub_tracking_pct` 14, `title_fade_in_s` 0.8, `sub_delay_s` 0.4 |
| `ID-BRAND-01` | base | `image` | channel name written by the band | `camera`, `text` (from the style's channel name), `dim_s` 0.6, `floor` 0.12, `wake` 0.26, `sweep_delay_s` 0.6, `sweep_s` 2.4, `band_width_pct` 16, `cap_pct` 8.0, `tracking_pct` 25, `y_pct` 42 |
| `ID-BRAND-02` | base | `image` | channel name on the dimmed picture | `camera`, `text`, `dim` 0.25, `ramp_in_s` 0.8, `fade_in_s` 1.0, `fade_out_s` 0.6, `cap_pct` 7.0, `tracking_pct` 25, `y_pct` 46 |
| `ID-MARK-01` | base | `image` | chapter mark written by the band | `camera`, `title`, `floor` 0.12, `wake` 0.55, `sweep_delay_s` 0.1, `sweep_s` 2.0, `direction` `ltr`, `band_width_pct` 18, `feather` 0.4, `angle_deg` 10, `release_at_s` 2.5, `release_s` 0.7, `text_fade_out_s` 0.4, `cap_pct` 4.5, `y_pct` 50, `warm` 0.14 |
| `ID-MARK-02` | base | `image` | chapter mark on the dimmed picture | `camera`, `title`, `dim` 0.40, `ramp_in_s` 0.6, `text_in_delay_s` 0.3, `text_fade_in_s` 0.4, `text_out_at_s` 2.4, `text_fade_out_s` 0.4, `release_s` 0.6, `cap_pct` 4.5, `y_pct` 50 |

- "Revealed by the band": the text's opacity at a pixel is the largest value the band's mask has had at that pixel so far, so
  the words are drawn in the band's direction and remain.
- `camera` is the same key list as `CAM-01`; the base techniques draw the picture exactly as `CAM-01` would and then apply
  light and text, so `view()` works and overlays on them are possible.
- Sizes are given as cap height in percent of the frame height so they hold at any output size; the renderer converts to the
  font size from the font's own metrics.
- Fonts: EB Garamond Regular, Italic and Medium (`.ttf`, with `OFL.txt`) in `style/gae/fonts/`, loaded through `vfx.font` by
  three new kinds; a missing file is an error with a clear message, never a silent fallback.
- Preview clips: today `*.mp4` is ignored by git and the old deploy sent the previews separately. The server now gets its code
  by `git pull`, so the preview clips must be tracked: un-ignore `style/gae/previews/*.mp4` and add the existing ones.

## 4b. The channel-name beat that also writes the video's title (`ID-BRAND-03`, added 2026-11-20)

The owner watched the first test video and asked for the channel-name beat to be held a little longer and to show the video's title too: "first the
light sweep will show our channel name and then it sweeps again to show the video title. And then you hold it a bit." Asked how the title should
appear, they chose: the channel name STAYS, the second sweep writes the title on a line BELOW it, and under the title a small line names the painting
and the painter. `ID-BRAND-01` and every storyboard that uses it are not touched; this is a new technique, `ID-BRAND-03`, next to it.

Nominal timeline (seconds from the start of the shot, defaults; a shot shorter than the nominal length scales every time, a longer one holds the end):

| from | for | what |
|---|---|---|
| 0 | `dim_s` 0.6 | the picture dims from 100 % to `floor` 0.12 |
| `sweep_delay_s` 0.5 | `sweep_s` 1.6 | the band crosses (left to right, 16 % wide, tilted 10 degrees); the name is written along its path (capitals, tracked +25 %, cap height 8 %, centred at 36 % of the height); behind the band the picture is at `wake` 0.26 |
| 2.1 | `name_hold_s` 2.4 | nothing moves except the camera's slow push; the name is fully written |
| 4.5 | `title_sweep_s` 1.6 | the band crosses a second time, same direction; the title (italic, as given, cap height 4.6 %, centred at 54 %) and under it the small line (capitals, tracked +14 %, cap height 2.2 %, centred at 62.5 %) are written along its path; the name stays and does not move; the picture is at `wake` before and behind this band (the band is the only light that moves) |
| 6.1 | `title_hold_s` 3.0 | everything is held until the shot ends (nominal length 9.1 s) |

Without a title and without a small line there is no second sweep: nominal length 4.5 s and the name sits at 42 % (`y_alone_pct`), as in `ID-BRAND-01`.
With one of the two lines, the second sweep writes that line at its own place. The two lines are never wider than 84 % of the frame: a longer one is
made smaller until it fits (one line, never wrapped; a title of 70 characters comes out at about three quarters of the size of a short one, a 57 px font instead of 76 px at 1080p, and still
reads on a phone). The title is kerned (pair adjustments read from the face's GPOS table; without them "Wa" in the italic face has a visible gap).
Params and defaults: the registry entry `ID-BRAND-03` in `style/gae/techniques.json`; code: `BrandTitle` in `bti/engine/techniques/identity.py`.

## 5. Style settings and the storyboard
- `style/gae/style.json` gets a block `identity`: `channel_name` "RAKING LIGHT", `default_style` "raking", and for each style
  the technique of each role (`open`, `label`, `brand`, `mark`) plus, for `dim`, the mark's entry transition (`TR-01`, 0.75 s).
- The storyboard gets an optional top-level field `identity: {"style": "raking" | "dim"}`. Absent means the old cards
  (`X-CARD-01`, `X-CARD-02`, `TXT-01`), which stay valid and drawable: old projects do not change until someone chooses.
- "Structure shots" are the shots with `intent: "structure"`: the title slot (today `X-CARD-02`) and the chapter cards
  (today `X-CARD-01` or `TXT-01`). The identity only ever touches structure shots and the opening overlays.

## 6. Applying a style (one deterministic function, no model)
`apply_identity(storyboard, style_id, style, timing, meta) -> (storyboard, report)`:
1. Opening: remove overlays of the `ID-OPEN-*` / `ID-LABEL-*` family from every shot; add the chosen style's opening overlay(s)
   to the shot that is on screen at the nominal start time, clamped to that shot (at least 3 s, else move the start earlier
   inside the same shot; if no shot can hold 3 s, skip and say so in the report). Title, artist and year come from the old
   title card's params when there is one, else from the project (`title`, `artist`, `year`).
2. Title slot: the first structure shot whose technique is `X-CARD-02` or `ID-BRAND-*` becomes the style's `brand` technique.
   Its picture is the picture of the shot before it, at that shot's last camera key, with a 3 % push over the beat.
3. Chapter cards: every structure shot whose technique is `X-CARD-01`, `TXT-01` or `ID-MARK-*` becomes the style's `mark`.
   Title: the old title without any leading number, in title case (small words `a an the of and in on to for at by` stay lower
   unless first), numbered in order: "5. The Mirror". Picture: the next non-structure shot's picture, with a camera that ends
   exactly on that shot's first camera key (start 4 % wider), so the mark flows into the chapter without a jump; when the next
   shot has no camera (a layout, a diagram), use the main picture, whole, with a 3 % push. Style `dim` sets the entry
   transition; style `raking` clears it (hard cut).
4. Keep each shot's `id`, `start`, `intent`, `note`, `locked`. A locked shot is not changed and is listed in the report.
   Changed shots get `source: "identity"`. Set `storyboard.identity.style`.
5. Applying the same style twice gives a byte-identical storyboard. Applying `raking`, then `dim`, then `raking` gives the same
   storyboard as applying `raking` once.
- The draft compiler (the program that places the cards in the silence the voice left) calls the same function at the end, with
  the project's chosen style or the default, so a new video gets its identity without any step by the owner or the agent.
- The check ("Kiểm tra") reports, as a warning, a structure shot whose technique does not belong to the chosen style.

## 7. Who chooses, and where
- **Owner**: step 5 has a selector "Kiểu mở đầu và mốc chương" with "Vệt sáng quét" and "Tối lại, hiện tên" (and the note
  "Kiểu cũ" while nothing was chosen). Choosing applies at once, the picture preview shows it, and the usual undo of a saved
  storyboard (history) takes it back. Step 6 shows which style the video will be exported with.
- **Agent**: `GET /api/projects/{pid}/identity` returns `{style, default, options: [{id, label}]}`;
  `PUT /api/projects/{pid}/identity {style, base_rev}` applies it under the same lock and revision rules as a storyboard save
  and returns `{rev, style, changed: [shot ids], skipped: [{shot, reason}]}` (409 on a stale `base_rev`, 422 on an unknown style).
  The agent guides (`skills/`, `docs/APP_GUIDE.md`) say that this route is how an agent picks the style, and that an agent
  never writes title cards or chapter cards by hand.
- Edit by instruction does not re-apply the identity (its undo rules stay as they are); the two briefings tell the model which
  techniques are the marks of the chosen style in case the owner asks for a new chapter mark.

## 8. Not in this build
- Treatments B (pool of light) and D (margin notes): not chosen.
- The detail label and the YouTube thumbnail: to be redesigned after this, from the same evidence.
- Changing the style from the instruction box ("đổi mốc chương sang kiểu tối lại"): later; the selector and the route cover it.
- The length of the silences the voice step leaves (today about 2.6 s for the title slot and 2.8 s for a chapter card, against
  nominal 5.0 / 4.0 s and 3.2 / 3.0 s): this build scales the timelines to what is there; making the silences longer for new
  videos is a separate, small change in the voice step that needs the owner's ear on a real video first.

## 9. Acceptance
- Engine: all seven techniques validate and draw (the registry sweep covers them); frames at fixed times match the mock-ups'
  logic (band position, brightness levels before, inside and behind the band, text revealed only behind the band, levels at
  the end); a shorter element scales; fonts load from the bundle on the Windows server.
- Applier: the five rules of section 6 as tests on the Arnolfini fixture; numbering and title case; locked shots; idempotence
  and the round trip; the mark's last camera key equals the next shot's first key.
- Route and page: the choice survives a reload; a stale revision is refused; the selector shows the current style; one browser
  check that picks each style on a copy of the sample project and looks at a frame of the opening, the beat and a mark.
- A real look: I render the opening, the channel-name beat and one mark of the Arnolfini sample in both styles on the server and
  compare them with the mock-ups before anything is called done.
