# R10 - Animated explanatory components for "Raking Light": the map first, then the rest

Date: 2026-11-18. Worker: `r10components`. Research only: no product code was written or changed.
Questions from the owner: (1) what does a modern, readable, attractive map moment look like in videos cut by people who are good at it, and what should ours become; (2) which other animated explanatory components (not maps) do such videos use, which would a painting video need, and which does our engine lack.

All contact sheets are in `.scratch/r10/sheets/` (full-frame crops in `.scratch/r10/frames/`). Downloaded segments are in `research_media/other/r10/`. Time codes are `m:ss` in the source video. Where a claim rests on 4 frames per second I say "4 fps"; where only on 1 fps or a coarse scan I say so. Hex values are the centre of 16-level colour bins read from H.264 frames (about plus or minus 8 per channel) unless marked "median".

---

## 0. One-page summary

### Question 1: the map

**What good map moments look like (15 moments, 6 makers, every one looked at at 4 fps; Part 2).**
- They last **4.0 to 15.5 seconds**; the reference channel's moments are shorter (median about 6.5 s; range 4.0 to 14.3 s), the other makers' longer (8 to 15.5 s).
- Every map of the reference channel (Great Art Explained, "GAE"; 7 of its 8 moments measured by phase correlation and ECC, the eighth static by eye) has a **static camera**: shift 0.0 px, scale 1.000 to 1.008 over 3 to 13 s. Five of the seven moments by other makers move the camera (M10, M11, M12 measured, a push of about 1.1 to 1.4 times over 5 to 13 s, one with a perspective tilt; M14, M15 by eye); one is static (M9) and one inconclusive (M13). So movement is not what makes GAE maps readable; **what makes them readable is real geography, contrast, and things appearing in step with the spoken words**.
- Every moment ties each marker or line to a spoken word: Sargent's 15 red dots land one every 0.87 s as 16 places are named (2:16 to 2:30, `cuHgxPe3J7I`); the dotted walk Bucharest to Paris draws in 5.3 s during "a legendary walk from Bucharest to Paris" (14:19.75 to 14:25, `ACnM_063tsw`); History on Maps drops three pins while the narrator says Luoyang, Lanzhou, Dunhuang.
- The base map is **real geography** in all 15 (antique atlas page, satellite photo, Google Maps screenshot, OpenStreetMap relief, game-engine terrain, flat vector). None is an invented shape.
- Contrast is high where it works: white label on dark satellite photo is about 9:1 (Starry Night, 11:47); our label on our grey is **1.8:1** and land against sea is **1.28:1**.
- Labels are 2.4 to 3.7 percent of the frame height (cap height), white or ink, **no box** in the best GAE moments (italic serif "View from room", "Constantinople", "Theology"), boxed in the two that look like stock explainers (Oslo, History on Maps).
- Markers and routes: a ring of 10 to 19 percent of the frame height with arrows (bearings), 1 percent dotted red route with an arrowhead drawn progressively over 3 to 7 s, a glowing white line on dark terrain, or 24 px dots (3.4 percent) dropped one by one.
- Depth and finish: only the tilted, relief-shaded OpenStreetMap map (Johnny Harris), the dark terrain with a glowing line (GAE Istanbul 7:34 to 7:40) and the colour-from-red relief fly-over (Historia Civilis) have tilt, shadow, vignette or light. Those three are the ones that look made by a modern studio.

**What ours is today (Part 1).** An invented grey blob map (seeded noise, no coastline, no country, no sea name), land against sea at 1.28:1, label contrast 1.8:1, label cap height 2.2 percent, both rings on screen from the first frame, no camera, no scale, places given as canvas pixels (not longitude and latitude), a 7 px route (0.65 percent) that draws between 1.5 s and 4.0 s. It reads as a placeholder, not a place.

**What it should become (Part 3).** One map component, driven by JSON (places with longitude and latitude, optional route, optional region, start and end view), over **bundled public-domain geography (Natural Earth, public domain, no credit needed)**, with three looks the owner can choose between, each built from the engine's existing 2D primitives:
- **A "Plate"**: warm paper, ink coastlines with water-lining, italic labels, dotted red-brown route with a travelling head, slow push; for history and anything before 1900.
- **B "Raking relief"**: dark shaded relief lit from the upper left at a grazing angle, a band of light that reveals the land, a glowing thin route, mild tilt; the channel's own raking-light idea on a map.
- **C "Cut paper"**: pale quiet land with a soft shadow on the sea, one accent colour for the region and route, a pulsing ring at each place, globe-to-region start; for modern places and quick use.

### Question 2: components beyond the map

I found **21 devices** that make one kind of fact visible, each seen in at least one real video, plus one proposed device (the pictogram comparison) that I did not see anywhere (Part 4). Against our registry of 78 techniques: **4 exist in usable form** (size ruler `AN-05`, year card `STATIC-09`, two-state compare `CMP-01`/`CMP-05`/`X-CMP-02`, perspective rays and grid `AN-03`/`AN-06`), **10 exist weaker** (the three maps, the ring with one arrow, infrared compare, paint cross-section, room plan, pigment key, name labels, quote over image, portrait tag), and **8 are missing**: region lit, the time axis with dates, the family or succession tree, the big number with its source line, the two-figure comparison, the pictogram comparison, size against a familiar object, and the chain of places or owners as picture and caption. (The document with one entry lit and the unboxed key of parts of a picture are in the "weaker" group.)

In the Arnolfini narration (91 sentences) the sentences each device could serve are counted in Part 4. The most frequent needs: labelled parts of a picture or room (about 14 sentences), places and journeys (10), dates and spans (7), comparison with another work (6), family and patron relations (6), material and technique (6), quantity and price (5).

**Build first (Part 5):** (1) the map component with three looks, (2) time axis with dates, (3) big number and two-figure comparison, (4) family or succession tree, (5) document with one line lit, (6) same picture in two states with a technique label (infrared, X-ray, before and after), (7) unboxed labels as a key to the parts of a picture, with portrait roundels as an option. Parameter lists are in Part 5.

---

## Part 1. Our maps today, judged against the screen

Sources: `style/gae/previews/STATIC-06.mp4`, `AN-04.mp4`, `X-ANN-05.mp4` (640x360, 30, 30 and 15 fps); sheets `ours_STATIC-06_0-5.5s.jpg`, `ours_AN-04_0-6s.jpg`, `ours_X-ANN-05_0-6s.jpg` (2 fps, looked at); registry entries in `style/gae/techniques.json`; one full-size frame measured (`frames/ours_static06_4.5.png`). The sample video uses `STATIC-06` once (shot `s0012`, at the word "Bruges", about 100 s).

| # | Trait, as a checkable fact | Value on screen | Where I checked |
|---|---|---|---|
| 1 | The land is an invented shape, not geography | grey blobs from `seed: 5` (registry note: "Procedural stand-in map (grey, seeded blobs)"); no coastline, no country, no mountain, no sea name | all three sheets |
| 2 | Places are canvas pixels, not coordinates | Bruges `[520, 330]`, Lucca `[1360, 790]` on a 1920x1080 canvas (27 percent, 31 percent and 71 percent, 73 percent); the registry type is `point`, unit "canvas px". An agent cannot give longitude and latitude | `STATIC-06` params |
| 3 | Two greys | land `#a4a8a8` (54 percent of pixels), sea `#909490` (26 percent); contrast 1.28:1; plus a faint grid | frame 4.5 s |
| 4 | Labels are small and pale | cap height 8 px of 360 = **2.2 percent** of the frame height; colour about `#dae0e0` on `#a4a8a8` = **1.8:1** contrast | frame 4.5 s |
| 5 | Both places are marked before they are named | both white rings (radius 22 px at 1080 = 2.0 percent) are on screen at 0.0 s; the BRUGES label appears at 0.5 s, LUCCA at about 1.5 s | `STATIC-06` sheet 0.0 to 1.5 s |
| 6 | Origin and destination look the same | same ring, same size, same label style | `STATIC-06`, `AN-04` |
| 7 | The route is thin and arbitrary | 7 px dotted red `#d02020` = **0.65 percent** of the height; a quadratic curve with a free "bend", not a path; draws from about 1.5 s to 4.0 s (`route_delay_s` 1.4, `route_draw_s` 2.4); contrast of red on land 2.2:1 | sheet and registry |
| 8 | No camera, no change of scale | only 2052 of 230,400 pixels (0.89 percent) differ between 0.2 s and 5.0 s of `STATIC-06`, all of them the route; no push, no wide-to-close move | pixel difference |
| 9 | No sense of where in the world | no wider map, no neighbouring countries, no distance, no scale bar; two or six labels only | all three |
| 10 | Everything is flat | no shadow, no vignette, no grain, no light, no tilt | all three |
| 11 | Three techniques each hold part of the job | `STATIC-06` (route, dots, base map), `AN-04` (ring, arrow, place label), `X-ANN-05` (six dots one by one, pulse 0.7 s, label per dot, then dissolve into the next picture at about 5.5 s); none takes a region to light, a start view and an end view | registry |
| 12 | The map is a "base" shot that replaces the painting | it cuts away from the painting for 5 s with no link to the previous picture (the sample's `s0012` is a whole shot) | storyboard |

Net reading: nothing on screen says "this is Flanders and Tuscany", the eye has nothing to compare, and the one coloured thing (the route) is thinner than the label.

---

## Part 2. Map moments in real videos

Method. For each moment: a contact sheet at 4 fps with burned-in time codes (`.scratch/r10/sheets/`), full-resolution frames for details (`.scratch/r10/frames/`), hex values by quantised dominant colours or median, camera by `cv2.phaseCorrelate` and `cv2.findTransformECC` between a frame near the start and one near the end (pure translation or scale measured; correlation noted when low). Narration: GAE from the ASR transcripts already in `research_media/great-art-explained/` (segment-level, not word-level); other makers from YouTube auto-captions (about plus or minus 1 s). The Oslo moment has no transcript.

### 2.1 The 15 moments (6 makers)

Makers: Great Art Explained (GAE, 8 moments), TED-Ed (2), Johnny Harris (1), Historia Civilis (1), Kings and Generals (1), History on Maps (2). With the further makers in Part 4 (Everything Explained, UsefulCharts, National Gallery, Getty, VICE News, Nerdwriter1, ACTUAL SIZE, Rijksmuseum) the study covers 14 makers.

| id | Maker, video, URL, time code | Length | Narration at that moment | Base map | Camera | What appears, in order | Label, marker, route | Start / end |
|---|---|---|---|---|---|---|---|---|
| M1 | GAE, *John Singer Sargent (Full Length)*, `youtube.com/watch?v=cuHgxPe3J7I`, 2:15.6 to 2:29.9 | 14.3 s | "They lived in Florence, Venice, Rome, Sorrento, Naples, Lake Como, Lucerne, St. Moritz, Munich, Berlin, Paris Biarritz Nice Madrid Seville and Cadiz" (2:16.08 to 2:36.56, ASR) | antique chromolithograph of Europe, washed out about 50 percent: `#e8e8d8`, `#f8f8e8`, pastel region tints; paper-like | **static** (shift 0.0 px, scale 1.001) | cut in; first dot at 2:16.5; 15 dots counted in the last frame, one every about 0.87 s, each as its place is named | red dot `#e81e0c` (median), about 24 px at 720p = 3.4 percent of the height; **no labels, no line** | hard cut in from an archive photo (2:15.5 to 2:15.75); hard cut out to a pencil sketch at 2:30 |
| M2 | GAE, Starry Night episode (file `crCPVoPsTtk.mp4`; title not in the 86 `.info.json` set), 11:42.5 to 11:50.0 | 7.5 s | "he places the village in the valley, even though it was not visible from Vincent's room or from his studio and was in fact in the opposite direction" (11:40.26 to 11:52.26) | real aerial photograph (Saint-Remy), `#384848`, `#283838`, `#485858`; warm roofs on the left | **static** (0.0 px, 1.000) | cut in with white ring and "ASYLUM" already there; the arrow to the right ("View from Studio") at about 11:45.25, then up ("View from room") and left ("St. Remy") by 11:46.0; held to 11:49.75 | ring about 140 px = **19 percent** of the height, white line about 3 px; arrows with 1 px heads; labels white serif italic, cap height about **2.5 percent**, "ASYLUM" bold italic caps; no box; label at each arrow end; contrast white on ground about 9.5:1 | hard cut in from the painting-and-drawing split (11:42.25 to 11:42.5); hard cut out to the painting at 11:50.0 |
| M3 | GAE, *Great Art Cities Explained: Paris*, `ACnM_063tsw`, 14:18.5 to 14:26.5 | 8 s | "After training in Bucharest ... Brancusi set off on a legendary walk from Bucharest to Paris and arrived the same year Picasso Modigliani and Chagall did 1904" (14:14.74 to 14:31.80) | right panel (about 62 percent of the width) = antique printed political map of Europe in greys `#c8c8c8`, `#989898`, `#e8e8e8` with its own printed labels; left panel = a photograph of the walker | **static** (0.3 px, 0.996) | map panel and photo arrive together at 14:18.5; red dotted route drawn from Bucharest (right) to Paris (left) between **14:19.75 and 14:25.0 (5.3 s)**; arrowhead at the end | route `#db221a` (median), dot about 7 px = 1.0 percent of the height, spacing about 12 px, follows a curve via Vienna, Munich and Basel, not a straight line; no labels of its own | hard cut in; out: a new photo strip slides in from the right at 14:26.0 to 14:26.75 and pushes the map out |
| M4 | GAE, *Venice Special (Biennale)*, `f8OIYzV5Npo`, 22:38.5 to 22:43.7 | 5.2 s | "it was like going first from the UK to Magera to unload with a crane all the four big sculptures" (22:38.60 to 22:48.28) | **Google Maps screenshot** of Europe: sea `#78a8f8` (31 percent), land `#a8d8b8`, `#98d8a8`, yellow roads, service labels in black bold sans | static (0.0 px, 1.000) | cut in; dashed red route drawn London to Venice between about 22:40.5 and 22:43.5 (3 s) | route `#db280a` (median), about 6 px = 0.9 percent, arrowhead at the end | hard cut in and out |
| M5 | same video, 22:57.75 to 23:02.5 | 4.8 s | "... on a huge pontoon boat and crane in front of the balustrade of the St. Regis" (22:56.04 to 23:02.20) | Google Maps screenshot of the Venice lagoon: sea `#88b8f8` (48 percent), land `#e8e8e8` (16 percent) | static (0.0 px, 1.000) | cut in; thin dashed red boat route drawn left to right 22:58.5 to about 23:02 | route `#d22221` (median), about 3 px = 0.4 percent, low contrast | hard cuts |
| M6 | GAE, *Great Art Cities: Istanbul*, `XKp6ahy2eBk`, about 7:34.4 to 7:40.0 | 5.6 s | "The water was transported to the city from up to 200 kilometers away by these immense Byzantine aqueducts" (7:36.34 to 7:41.68) | **dark tilted terrain**, near black `#181818` (49 percent) and `#080808` (12 percent), warm green-brown hills `#282818`, `#383828`; looks like a satellite fly-over, darkened | static (0.0 px, scale 1.008) | line already drawn at the cut; ring and label appear at about 7:36.0 (1.6 s later) | route: white line about 3 px with soft glow, the whole 200 km path; ring about 113 px = **15.7 percent** of the height; label "Constantinople" bold italic serif white, cap height about **2.6 percent**, left of the ring; no box | hard cut in from the aqueduct drawing (7:34); out: cut to a flag photograph at 7:40 |
| M7 | GAE, *The Scream*, `d50FbuyswAU`, 15:21.0 to 15:25.0 | 4.0 s | no transcript for this video (unknown) | greyscale satellite (Google Maps with colour removed): `#282828`, `#383838`, `#686868`, `#787878`; service labels visible | static (0.0 px, 1.001) | ring arc starts 15:21.5, full ring by 15:22.0; two lime-yellow lines drawn from the ring outward between about 15:22.25 and 15:23.5 (sight lines) | ring about 70 to 95 px = 10 to 13 percent of the height, yellow-green; lines `#f5f761` (median), about 4 px = 0.6 percent; label "OSLO" white bold caps (cap about **3.7 percent**) **on a black rectangle** | hard cut from a watercolour at 15:21.0; hard cut to hill-road footage at 15:25.0 |
| M8 | GAE, *Pollock Part One*, `0sQ_cfZ8q9k`, 17:20.7 to 17:28.9 | 8.2 s | "The WPA was a government program created in 1935 as part of President Franklin D Roosevelt New Deal ..." (17:18.12 to 17:36.32) | **archival** black-and-white graphic of the United States with state borders (not made by the channel) | static | map is shown 17:20.75 to 17:22.75, then period crowd footage fades in inside the country shape (17:22.75 to 17:23.5) and stays | no labels, no markers | hard cut in; out: hard cut to a mural photograph at 17:29 |
| M9 | TED-Ed, *The Silk Road: Connecting the ancient world through trade*, `vn3e37VWc0k`, 0:36.75 to 0:47.75 | 11 s | "The Silk Road wasn't actually a single road, but a network of multiple routes that gradually emerged over centuries, connecting ... thread by thread" (0:36.52 to 0:45.93) | illustrated flat map: land `#98e898` (40 percent), desert `#e8d878` (33 percent), sea `#98b8d8` (12 percent) | static (shift 0.0, scale 1.005) | globe scene wiped by a red band rising from the bottom (0:36.75 to 0:37.75); one route line grows 0:37.75 to 0:39.5; branches added one by one to 0:46.75 | route `#ac331e` (median), about 1 percent of the height; no labels | wipe in; cut out to a desert scene at 0:47.75 |
| M10 | TED-Ed, same, 1:29.25 to 1:44.75 | 15.5 s | "Stretching nearly 2,000 miles from the Tigris River to the Aegean Sea, its regular relay points allowed goods and messages to travel ..." (1:36.99 to 1:43.94) | same style, paler `#a8e8a8` ground, region names in small grey serif ("Persia", "Anatolia", "Arabia") | **moves** (ECC scale 1.12, shift 49 px of 320; correlation 0.42, so rough) | map fades in over about 1.0 s; a character (Darius) stands at the left from 1:33; the route is drawn from about 1:37.5 to 1:44.25 (**about 7 s**); "Sardis", "Nineveh", "Susa" appear along it | route `#a83828`, about 1.3 percent; small serif labels about 1.5 percent | fade in; the route is still drawing when the shot ends |
| M11 | Johnny Harris, *The 3 Strangest Borders on Earth*, `Fp2PcrRNlGo`, 1:35.5 to 1:50.5 | 15 s | "The line is dashed because Morocco doesn't want all of this to be a country ... since 1975 when Spain left this land, Morocco has been fighting to keep the people down here from controlling the land" (1:34.19 to 1:50.29) | **tilted (perspective) OpenStreetMap relief map**: land `#f8f8f8` (42 percent), sea `#b8c8c8` (24 percent), faint terrain; credit "(c) OpenStreetMap contributors" bottom left, about 2 percent of the height | **moves**: push and tilt (ECC scale about 1.35 over 13 s; correlation 0.61) | the claimed region rises as a flat dark navy `#082838` polygon at 1:36.75 to 1:37.0; Morocco as a red disc with a flag and a yellow band reading "MOROCCO" (about 12 percent of the frame height); a small Spain flag disc flies in 1:43.0 to 1:46.0 and out 1:46 to 1:50 | region fill, flag discs; no leader lines | cut in from a drone shot; the segment continues to a studio shot at 1:51 |
| M12 | Historia Civilis, *The Battle of the Teutoburg Forest (9 C.E.)*, `kmF3VBA_RcM`, 0:00 to 0:11, and 0:14 to 0:22 | 11 s + 8 s | "It's September of year 9. Augustus rules in Rome ... And far to the north, Publius Quinctilius Varus is on the other side of the Rhine with three legions" (0:00.98 to 0:12.35) | shaded-relief physical map (sea `#b8e8f8` 52 percent, mountain browns `#785858`); the Roman world tinted translucent red; opens from deep red `#6e0f0f` and fades into the map in about 1.2 s | **moves** continuously: Alps to Germania over about 8 s (scale 1.24 over 5 s in the second part, correlation 0.84) | territory tint, then at 0:08.5 a **flat red rectangle** (a legion) lands on "Germani"; at 0:20.5 a pale disc grows round it | label "Germani" in tracked translucent serif italic, about 3 percent; marker is a rectangle about 8 percent of the width | fade from red; hard cut to a title card at 0:11 |
| M13 | Kings and Generals, *Scipio's Masterpiece - Zama 202 BC*, `qeAcgE3Msto`, 1:33.25 to 1:43.4 and 2:07.25 to 2:29 | 10 s and 22 s | "By early summer 203 BC, all hope had been lost for the Barca brothers in Italy" (2:07.28) | strategy-game engine map (sea `#486888` 23 percent, magenta and purple polity fills, relief land) | slow drift (low correlation, 0.25 to 0.53; I cannot give a number) | unit stack icons and banners; city names in small caps about 1.5 percent | no route lines drawn by the editor in these frames | cut in; at 2:06 the segment fades up from black |
| M14 | History on Maps, *History of Silk Road*, `aGG0kgVqhWY`, 0:30.5 to 0:44.5 | 14 s | "starting at the old capital cities of Luoyang and Xi'an, the silk road routes cross the yellow river at Lanzhou, then follow the Gansu corridor ... into Xinjiang at Dunhuang the route split three ways" (0:28.72 to 0:51.44) | flat vector, white land `#f8f8f8` / blue sea `#0878b8` (elsewhere) | **moves** (pan and zoom by eye; automatic measure failed) | pins drop at Luoyang (about 0:31.5), Lanzhou (0:33 to 0:34) and Dunhuang (0:35.5), about 0.7 s apart; a brown route line is drawn through them 0:33.5 to 0:36.5; **Xinjiang fills pale yellow `#f9e283` from the left, 0:36.25 to 0:40**; label "Xinjiang" in tracked italic at 0:40.5; three branches and "TAKLAMAKAN" 0:42 to 0:45 | red teardrop pins with a white hole, labels about 2 percent | cut; after 0:57 a 3D book appears as a bridge |
| M15 | History on Maps, same, 1:19 to 1:27 | 8 s | "Darius the First built the two thousand mile Persian royal road ... only one tenth the amount of time of a single traveler" (1:11.20 to 1:26.08) | flat vector, land `#f9e283`, sea `#0878b8` | moves (zoom and pan; ECC value 1.95 is not reliable) | date chip "330 BC" top centre; portrait on a **pin** (a circle with a painting of a rider, about 21 percent of the height) with a red serif heading "Royal Road"; dashed black route; "Sardis" label; callout "Normal person: about 90 days / Royal messenger: about 9 days" slides up at about 1:21.0 | chip: blue pill `#2666a2`, white bold sans, cap about 4.5 percent; callout: peach box `#f4c583` with a brown tab, two lines about 4 percent; route about 1.2 percent | cuts |

### 2.2 What the good ones have in common, with the numbers

| Property | Reference channel (M1 to M8) | Other makers (M9 to M15) | Ours today |
|---|---|---|---|
| Length | 4.0 to 14.3 s (median about 6.5) | 8 to 15.5 s | 5.0 s (preview) |
| Camera | **static in 7 of 7 measured** (the eighth, M8, static by eye) | moves in 5 of 7 (M10, M11, M12 measured, scale 1.1 to 1.4 over 5 to 13 s, one tilted; M14, M15 by eye); M9 static; M13 inconclusive | static |
| Base map | real: atlas page, satellite photo, Google Maps | real: OSM relief, game terrain, flat vector, illustration | invented blobs |
| Contrast, text over ground | about 9:1 (white on dark photo); ink on paper | high (white on blue, black on white) | label 1.8:1, land to sea 1.28:1 |
| Label cap height | 2.4 to 3.7 percent (serif italic 2.5 to 2.6) | 1.5 to 4.5 percent | 2.2 percent |
| Marker | 3.4 percent dot (M1); 10 to 19 percent ring (M2, M6, M7) | pins, flag discs, rectangle, 12 to 21 percent | 2.0 percent ring, same for all |
| Route | 0.9 to 1.0 percent dotted red with arrowhead (M3, M4); thin glowing white (M6); lime line (M7) | 1.0 to 1.3 percent, drawn 3 to 7 s | 0.65 percent dotted, 2.4 s |
| Sync to words | dots per place name (M1); route during "walk from Bucharest to Paris" (M3) | pins per place name (M14), route per sentence (M10) | none: a fixed delay |
| Region lit | none | M11, M14 (fill, extrusion) | none |
| Depth and finish | M6 only (dark terrain, glow) | M11 (tilt, relief), M12 (relief, colour from red) | none |
| In and out | hard cuts at both ends (M1, M2, M4 to M8); one slide-out (M3) | wipe, fade, cut | hard start, dissolve out (X-ANN-05) |

What separates the good ones from Part 1, in order of effect: (1) the ground is a real place a viewer can recognise at a glance; (2) text and marks have 5:1 or more against the ground; (3) things appear when the word is spoken; (4) there is a wider context to place the marks in (Europe around Bruges, an aerial photo around the asylum); (5) a start-to-end change of scale only in the better-funded makers, and not needed to be readable.

**Reading for the owner's two aims.** "More modern, easier to view, attractive": the three moments that look modern are M6 (dark terrain, glow), M11 (tilted relief with extruded region) and M12 (relief colour from red). All three are dark or high-contrast, use light and depth, and keep type small. "Reuse for other videos": all the GAE maps are screenshots of existing map services, so GAE does not reuse a component; it pastes a picture. Our advantage can be one data-driven component.

Identity check: History on Maps' pill, boxed callout and pin-with-portrait (M15) and Oslo's black box (M7) conflict with "nothing boxed"; they are shown to describe what exists, not to copy.

---

## Part 3. Three ways our map could look

### 3.1 Bundled geography (no network at render time)

| Data | What it gives | Licence (page where I read it) | Size | Use |
|---|---|---|---|---|
| **Natural Earth** vectors: land, coastline, ocean, lakes, rivers (1:50m and 1:10m), admin-0 countries, admin-1 provinces, populated places, ports | the whole basemap | "All versions of Natural Earth raster + vector map data ... are in the public domain." "Crediting the authors is unnecessary." Commercial use invited. `naturalearthdata.com/about/terms-of-use/` | 1:50m physical bundle 7.25 MB; 1:10m coastline 2.93 MB, land 3.12 MB, rivers 1.98 MB, lakes 2.24 MB, bathymetry 14.86 MB; admin-0 countries 4.7 MB, admin-1 14.22 MB, populated places 2.68 MB (1:10m pages, read 2026-11-18) | A, B, C |
| **Natural Earth II raster** (shaded relief and water) | relief for B | same public-domain terms | 1:50m "small" 84.78 MB; 1:10m 184.76 MB (medium) or 309.77 MB (large) | B; bake to a smaller Mercator JPEG at build time (size and sharpness untested) |
| **GEBCO 2024 grid** (elevation and bathymetry, 15 arc-seconds) | own hillshade at city scale | "placed in the public domain ... free of charge"; credit the source; not for navigation. `gebco.net/data-products-gridded-bathymetry-data/gebco2024-grid` | 7.5 GB global | only as an offline source for baked relief tiles; never bundled whole |
| **GeoNames** | place name to coordinates lookup for the agent, at authoring time | "cc-by licence"; "give credit to GeoNames" (page does not name the version). `geonames.org/export/` | `allCountries.zip` and country files | not bundled; credit if used |
| **AWMC geodata** (Ancient World Mapping Center): ancient coastlines, rivers, roads | pre-medieval Mediterranean | repository README: ODbL 1.0 (share-alike on the database, attribution). `github.com/AWMC/geodata`; I did not open `LICENSE.txt` | not checked | optional, only if the owner wants antiquity with ancient shores |
| Historical borders | borders of 1434 Burgundy | **not found with a licence I read**; the agent should supply a region polygon itself (GeoJSON) | | |
| OpenStreetMap tiles | the look of M11 | ODbL plus tile-usage terms; **not re-read this session**; do not bundle tiles; M11 shows a credit line in the corner | | avoid |

Rule I would set: bundle only Natural Earth (public domain) in the repository; everything else is optional and each needs its credit line printed in the end credit if used.

### 3.2 The data an agent supplies (all three treatments)

```json
{
  "look": "plate | relief | cutpaper",
  "places": [
    {"id": "bruges", "name": "Bruges", "lon": 3.2247, "lat": 51.2093, "at_s": 1.0, "label_side": "auto"},
    {"id": "lucca",  "name": "Lucca",  "lon": 10.5027, "lat": 43.8429, "at_s": 2.3, "label_side": "auto"}
  ],
  "route": {"from": "bruges", "to": "lucca", "via": [[5.5, 48.8], [7.6, 46.0]],
            "shape": "curve | great_circle | straight | path", "start_s": 2.6, "draw_s": 3.0, "head": "dot | arrow | none"},
  "region": {"iso": ["BE"], "polygon": null, "at_s": 0.6, "fill_s": 1.0},
  "view_start": {"center": [6.86, 47.66], "width_km": 3800},
  "view_end":   {"fit": ["bruges", "lucca"], "margin_pct": 19},
  "duration_s": 8.0,
  "era": "modern | historic",
  "credit": "optional string for the end credit"
}
```

Worked numbers for the Arnolfini sample (Bruges 51.2093 N 3.2247 E; Lucca 43.8429 N 10.5027 E; great-circle distance 984 km; Web Mercator; frame 1920x1080): the end view that keeps both places inside the middle 62 percent is **2,357 km wide**, centre 6.86 E 47.66 N, **1.23 km per pixel**; Bruges sits at **38.4 percent, 19.0 percent** and Lucca at **61.6 percent, 81.0 percent** of the frame. At the start view (3,800 km wide, same centre) they sit at 42.8 percent, 30.8 percent and 57.2 percent, 69.2 percent.

Where "at_s" is given as a word anchor the storyboard already supports (`{"w": ..., "off": ..., "text": "Bruges"}`), the dot for each place lands on its word, which is the one habit all good moments share.

### 3.3 Treatment A "Plate" (atlas page)

Evidence behind it: M1 and M3 (antique atlas pages), M10 (labels in small serif). Fits the identity: EB Garamond, no box, text fades only, small type.

Look (hex): paper ground and land `#EFE6D2`; sea `#DDD4BE` (1.2:1 against land on purpose, the ink does the work); ink `#3B2F26`; accent route and region `#8C2F23`. Coastline hairline 1.5 px at 1080 in ink at 85 percent; **water-lining** (the classic atlas device) as two more offset coastlines in the sea, 6 px and 12 px out, ink at 25 percent and 12 percent; graticule every 5 degrees at 8 percent; paper grain 3 percent, corner vignette 14 percent. Place names EB Garamond italic, cap height 2.4 percent, ink; region and sea names small capitals, cap 2.0 percent, tracking +25 percent, ink at 70 percent. Place mark: filled dot 0.45 percent of the height in `#8C2F23` inside a ring 1.1 percent in ink. Route: dotted `#8C2F23`, dot radius 0.28 percent, spacing 1.4 percent, with a travelling head (dot 0.7 percent plus soft glow); no arrowhead. Region: multiply tint `#8C2F23` at 18 percent plus an inner ink outline 2 px.

Second by second, 8 s, Bruges to Lucca (hard cut in; a 0.5 s dissolve is a parameter):

| t | On screen |
|---|---|
| 0.0 | cut to the wide plate (3,800 km): Western Europe and the Mediterranean, nothing marked; the camera already moves, slow ease-in-out push toward the midpoint |
| 0.6 to 1.6 | region (Belgium, `BE`) tints over 1.0 s |
| 1.0 | BRUGES: dot and ring fade in over 0.3 s at about (42.8 percent, 30.8 percent) (it drifts to 38.4 percent, 19.0 percent by the end); italic label fades in at 1.2 s, above and right, offset 1.6 percent |
| 2.3 | LUCCA, same, label below and right |
| 2.6 to 5.6 | dotted route drawn from Bruges to Lucca along `via` points (curve of about 12 percent of the chord), head travels with it; dots are anchored in map space so they scale with the push |
| 5.6 to 7.0 | hold; end view reached at 6.0 s (2,357 km wide) |
| 7.0 to 8.0 | everything fades together to the next picture (0.5 s dissolve), or a hard cut |

Parameters: `places`, `route`, `region`, `view_start`, `view_end`, `ink`, `paper`, `sea`, `accent`, `waterline` (0 to 3 lines), `graticule_deg`, `grain`, `vignette`, `label_cap_pct`, `dot_spacing_pct`, `push_ease`, `in` (cut or dissolve).

Hard to build: (1) water-lining needs a distance transform of the sea mask at the current zoom each frame (cache by zoom level); (2) label placement (8 candidate positions, reject those that touch the route or another label); (3) the paper texture must not crawl when the camera moves, so pin it to the screen, not to the map (decision for the owner: pinned grain looks like a lens, map-pinned grain looks like a print); (4) the identity says text never scales: labels keep a fixed pixel size and only their position follows the push; if the owner counts that as sliding, hold the camera still while labels are visible.

### 3.4 Treatment B "Raking relief" (dark relief and a band of light)

Evidence behind it: M6 (dark terrain, glowing line, ring and italic label), M2 (white label on a dark photograph), M11 (tilt, relief), and the channel's own `ID-OPEN-01` band.

Look (hex): sea `#0C1116`; land base `#2A2B27` multiplied by the desaturated Natural Earth II relief (light from the upper left, azimuth 315 degrees, so the map is lit at a grazing angle like a painting under raking light); coastline hairline `#8A8F94` at 55 percent; no graticule; labels EB Garamond italic `#E9E2D0`, cap 2.4 percent, soft shadow 4 px at 50 percent; route `#F2D9A6` 2.5 px with a glow (blur radius 6 px, 35 percent, additive); ring 1.2 percent `#E9E2D0`; vignette 35 percent; grain 2 percent; optional tilt: perspective warp, pitch 18 degrees, top edge foreshortened 12 percent (parameter `tilt_deg`, 0 allowed).

| t | On screen |
|---|---|
| 0.0 to 0.4 | cut to the dark plate at 8 percent brightness, wide view |
| 0.2 to 2.6 | a soft band (14 percent of the width, edge tilted 10 degrees, same curve as `ID-OPEN-01`) travels left to right; behind it the land stays at 55 percent, ahead at 8 percent |
| 1.0 | BRUGES: ring fades in (0.3 s); label fades in 0.3 s later, no slide |
| 2.3 | LUCCA, same |
| 2.6 to 5.6 | glowing route drawn from Bruges to Lucca (3.0 s), head as a small spark; the camera pushes 1.0 to 1.55 times and the tilt eases from 0 to 18 degrees |
| 5.6 to 7.2 | hold; relief gently brightens behind the route (55 percent to 70 percent over 1.6 s) |
| 7.2 to 8.0 | brightness to 100 percent while the whole map fades to the next picture |

Parameters: `places`, `route`, `region` (region lit by raising the relief brightness inside the polygon to 100 percent), `sun_azimuth_deg`, `floor`, `wake`, `band_width_pct`, `band_s`, `tilt_deg`, `glow_px`, `glow_pct`, `vignette`, `grain`.

Hard to build: (1) relief at city scale: the 1:50m raster goes soft beyond about 1,000 km wide; for closer views fall back to vector only (flat dark land) or use baked GEBCO tiles; (2) the tilt is a `cv2.warpPerspective` of the finished frame (cheap) but labels must be drawn after the warp to stay upright and constant in size; (3) the band must be one function shared with `ID-OPEN-01` so the two never drift apart (it is the same light); (4) glow in float needs the frame at full size; time per frame untested.

### 3.5 Treatment C "Cut paper" (quiet, modern)

Evidence behind it: M14 and M15 (flat vector, region fill, pins), M9 and M10 (flat illustration), M11 (region lit against neighbours). Strips out the boxes, the pill and the portraits.

Look (hex): sea `#DCE6EA`; land `#F6F4EE` with a soft shadow cast on the sea (offset 6 px down-right, blur 10 px, black at 12 percent) so the land looks like cut paper; borders `#C9C5BA` 0.8 px; accent (region and route) `#C2452F`; ink `#2B2B2B`. Labels EB Garamond regular (not italic), cap 2.4 percent, ink at 85 percent, offset 1.6 percent from the dot. Place mark: dot 0.5 percent `#C2452F`, plus a **ring that pulses** (0.5 to 2.4 percent of the height over 1.2 s, opacity 70 to 0 percent, once, at the time of the word). Region: fill `#C2452F` at 16 percent plus outline 2 px at 80 percent; neighbours stay as they are. Route: solid 0.9 percent line `#C2452F` with a rounded cap, drawn with a head; arrowhead optional.

| t | On screen |
|---|---|
| 0.0 to 1.2 | orthographic globe, diameter 78 percent of the height, sea `#DCE6EA`, land `#F6F4EE`, soft shadow below the globe; Europe turns to the centre |
| 1.2 to 2.0 | globe and flat map are crossfaded (0.8 s) at matching centre and scale; the shadow of the sphere becomes the shadow of the land |
| 1.4 | Belgium fills with `#C2452F` at 16 percent over 1.0 s |
| 1.6 | BRUGES: dot, pulse, label (fade 0.3 s) |
| 2.8 | LUCCA, same |
| 3.2 to 6.2 | route draws Bruges to Lucca (3.0 s); the camera is still (no push) so labels do not move |
| 6.2 to 7.5 | hold |
| 7.5 to 8.0 | fade to the next picture |

Parameters: `places`, `route`, `region`, `globe` (true or false, with `globe_s`), `accent`, `land`, `sea`, `shadow_px`, `shadow_pct`, `pulse` (true or false), `pulse_s`, `border_px`, `label_cap_pct`.

Hard to build: (1) the globe is a per-pixel inverse orthographic map from the equirectangular land mask (`cv2.remap`, about one full-frame remap per frame, cost untested) and the handover to Mercator is a crossfade, not a true projection morph; (2) the soft shadow of every land polygon is a blur of the land mask (cache per zoom level); (3) `region` needs a polygon source: modern countries come from Natural Earth admin-0; a historic region (Burgundy 1430) must be supplied by the agent as GeoJSON.

### 3.6 Which treatment for which video

A for anything before 1900 and for most paintings (the paper look matches the book illustrations the owner's sources use); B for journeys, voyages and moments of drama (the Istanbul moment shows the effect); C for modern places and for quick use on short shots. A and B share the same engine code for projection, polygons, labels and route; C adds the globe and the shadow. The component should be one technique with `look` as a parameter (so `STATIC-06`, `AN-04` and `X-ANN-05` become presets of it).

---

## Part 4. Beyond maps: components that make one point visible

Evidence status for each candidate: "frames" means I looked at extracted frames; "1 fps" or "4 fps" is the sheet density. Time codes are in the source video. URLs are `https://www.youtube.com/watch?v=ID`.

### 4.1 The candidates (21 seen, 1 proposed)

| id | Device | Kind of fact | Seen in (channel, video, time, sheet) | Ours today | Engine could draw | Arnolfini sentences it could serve |
|---|---|---|---|---|---|---|
| C1 | Route drawn on a map | a journey, a trade link | GAE Paris `ACnM_063tsw` 14:19.75 to 14:25; GAE Venice `f8OIYzV5Npo` 22:40.5 to 22:43.5; TED-Ed `vn3e37VWc0k` 1:37.5 to 1:44.25 (Part 2 sheets, 4 fps) | `STATIC-06`, `AN-04`: weaker (invented map, canvas pixels) | yes, with bundled Natural Earth | 010, 011, 012, 039, 040 (5) |
| C2 | Places marked one by one | a list of places | GAE Sargent `cuHgxPe3J7I` 2:16 to 2:30; History on Maps `aGG0kgVqhWY` 0:31 to 0:36 (4 fps) | `X-ANN-05`: weaker (no real map, no word sync) | yes | 011, 015, 059, 083 (4) |
| C3 | Place with bearings (ring and arrows with labels) | where a view was taken from, what lies in which direction | GAE Starry `crCPVoPsTtk` 11:42.5 to 11:50; GAE Scream `d50FbuyswAU` 15:21 to 15:25 (4 fps) | `AN-04` has a ring and one arrow: weaker | yes | 062, 065 (2) |
| C4 | Region lit | a territory, a domain | Johnny Harris `Fp2PcrRNlGo` 1:36.75; History on Maps 0:36.25 to 0:40 (4 fps) | lacks | yes (polygon fill) | 010, 012, 083 (3) |
| C5 | Time axis with dates | when, in what order | Everything Explained, *Every ART MOVEMENT Explained*, `hXBvN475dwo` 0:00 to 0:03, 0:24 to 0:26, 1:04 (1 fps, full frames) ; UsefulCharts `xAQfOAm0gN8` 0:32 to 0:37 (1 fps) | lacks (`STATIC-09` shows one year only) | yes | 003, 010, 015, 018, 020, 055, 084 (7) |
| C6 | Date on the picture | the year of one event | Nerdwriter1 *Death of Socrates* `rKhfFBbVtFg` 0:16.5 to 0:22 "1787" over "NEOCLASSICAL" (2 fps); History on Maps chip "330 BC" 1:19 to 1:27 | `STATIC-09`: have | yes | 003, 005, 018, 020 (4) |
| C7 | Size marked on the work (outline and numbers) | height and width | GAE Arnolfini `T15Kv6dtYO0` 2:53 to 2:58: white rectangle round the painting in a gallery shot, "60cm" above, "82cm" at the left, caption "OIL PAINTING ON OAK PANEL" (1 fps, full frame) | `AN-05`: have | yes | 004 (1) |
| C8 | Size against a known object | how big is it really | ACTUAL SIZE, *The Mona Lisa Is Shockingly Small*, `58oCpcnOLpE` 0:08 to 0:25: tape measure over the real work, spoken "Smaller than a carry-on suitcase" (1 fps). Footage, not a graphic | lacks (a graphic version was not seen) | yes (silhouette scaled to the work), needs a silhouette asset | 004 (1) |
| C9 | Big number with its source | a price, a record | VICE News, *What Made The Da Vinci Painting Worth $450 Million*, `IQF6QFEY4Ps` 0:41 to 0:45: "$450.3M" in outlined numerals about a third (33 percent) of the frame height over street footage, "Source: Christie's" small bottom left (4 fps). **Static, no count-up** | lacks | yes | 036, 040, 035, 068 (4) |
| C10 | Same picture in two states (cross-dissolve) | before and after, colour reconstruction | GAE Istanbul `XKp6ahy2eBk` 4:57 to 5:03 (statue white to colour over about 3 s) and 5:12 to 5:19 (relief, about 6 s) (1 fps) | `CMP-01`, `CMP-05`, `X-CMP-02`: have | yes | 081, 082 (2) |
| C11 | Hidden layer revealed with a technique label | what lies under the paint | National Gallery, *See Jan van Eyck's original drawings beneath 'The Arnolfini Portrait'*, `GsjKKvbVsOs` 0:38.5 to 0:41.5, 0:49 to 0:50, 0:55 and 1:33 to 1:35: infrared and colour of the Arnolfini Portrait itself swap by cross-dissolve of 0.5 to 1.0 s (4 fps); GAE Bosch Part 2 `IYFtwTo50Gg` 0:55.5 to 1:04: "INFRARED SCAN" caption bottom centre (1 fps) | `CMP-02` partial (blur stages, not a real scan) | yes (two images and a caption) | 082 (1) |
| C12 | Paint cross-section with light rays | how oil layers work | GAE Mona Lisa `ElWG0_kjy_Y` 8:10 to 8:39: macro photograph of strata, gold V-shaped rays bounce off a white ground, labelled strata (1 fps, full frame) | `DIA-03` partial | partly: needs a photographic strip and rays | 081, 082 (2) |
| C13 | Plan of a room with a lit spot or a mark | where things are | GAE Last Supper `eKyYPSpiC9g` 8:22 to 8:29: floor plan with a soft spot of light moving across it; GAE Bernini `H8fGd3fCJbg` 23:01 to 23:11: black-and-white plan, a red arc drawn in one room (1 fps, full frames) | `DIA-06` partial | yes, needs the plan as an image | 047, 049, 051, 065 (4) |
| C14 | Composition geometry on the painting | how the picture is built | GAE Guernica `qJLH7JAsBHA` 6:40 to 6:48: red triangle, green zones, blue axis, numbered widths 1, 2, 3 (1 fps, full frame) | `AN-03`, `AN-06`: have | yes | 062, 069, 079 (3) |
| C15 | Pigment key on the painted palette | which materials | GAE Las Meninas `YFI6cQF1ros` 16:03 to 16:12: names "Brown Ochre, Charcoal Black, Bone Black, Umber, Yellow Ochre, Red Ochre, Azurite, Calcite, Vermilion" in white serif on the painted palette, no leader lines (1 fps, full frame) | `CMP-04`, `FOOT-01` partial | yes | 035, 037, 039 (3) |
| C16 | Unboxed labels as a key to parts of a picture | what each part is | GAE Vienna `MAF9LURl7bs` 5:00 to 5:11: "Theology", "Jurisprudence", "Medicine", "Philosophy" in white serif italic on the four ceiling panels, no box, no line (1 fps, full frame) | `STATIC-08`, `X-ANN-03`: partial (labels sit over heads) | yes | 005, 027, 042, 047 to 060, 065 to 069 (about 14) |
| C17 | Family or succession tree | who is related to whom, who followed whom | UsefulCharts *Medici Family Tree* `xAQfOAm0gN8` 0:47 to 1:30: cream ground, salmon boxes each with a portrait, name and dates, orthogonal connectors, branch names in small capitals, a shield at the root; the camera moves over the chart (1 fps, full frames) | lacks | yes (boxes and lines), needs portrait assets | 012, 018, 020, 022 (4) |
| C18 | Document with one entry lit | what the record says | Getty, *What is art provenance?*, `J9yP1N0nLUg` 2:52 to 3:26: a ledger page, a blue rectangle moves from entry to entry (4 fps, full frame at 3:00); Nerdwriter1 `rKhfFBbVtFg` 0:54 to 1:05: a page and a quote strip over the painting (2 fps); GAE Van Gogh `lAjVuUB9AkI` 6:32 to 6:41: letter pages (1 fps) | `STATIC-04` partial (quote over image) | yes: document image, dim, a lit window | 005, 018, 090 (3) |
| C19 | Chain of places or owners as picture and caption | where a work went | Getty `J9yP1N0nLUg` 3:28 to 3:41: white card, two photographs with captions "Gerome's studio, Paris" and "Knoedler & Co, New York City" (1 fps, full frame) | lacks | yes | none in the Arnolfini script (0) |
| C20 | Portrait roundel with name | a person | History on Maps 1:19 to 1:27 (round portrait on a pin, "Royal Road" heading); UsefulCharts nodes (portrait, name, dates) (1 fps) | `STATIC-05` partial | yes | 014, 018, 030, 066, 084 (5) |
| C21 | Two-figure comparison callout | a ratio | History on Maps 1:21 to 1:27: "Normal person: about 90 days / Royal messenger: about 9 days" in a peach box (4 fps, full frame) | lacks | yes | 036 (600 against 2,000 pelts) (1) |
| C22 | Pictogram comparison of quantities (**proposed, not seen**) | 600 against 2,000 pelts, a hundred martens | no real example found in the videos I looked at | lacks | yes | 036, 040 (2) |

Other devices I confirmed exist in the reference channel but did not measure again: detail lifted beside the source (`LAY-04`, `TR-04`), spotlight (`HI-01`), year card (`STATIC-09`). Rijksmuseum's *How We Are Removing Varnish From The Night Watch* (`S-2tIXR0Sb4`, 0:40 to 1:40, 1 fps) is footage only, with no before-and-after graphic and no slider; a draggable-wipe before-and-after was **not seen**.

### 4.2 Detail for the devices that matter most

**C5 Time axis (Everything Explained `hXBvN475dwo`, 0:00 to 1:15).** A horizontal black line with black dots at centuries (14th, 15th, 16th, ..., "Now"), thin vertical stalks up or down to circular thumbnails (about 10 percent of the frame height) each with its name in small black caps (cap about 1.5 percent) on a near-white ground. It is shown three times at 0:00 to 0:01, 0:24 to 0:26 and 1:04; at 1:04 the view is panned along the axis. Data: a list of `{date, label, image}`, an axis range, a focus date. Second by second (from the frames): 0 s axis ticks appear; 0.3 s first thumbnail grows on its stalk; each later item arrives about 0.5 to 1.0 s after the previous; after the last item a slow pan along the axis. A 3D variant (UsefulCharts 0:32 to 0:37): a poster of coloured vertical bars (one per empire) with the period names at the left, shown tilted on a table.

**C17 Tree (UsefulCharts `xAQfOAm0gN8`, 0:47 to 1:30).** Cream ground `#EDE5D5` (by eye), salmon boxes `#E8735A` (by eye) with white names and dates (portrait left, name, dates under), a shield with red balls at the root, orthogonal connectors in salmon about 3 px, branch labels "SENIOR BRANCH" and "JUNIOR (POPOLANI) BRANCH" in small capitals. Camera: continuous zoom and pan. Data: nodes `{id, name, dates, image, role}`, edges `{parent, child, kind}`, a focus node, a start view. Timing seen: root shield appears at 1:09 to 1:10 and grows from small to large over about 4 s; the camera then drifts for the rest of the 60 s.

**C11 Hidden layer (National Gallery `GsjKKvbVsOs`).** The infrared reflectogram of the Arnolfini Portrait (grey, Giovanni's hat and Costanza's headdress clearly drawn) and the colour picture are the same crop. At 0:38.5 to 0:41.0 colour shows, then dissolves to infrared over about 1 s (0:41.0 to 0:41.75); at 0:49.0 to 0:50.0 infrared dissolves to colour in about 0.5 s; at 0:55 colour to infrared; at 1:33 to 1:35 a detail (Costanza's face) goes infrared to colour in about 1.5 s. The picture does not move during a dissolve; the narrator explains in step. This is the one device that touches the Arnolfini Portrait itself.

**C18 Document line (Getty `J9yP1N0nLUg`).** A film of a dealer's ledger page, with a **blue rectangle outline** (about 3 px, `#2A3CC8` by eye) round one entry at a time (at 3:00 round "9379 J. L. Gerome 2645/ Lion on the Watch"); the outline moves between entries over 2 to 3 s each. Our identity forbids a box, so the lit-line version would dim the rest of the page to 35 percent and leave the entry bright (the engine's `X-HI-01` does this to pictures).

**C9 Big number (VICE `IQF6QFEY4Ps`).** "$450.3M" fades in at 0:41.0 (0.25 s) over footage that keeps playing, outlined white numerals with a grey fill (by eye), height about 33 percent of the frame, centred slightly above the middle, held 4 s, cut. A source line "Source: Christie's" in small white sans at the bottom left (cap about 1.8 percent). No counting up.

### 4.3 Counts in the Arnolfini narration (`projects/arnolfini/timing.json`, beats 000 to 090)

My reading of the sentences (a judgement, not a measurement). Sentence numbers are beat indices in `.scratch/r10/arnolfini_beats.txt`.

| Fact type | Beats | Count |
|---|---|---|
| Place or journey | 009, 010, 011, 012, 015, 022, 039, 040, 059, 083 | 10 |
| Date or span | 003, 005, 010, 015, 018, 020, 055, 084 | 8 (7 with real dates) |
| Quantity or price | 004, 035, 036, 040, 068 | 5 |
| Size | 004, 064 | 2 |
| Comparison with another work | 022, 030, 055, 056, 084, 028 | 6 |
| Family or patron relation | 012, 015, 018, 020, 022, 083 | 6 |
| Material or technique | 004, 035, 037, 057, 081, 082 | 6 |
| Change over time (restoration, underdrawing, layers) | 081, 082 | 2 |
| Document, inscription, inventory | 005, 018, 090 | 3 |
| People to show by name | 014, 018, 030, 066, 084 | 5 |
| Parts of a picture or room to name | 005, 027, 042, 047 to 060, 065 to 069 | about 14 |
| Composition or space | 062, 065, 069, 079 | 4 |
| Palette or dyes | 035, 037, 039 | 3 |
| Provenance (owners over time) | none | 0 |

Observation: the Arnolfini script, a typical long-form narration, calls for a map 10 times in 91 sentences, a name-a-part key about 14 times, and a time axis or date about 8 times. It never asks for a provenance chain, but videos about stolen, lost or sold works would.

---

## Part 5. What to build first

Scores are 1 to 5: need (counts above, scaled), how much clearer the point becomes, ease of building on the current engine. Product is need x clarity x ease.

| Rank | Component | Need | Clarity | Ease | Product | Why |
|---|---|---|---|---|---|---|
| 1 | Map component, three looks (C1 to C4) | 4 | 5 | 2 | 40, but the owner asked for it by name | 10 sentences; replaces three weak techniques |
| 2 | Labels as a key to parts of a picture (C16, with C20 portraits) | 5 | 4 | 4 | 80 | about 14 sentences; engine has labels; the Vienna frame already matches the identity |
| 3 | Time axis with dates (C5, C6) | 4 | 4 | 4 | 64 | 7 to 8 sentences; no assets except thumbnails |
| 4 | Big number and two-figure comparison (C9, C21, C22) | 4 | 4 | 4 | 64 | price, pelts, martens, size; very cheap (text and bars) |
| 5 | Family or succession tree (C17) | 3 | 5 | 3 | 45 | patrons, dynasties, marriages are the commonest relations in art books |
| 6 | Same picture in two states with a technique label (C10, C11) | 2 | 5 | 4 | 40 | the one device that shows a real change; mostly exists (`CMP-01`, `CMP-05`) and needs a caption and timing rules |
| 7 | Document with one entry lit (C18) | 3 | 4 | 3 | 36 | inscription, inventory, letters |
| later | Pigment key (C15), plan of a room (C13), chain of owners (C19), cross-section (C12), size against an object (C8) | 1 to 3 | 3 to 4 | 2 to 4 | 12 to 36 | rarer or need assets |

Build first: ranks 1 to 7. (Rank 2 outranks the map on the product; the map is first because the owner asked and because it replaces three techniques.) None of them needs a new library: they are polygons, lines, discs, text, crops and blends, all in the engine's list.

### 5.1 Parameter lists an agent could fill

All sizes are percent of the frame height unless noted; all times in seconds from the start of the shot; all text in the channel's typeface (EB Garamond), nothing boxed, text fades only.

**1. `MAP-01` (one technique, three looks).** `look` (`plate|relief|cutpaper`), `places` [`id`, `name`, `lon`, `lat`, `at` (anchor or seconds), `label_side` (`auto|n|ne|e|se|s|sw|w|nw`)], `route` {`from`, `to`, `via` [[lon,lat]...], `shape` (`curve|great_circle|straight|path`), `start`, `draw_s`, `head` (`dot|arrow|none`)}, `region` {`iso` [..] or `polygon` (GeoJSON), `at`, `fill_s`}, `view_start` {`center`, `width_km`}, `view_end` {`fit` [ids] or `center` and `width_km`, `margin_pct`}, `duration`, `era`, `credit`. Look-specific: see 3.3 to 3.5. Validation: every place needs `lon` in [-180, 180] and `lat` in [-85, 85]; a `route` references existing place ids; `view_end.width_km` between 50 and 20,000.

**2. `LABELS-KEY` (key to parts of a picture).** `labels` [{`text`, `point` (a region name of the picture or [x, y] in source pixels), `side` (`auto|n|ne|e|se|s|sw|w|nw`), `at`, `style` (`italic|regular|caps`)}], `cap_pct` (2.0 to 3.0, default 2.4), `leader` (`none|hairline`, default `none`), `shadow` (true), `fade_s` (0.3), `stagger_s` (0.4), `hold_s`, `dim_picture_to` (0.6 to 1.0, default 0.8). Photo-portrait option: `portraits` [{`image`, `name`, `dates`, `point`}] drawn as 6 percent roundels with a name beneath (fade only).

**3. `TIMELINE-01`.** `axis` {`from`, `to` (years, negative for BC), `tick_every` (years), `unit` (`year|century`)}, `items` [{`date`, `label`, `image` (optional), `side` (`up|down|auto`), `at`}], `focus` (a date to centre), `pan_s`, `stalk_px`, `thumb_pct` (6 to 12), `cap_pct` (1.5 to 2.0), `ground` (`dark|light`), `stagger_s`. For the Arnolfini example: 1425 painter to the Duke, 1431 Bruges, 1432 Ghent Altarpiece, 1434 the panel.

**4. `NUMBER-01` (number with source, and a two-figure comparison).** `value` (text, e.g. "$450.3M" or "600 -> 2,000"), `caption` (one short line), `source` (small line, bottom left), `cap_pct` (6 to 25), `style` (`outline|solid`), `count_up_s` (0 for none, 0.8 to 2.0 allowed), `compare` [{`label`, `value`, `n` (number of units for a pictogram row)}] (two to four rows), `hold_s`, `fade_s`.

**5. `TREE-01`.** `nodes` [{`id`, `name`, `dates`, `image` (optional), `role` (`root|branch|leaf`), `accent` (bool)}], `edges` [{`parent`, `child`, `kind` (`descent|marriage|succession`)}], `focus` (node id), `reveal` (`by_edge|all`), `step_s` (0.6), `camera_end` {`focus`, `zoom`}, `ground` (`cream|dark`). Names and dates only, no box; the connectors are 2 px hairlines.

**6. `STATES-01` (same picture in two states).** `a` (image), `b` (image of the same crop), `label_a`, `label_b` (the technique names, e.g. "Infrared", "Colour", "Before", "After"), `mode` (`dissolve|wipe_lr|wipe_rl`), `dissolve_s` (0.5 to 1.5), `holds` [seconds per state], `caption_pos` (`bottom_center|bottom_left`), `cap_pct` (2.0 to 2.8). Rule from the frames: the picture does not move during the change.

**7. `DOC-LIT` (document with one entry lit).** `document` (image), `lit` [{`rect` [x, y, w, h] in source pixels, `at`, `hold_s`}], `dim_to` (0.25 to 0.6, default 0.35), `ramp_s` (0.4), `zoom_to_lit` (bool, 1.0 to 1.8 times), `caption` (one line), `translation` (optional second line in italic under the lit entry).

### 5.2 What I would not build first, and why

- Plan of a room (C13): lovely in GAE (a soft spot of light moving over a plan), but it needs a drawn plan for every painting; an agent cannot supply that from JSON alone.
- Size against an object (C8): the only example I saw is footage. A graphic version is easy, but the Arnolfini script needs it once.
- Chain of owners (C19): needs ownership history, which the narration of this video never uses.

---

## Appendix A. Evidence files

Contact sheets (`.scratch/r10/sheets/`):
- Ours: `ours_STATIC-06_0-5.5s.jpg`, `ours_AN-04_0-6s.jpg`, `ours_X-ANN-05_0-6s.jpg`.
- Map moments (4 fps): `GAE_cuHgxPe3J7I_t135-150_4fps.jpg` (M1), `GAE_crCPVoPsTtk_t696-712_4fps.jpg` (M2), `GAE_ACnM_063tsw_t857-867_4fps.jpg` (M3), `GAE_f8OIYzV5Npo_t1358-1364_and_1377-1383_4fps.jpg` (M4, M5), `GAE_XKp6ahy2eBk_t454-460_4fps.jpg` (M6), `GAE_d50FbuyswAU_t920-926_4fps.jpg` (M7), `GAE_0sQ_cfZ8q9k_t1040-1049_4fps.jpg` (M8), `TEDEd_vn3e37VWc0k_t0036-0048_and_0128-0145_4fps.jpg` (M9, M10), `JohnnyHarris_Fp2PcrRNlGo_t0135-0150_4fps.jpg` (M11), `HistoriaCivilis_kmF3VBA_RcM_t0000-0011_and_0014-0022_4fps.jpg` (M12), `KingsGenerals_qeAcgE3Msto_t0133-0144_and_0207-0217_4fps.jpg` (M13), `HistoryOnMaps_aGG0kgVqhWY_t0031-0044_and_0119-0127_4fps.jpg` (M14, M15).
- Component sheets: `GAE_devices_T15Kv6dtYO0-t0250_ElWG0_kjy_Y-t0810_IYFtwTo50Gg-t0050_eKyYPSpiC9g-t0820_qJLH7JAsBHA-t0638_H8fGd3fCJbg-t2258_1fps.jpg`, `GAE_devices_YFI6cQF1ros-t1558_lAjVuUB9AkI-t0632_eKyYPSpiC9g-t2405_yUq9qMm9NtI-t0205_MAF9LURl7bs-t0500_1fps.jpg`, `GAE_XKp6ahy2eBk_t0456-0526_istanbul_recolour_1fps.jpg`, `NationalGallery_GsjKKvbVsOs_t0037-0042_0049-0056_0133-0136_4fps.jpg`, `EverythingExplained_hXBvN475dwo_t0000-0115_and_NationalGallery_GsjKKvbVsOs_t0030-0145_1fps.jpg`, `UsefulCharts_xAQfOAm0gN8_t0030-0130_and_Rijksmuseum_S-2tIXR0Sb4_t0040-0140_1fps.jpg`, `Nerdwriter1_rKhfFBbVtFg_t0014-0024_and_0052-0068_2fps.jpg`, `Getty_J9yP1N0nLUg_t0240-0350_ActualSize_58oCpcnOLpE_t0000-0102_VICE_IQF6QFEY4Ps_t0015-0100_1fps.jpg`, `VICE_IQF6QFEY4Ps_t0040-0046_Getty_J9yP1N0nLUg_t0252-0258_4fps.jpg`.
- Full-frame montages (`.scratch/r10/frames/`): `_quad_gae_dev1.jpg` (Arnolfini size, Mona cross-section, Bosch infrared, Bernini plan), `_quad_gae_dev2.jpg` (Vienna labels, Meninas pigment key, Last Supper plan, Guernica geometry), `_quad_tree_etc.jpg` (UsefulCharts timeline and tree), `_quad_ee_ng.jpg` (Everything Explained timeline, National Gallery infrared), `_quad_vice_getty.jpg` (VICE number, Getty ledger and chain card, ACTUAL SIZE tape), `GAE_paris_864.png`, `GAE_starry_707.png`, `GAE_venice_1363.png`, `JH_t0143.png`, `HoM_t0126.png`, `TEDEd_t0144.png`.
- Scouting sheets (coarser, `_scout_*.jpg`, 1 fps or 0.5 fps) and the helper scripts `sheet.py`, `multi.py`, `quad.py`, `probe.py`, `caps.py`, `vcaps.py` are in `.scratch/r10/`; `arnolfini_beats.txt` is the narration split into 91 beats.

Downloads (all in `research_media/other/r10/`, 480p or lower, each at most 90 s): 12 segments, listed in the final message. One attempt failed (National Gallery `V1vAcYiXI4Q` 2:00 to 3:20, ffmpeg exit 8) and was not retried or worked around. YouTube auto-caption text files for 16 videos (text only; two further caption requests were refused with HTTP 429 and not repeated) are in `.scratch/r10/caps/`. The eight earlier two-minute files in `research_media/other/` were used for scouting only.

## Appendix B. What I could not verify

- The title of the Starry Night episode (`crCPVoPsTtk.mp4` has no `.info.json` among the 86).
- Narration for the Oslo moment (no transcript for `d50FbuyswAU`). Captions for the other makers are YouTube auto-captions with about plus or minus 1 s accuracy; GAE ASR is segment-level, so "each dot lands on its word" in M1 is read from 4 fps frames against 1-second segment lines, not from word timestamps.
- Whether GAE's satellite maps are Google or another service (the Venice moments are clearly Google Maps screenshots; Starry Night and Oslo only look like it).
- Camera for Kings and Generals (low correlation), for History on Maps (automatic measure failed), and the 1.95 scale at M15. Pulses or glows on dots could not be seen at 4 fps.
- Hex values are quantised bins; cap-height percentages are read from pixel counts on 720p or 480p frames (about plus or minus 0.3 points). Colours marked "by eye" in Part 4 were not sampled.
- Natural Earth raster at 50m is 84.78 MB (page); how small it can be baked without visible softness at 1,000 km width, and the per-frame cost of polygon projection, shadows, globe remap and glow, were not tested (no code was run).
- Licences not read in full: GeoNames (page says "cc-by", no version), AWMC (README says ODbL 1.0, `LICENSE.txt` not opened), OpenStreetMap (not re-read). No open source for historical borders was verified.
- A draggable before-and-after slider, a counter that counts up, and a pictogram quantity comparison were **not seen** in any video I looked at. The graphic scale-against-an-object device was seen only as footage.
- The Arnolfini counts in 4.3 are my reading of the sentences.
- I could not see a map of the Burgundian territories in the National Gallery or Smarthistory videos about Van Eyck (the one download failed), so there is no art-historical map beyond the reference channel's.
