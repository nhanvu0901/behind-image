# The paintings of the library, as a queue for the pipeline

Generated on 2026-11-19 by `tools/paintings_table.py` from `library/artworks.json` and `library/dossiers/` and an `output/index.json` (297 entries: 285 artworks and 12 themed chapters). Do not edit the table by hand: change the script's notes and run it again.

## How to read it

- **key**: the artwork key of the library; a project is created from it (`POST /api/library/projects` with `artwork_key`).
- **status**: where the artwork stands as a subject for a video.
  - `done`: the output folder of the artwork holds the finished video (from the `output/index.json` this table was made with).
  - `in-progress`: a project exists and its output folder has no finished video yet (the project column says where it stands).
  - `recommended-1` to `recommended-5`, `runner-up`: the ranking of the research of 2026-11-19 (interesting story, little coverage on YouTube, a large reproduction).
  - `considered`: looked at in that research, not shortlisted.
  - `candidate`: enough text for a twelve-minute script (1,500 words of source text or more, or two books or more); YouTube and the reproduction are not checked yet.
  - `covered`: a large dedicated video exists on YouTube (measured); `covered-assumed`: very famous, assumed covered, not measured.
  - `not-flat`: not a flat painting (sculpture, embroidery, ceiling, installation): the pipeline's camera moves do not fit.
  - `thin-text`: one book and under 1,500 words: not enough for a long video.
  - `theme`: a themed chapter of a book, not one artwork.
- **words N / R / L**: words of source text by trust: normal / restored (the reviewed text of the machine-translated book, usable for ideas and readings, not for hard facts) / low (not used for facts).
- **img**: pictures of the artwork found in the books. **rights**: the library's own estimate (`pd_likely` public domain likely, and so on); copyright is not a blocker for the owner.
- **YouTube** and **reproduction**: from web searches and the Wikimedia Commons file data on 2026-11-19; `not checked` means nobody looked. Views are what the search pages showed that day.
- 5 paintings are in the library under two keys, one per book (the note says which): merge the pair in the library (`POST /api/library/artworks/merge`) before a project is made, so that both books feed it.
- The app saves a Wikimedia image at most 3,840 pixels wide, so a very large canvas zooms less deep than a small panel with the same file size.

## Counts

| status | artworks |
|---|---|
| `done` | 1 |
| `in-progress` | 1 |
| `recommended-1` | 1 |
| `recommended-2` | 1 |
| `recommended-3` | 1 |
| `recommended-4` | 1 |
| `recommended-5` | 1 |
| `runner-up` | 6 |
| `considered` | 10 |
| `candidate` | 65 |
| `covered` | 26 |
| `covered-assumed` | 10 |
| `not-flat` | 10 |
| `thin-text` | 151 |
| `theme` | 12 |

## The table

| # | status | key | title | artist | year | books | words N / R / L | img | rights | project | YouTube | reproduction | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `done` | `eyck-the-arnolfini-portrait` | The Arnolfini Portrait | Jan van Eyck | 1434 | payne_gae, hodge_aid, brookehitching_mad | 3476 / 0 / 0 | 14 | pd_likely | arnolfini-opus (video 12:44, 2026-11-19) | heavy: Great Art Explained 780k | 3840x5253 as saved by the app (Commons original 4386x6000) |  |
| 2 | `in-progress` | `munch-the-scream` | The Scream | Edvard Munch | 1893 | payne_gae, hodge_aid, grovier_nws | 3196 / 746 / 0 | 12 | pd_likely | scream (at step: edit, 2026-11-19) | heavy: Great Art Explained 1.03 million | not checked |  |
| 3 | `recommended-1` | `tour-the-fortune-teller` | The Fortune Teller | Georges de La Tour |  | hagen_wgps | 2694 / 0 / 0 | 0 | pd_likely |  | small: top 3,893 views, no large channel | 3806x3148 (Commons, Google Art Project) | Smuggled out of France in 1960; a scholar called it a forgery and found the word MERDE woven into a scarf (removed in 1982). The forgery claim is a minority view. |
| 4 | `recommended-2` | `altdorfer-the-battle-of-issus` | The Battle of Issus | Albrecht Altdorfer | 1529 | hagen_wgps | 2638 / 0 / 0 | 0 | pd_likely |  | small: Smarthistory 4:44 with 29k, the rest under 5k | 4592x6000 (Commons, Google Art Project) | Troop numbers on the banners (300,000 against 32,000), a map of the Mediterranean behind the battle, hung in Napoleon's bathroom. Best fit for the map and number components. |
| 5 | `recommended-3` | `tintoretto-the-abduction-of-the-body` | The Abduction of the Body of St Mark | Tintoretto | 1562–1566 | hagen_wgps | 2912 / 0 / 0 | 0 | pd_likely |  | none found for this painting; clips up to 7k | 7720x9600 (Commons) | Venice had its saint stolen from Egypt, hidden under pork; the doctor who paid is painted beside the saint; trimmed in 1807, a pyre overpainted until 1949. |
| 6 | `recommended-4` | `teniers-archduke-leopold-wilhelm-s-galleries` | Archduke Leopold Wilhelm’s Galleries at Brussels | David Teniers the Younger | c. 1650 | hagen_wgps | 2716 / 0 / 0 | 0 | pd_likely |  | none found beyond a one-hour lecture with 2.8k | 6558x4885 (Commons, Google Art Project) | A painting of exactly 50 paintings and their road from Venice through Charles I to Vienna. Which version (Vienna, Prado, others) must be confirmed; our text names only about eight of the 50. |
| 7 | `recommended-5` | `master-the-little-garden-of-paradise` | The Little Garden of Paradise | Upper Rhenish Master | c. 1410 | hagen_wgps | 2754 / 0 / 0 | 0 | pd_likely |  | small: 6.3k (German), nothing in English | 4752x3643 (Commons); deepest zoom of all, 115 px per cm | Postcard-sized panel hiding a small devil, a dead dragon and ten nameable birds. Less story, few components. |
| 8 | `runner-up` | `gozzoli-procession-of-the-magi` | Procession of the Magi | Benozzo Gozzoli | 1459–1461 | hodge_aid, hagen_wgps | 3315 / 0 / 0 | 0 | pd_likely |  | small: travel clips up to 14k | no complete flat image; part photographs about 5000 px | Two books. The Medici as the Magi; the painter's own portrait signed on his cap. A fresco on three walls. |
| 9 | `runner-up` | `carpaccio-miracle-of-the-relic-of` | Miracle of the Relic of the Cross | Vittore Carpaccio | 1494–1495 | hagen_wgps | 2818 / 0 / 0 | 0 | pd_likely |  | almost none: clips under 1.7k | 4326x4068 (Commons) | Venice in 1494 as a snapshot: the wooden Rialto bridge, the chimneys, the crowd. Lower drama. |
| 10 | `runner-up` | `velazquez-venus-at-her-mirror-the` | Venus at her Mirror (The Rokeby Venus) | Diego Velázquez | c. 1646 | hagen_wgps | 2725 / 0 / 0 | 0 | pd_likely |  | medium: a 43-minute documentary with 34k, a clip with 15k | 6162x4226 (Commons) | Slashed with a knife in 1914; the blurred face in the mirror; the Inquisition's fine for such pictures. |
| 11 | `runner-up` | `veronese-the-marriage-at-cana` | The Marriage at Cana | Paolo Veronese | 1562–1563 | hagen_wgps | 2482 / 0 / 0 | 0 | pd_likely |  | small: about eight videos, 13k to 33k | 10068x6742 (Commons), but the canvas is 9.9 m wide: shallow zoom | Two books. The three great painters as the musicians; the 1573 trial; taken by Napoleon. Same painting as `veronese-the-wedding-at-cana`: merge the two first. |
| 12 | `runner-up` | `surikov-the-boyarina-morozova` | The Boyarina Morozova | Vassily Surikov | 1887 | hagen_wgps | 2293 / 0 / 0 | 0 | pd_likely |  | small in English (1k to 3k), Russian up to 35k | 4696x2446 (Commons), canvas 5.9 m wide: shallow zoom | A noblewoman dragged to prison in 1672 raising two fingers. |
| 13 | `runner-up` | `veronese-the-wedding-at-cana` | The Wedding at Cana | Paolo Veronese | 1562–1563 | hodge_aid | 698 / 0 / 0 | 0 | pd_likely |  | small: about eight videos, 13k to 33k | 10068x6742 (Commons), but the canvas is 9.9 m wide: shallow zoom | Two books. The three great painters as the musicians; the 1573 trial; taken by Napoleon. Same painting as `veronese-the-marriage-at-cana`: merge the two first. |
| 14 | `considered` | `manuel-the-execution-of-john-the` | The Execution of John the Baptist | Niklaus Manuel | c. 1517 | hagen_wgps | 3058 / 0 / 0 | 0 | pd_likely |  | not checked | 1256x1641 (Commons): too small for close-ups | Signed with a dagger. |
| 15 | `considered` | `rivera-dream-of-a-sunday-afternoon` | Dream of a Sunday Afternoon in Alameda Park | Diego Rivera | 1948 | hagen_wgps | 3038 / 0 / 0 | 0 | unknown |  | medium: Spanish up to 68k, Sotheby's 42k | not checked | A hotel hid it for seven years. |
| 16 | `considered` | `witz-the-miraculous-draught-of-fishes` | The Miraculous Draught of Fishes | Konrad Witz | 1444 | hagen_wgps | 2997 / 0 / 0 | 0 | pd_likely |  | not checked | 2920x2568 (Commons): small |  |
| 17 | `considered` | `rembrandt-belshazzar-s-feast` | Belshazzar’s Feast | Rembrandt van Rijn | c. 1635 | hagen_wgps | 2934 / 0 / 0 | 0 | pd_likely |  | small: National Gallery 15.6k | not checked | The Hebrew writing on the wall; an X-ray shows overpainting. |
| 18 | `considered` | `christus-st-eligius` | St. Eligius | Petrus Christus | 1449 | hagen_wgps | 2883 / 0 / 0 | 0 | pd_likely |  | small: 15k to 16k | not checked |  |
| 19 | `considered` | `delacroix-the-death-of-sardanapalus` | The Death of Sardanapalus | Eugène Delacroix | c. 1827 | hagen_wgps | 2728 / 0 / 0 | 0 | pd_likely |  | small: all under 15k | not checked | Read only by its headings. |
| 20 | `considered` | `goes-the-portinari-altar` | The Portinari Altar | Hugo van der Goes | c. 1475 | hagen_wgps | 2709 / 0 / 0 | 0 | pd_likely |  | small: Smarthistory 48.6k | not checked | Two books. Same painting as `goes-portinari-altarpiece`: merge the two first. |
| 21 | `considered` | `cosimo-the-death-of-procris` | The Death of Procris | Piero di Cosimo | c. 1500 | hagen_wgps | 2681 / 0 / 0 | 0 | pd_likely |  | small: National Gallery film 36k | not checked |  |
| 22 | `considered` | `menzel-the-steel-mill` | The Steel Mill | Adolph Menzel | 1875 | hagen_wgps | 2559 / 0 / 0 | 0 | pd_likely |  | small: best English video 6.3k | 6016x4000 (Commons) | Fewer hidden details. |
| 23 | `considered` | `goes-portinari-altarpiece` | Portinari Altarpiece | Hugo van der Goes | c. 1475–1476 | hodge_aid | 983 / 0 / 0 | 0 | pd_likely |  | small: Smarthistory 48.6k | not checked | Two books. Same painting as `goes-the-portinari-altar`: merge the two first. |
| 24 | `candidate` | `dix-metropolis-triptych` | Metropolis (Triptych) | Otto Dix | 1928 | hagen_wgps | 3634 / 0 / 0 | 0 | unknown |  | not checked | not checked |  |
| 25 | `candidate` | `greco-the-burial-of-count-orgaz` | The Burial of Count Orgaz | El Greco | 1586 | hagen_wgps | 3282 / 0 / 0 | 0 | pd_likely |  | not checked | not checked | Same painting as `greco-the-burial-of-the-count`: merge the two first. |
| 26 | `candidate` | `bosch-the-haywain` | The Haywain | Hieronymus Bosch | 1485–1490 | hagen_wgps | 3224 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 27 | `candidate` | `chagall-white-crucifixion` | White Crucifixion | Marc Chagall | 1938 | hagen_wgps | 3042 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 28 | `candidate` | `bellotto-the-freyung-vienna-from-the` | The Freyung, Vienna, from the Southeast | Bernardo Bellotto | 1759–1760 | hagen_wgps | 3019 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 29 | `candidate` | `jordaens-the-king-drinks` | The King Drinks | Jacob Jordaens | 1640–1645 | hagen_wgps | 3007 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 30 | `candidate` | `elsheimer-st-elizabeth-tending-the-sick` | St Elizabeth Tending the Sick | Adam Elsheimer | c. 1597 | hagen_wgps | 2974 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 31 | `candidate` | `spitzweg-the-poor-poet` | The Poor Poet | Carl Spitzweg | 1839 | hagen_wgps | 2961 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 32 | `candidate` | `tiepolo-the-death-of-hyacinthus` | The Death of Hyacinthus | Giovanni Battista Tiepolo | 1752–1753 | hagen_wgps | 2902 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 33 | `candidate` | `caravaggio-judith-and-holofernes` | Judith and Holofernes | Caravaggio | c. 1599 | hagen_wgps | 2891 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 34 | `candidate` | `brun-the-chancellor-seguier` | The Chancellor Séguier | Charles Le Brun |  | hagen_wgps | 2886 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 35 | `candidate` | `rembrandt-jacob-blessing-the-sons-of` | Jacob Blessing the Sons of Joseph | Rembrandt van Rijn | 1656 | hagen_wgps | 2873 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 36 | `candidate` | `grien-the-three-stages-of-life` | The Three Stages of Life, with Death | Hans Baldung Grien | c. 1510 | hagen_wgps | 2836 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 37 | `candidate` | `tiepolo-the-banquet-of-cleopatra` | The Banquet of Cleopatra | Giovanni Battista Tiepolo | 1746–1750 | hagen_wgps | 2825 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 38 | `candidate` | `botticelli-the-story-of-nastagio-degli` | The Story of Nastagio degli Onesti | Sandro Botticelli | 1482–1483 | hagen_wgps | 2806 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 39 | `candidate` | `raphael-the-fire-in-the-borgo` | The Fire in the Borgo | Raphael | 1514–1517 | hagen_wgps | 2803 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 40 | `candidate` | `goya-the-duchess-of-alba` | The Duchess of Alba | Francisco de Goya | 1797 | hagen_wgps | 2792 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 41 | `candidate` | `watteau-the-music-party` | The Music-Party | Antoine Watteau | c. 1718 | hagen_wgps | 2792 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 42 | `candidate` | `brothers-february-miniature-from-the-tres` | February miniature from the “Très Riches Heures du Duc de Berry” | The Limburg Brothers | c. 1416 | hagen_wgps | 2739 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 43 | `candidate` | `renoir-the-luncheon-of-the-boating` | The Luncheon of the Boating Party | Pierre-Auguste Renoir | 1881 | hagen_wgps | 2730 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 44 | `candidate` | `rubens-the-love-garden` | The Love Garden | Peter Paul Rubens | c. 1632–1634 | hagen_wgps | 2719 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 45 | `candidate` | `guardi-the-parlour-of-san-zaccaria` | The Parlour of San Zaccaria | Francesco Guardi | 1750 | hagen_wgps | 2717 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 46 | `candidate` | `tischbein-goethe-in-the-roman-campagna` | Goethe in the Roman Campagna | Johann Heinrich Wilhelm Tischbein | 1786–1787 | hagen_wgps | 2699 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 47 | `candidate` | `virgin-the-virgin-and-child-with` | The Virgin and Child with St Anne | Master of the Transfiguration of the Virgin | c. 1480 | hagen_wgps | 2698 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 48 | `candidate` | `caravaggio-martyrdom-of-st-matthew` | Martyrdom of St. Matthew | Caravaggio | 1599–1600 | hagen_wgps | 2685 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 49 | `candidate` | `velazquez-the-surrender-of-breda` | The Surrender of Breda | Diego Velázquez | 1635 | hagen_wgps | 2678 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 50 | `candidate` | `gainsborough-mr-and-mrs-andrews` | Mr and Mrs Andrews | Thomas Gainsborough | 1749 | hagen_wgps | 2670 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 51 | `candidate` | `guardi-the-departure-of-the-doge` | The Departure of the Doge on Ascension Day | Francesco Guardi | c. 1770 | hagen_wgps | 2668 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 52 | `candidate` | `derby-a-philosopher-giving-a-lecture` | A Philosopher giving a Lecture on the Orrery | Joseph Wright of Derby | c. 1764–1766 | hagen_wgps | 2647 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 53 | `candidate` | `eyck-the-virgin-of-chancellor-nicolas` | The Virgin of Chancellor Nicolas Rolin | Jan van Eyck | c. 1437 | hagen_wgps | 2632 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 54 | `candidate` | `richter-the-schreckenstein-crossing` | The Schreckenstein Crossing | Ludwig Richter | 1837 | hagen_wgps | 2616 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 55 | `candidate` | `bruegel-the-tower-of-babel` | The Tower of Babel | Pieter Bruegel the Elder | 1563 | hagen_wgps | 2613 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 56 | `candidate` | `tintoretto-the-origin-of-the-milky` | The Origin of the Milky Way | Tintoretto | c. 1580 | hagen_wgps | 2608 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 57 | `candidate` | `friedrich-chalk-cliffs-on-rugen` | Chalk Cliffs on Rügen | Caspar David Friedrich | c. 1818 | hagen_wgps | 2562 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 58 | `candidate` | `cranach-the-stag-hunt` | The Stag Hunt | Lucas Cranach the Younger | 1544 | hagen_wgps | 2556 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 59 | `candidate` | `courbet-the-studio` | The Studio | Gustave Courbet | 1855 | hagen_wgps | 2548 / 0 / 0 | 0 | pd_likely |  | not checked | not checked | Same painting as `courbet-the-artist-s-studio`: merge the two first. |
| 60 | `candidate` | `manet-the-execution-of-maximilian` | The Execution of Maximilian | Édouard Manet | 1868 | hagen_wgps | 2544 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 61 | `candidate` | `watteau-love-at-the-french-theatre` | Love at the French Theatre | Antoine Watteau | 1716–1721 | hagen_wgps | 2533 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 62 | `candidate` | `gower-armada-portrait-of-elizabeth-i` | Armada Portrait of Elizabeth I | George Gower | c. 1590 | hagen_wgps | 2515 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 63 | `candidate` | `ingres-the-turkish-bath` | The Turkish Bath | Jean-Auguste-Dominique Ingres | 1863 | hagen_wgps | 2507 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 64 | `candidate` | `angelico-st-nicholas-of-bari` | St Nicholas of Bari | Fra Angelico | 1437 | hagen_wgps | 2501 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 65 | `candidate` | `bruegel-peasant-wedding-feast` | Peasant Wedding Feast | Pieter Bruegel the Elder | c. 1567 | hagen_wgps | 2493 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 66 | `candidate` | `menzel-the-flute-concert-of-frederick` | The Flute Concert of Frederick the Great at Sanssouci | Adolph Menzel | 1850–1852 | hagen_wgps | 2481 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 67 | `candidate` | `ensor-christ-s-entry-into-brussels` | Christ’s Entry into Brussels | James Ensor | 1888 | hagen_wgps | 2408 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 68 | `candidate` | `caron-caesar-augustus-and-the-tiburtine` | Caesar Augustus and the Tiburtine Sybil | Antoine Caron | c. 1580 | hagen_wgps | 2400 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 69 | `candidate` | `caron-the-massacre-by-the-triumvirate` | The Massacre by the Triumvirate | Antoine Caron | 1566 | hagen_wgps | 2325 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 70 | `candidate` | `manet-a-bar-at-the-folies` | A Bar at the Folies Bergère | Édouard Manet | 1881 | hagen_wgps, grovier_nws | 2321 / 673 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 71 | `candidate` | `hogarth-an-election-entertainment` | An Election Entertainment | William Hogarth | 1754–1755 | hagen_wgps | 2301 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 72 | `candidate` | `degas-the-rehearsal-on-the-stage` | The Rehearsal on the Stage | Edgar Degas | 1873 | hagen_wgps | 2236 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 73 | `candidate` | `bacon-three-studies-for-figures-at` | Three Studies for Figures at The Base of a Crucifixion | Francis Bacon | 1944 | payne_gae | 2028 / 0 / 0 | 11 | copyright_likely |  | not checked | not checked |  |
| 74 | `candidate` | `valadon-the-blue-room` | The Blue Room | Suzanne Valadon | 1923 | payne_gae | 1891 / 0 / 0 | 8 | unknown |  | not checked | not checked |  |
| 75 | `candidate` | `dali-the-temptation-of-st-anthony` | The Temptation of St Anthony | Salvador Dalí | 1946 | payne_gae | 1887 / 0 / 0 | 6 | copyright_likely |  | not checked | not checked |  |
| 76 | `candidate` | `gentileschi-judith-beheading-holofernes` | Judith Beheading Holofernes | Artemisia Gentileschi | 1620 | payne_gae | 1887 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 77 | `candidate` | `ringgold-woman-on-a-bridge-1` | Woman On a Bridge #1 of 5: Tar Beach | Faith Ringgold | 1988 | payne_gae | 1874 / 0 / 0 | 8 | copyright_likely |  | not checked | not checked |  |
| 78 | `candidate` | `basquiat-hollywood-africans` | Hollywood Africans | Jean-Michel Basquiat | 1983 | payne_gae | 1860 / 0 / 0 | 8 | copyright_likely |  | not checked | not checked |  |
| 79 | `candidate` | `klint-group-x-altarpiece-no-1` | Group X, Altarpiece No. 1 | Hilma af Klint | 1915 | payne_gae | 1810 / 0 / 0 | 9 | unknown |  | not checked | not checked |  |
| 80 | `candidate` | `kusama-the-aftermath-of-obliteration-of` | The Aftermath Of Obliteration Of Eternity | Yayoi Kusama | 2009 | payne_gae | 1810 / 0 / 0 | 8 | copyright_likely |  | not checked | not checked |  |
| 81 | `candidate` | `brun-marie-antoinette-in-a-chemise` | Marie Antoinette in a Chemise Dress | Élisabeth Vigée le Brun | 1783 | payne_gae | 1808 / 0 / 0 | 6 | pd_likely |  | not checked | not checked |  |
| 82 | `candidate` | `keeffe-jimson-weed-white-flower-no` | Jimson Weed/White Flower No. 1 | Georgia O’Keeffe | 1932 | payne_gae | 1795 / 0 / 0 | 8 | copyright_likely |  | not checked | not checked |  |
| 83 | `candidate` | `gentileschi-judith-slaying-holofernes` | Judith Slaying Holofernes | Artemisia Gentileschi | 1612–1613 | hodge_aid, brookehitching_mad | 1755 / 0 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 84 | `candidate` | `titian-bacchus-and-ariadne` | Bacchus and Ariadne | Titian | c. 1520–1523 | hodge_aid, grovier_nws | 1059 / 853 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 85 | `candidate` | `weyden-descent-from-the-cross` | Descent from the Cross | Rogier van der Weyden | c. 1435–1438 | hodge_aid, grovier_nws | 809 / 886 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 86 | `candidate` | `tintoretto-crucifixion` | Crucifixion | Tintoretto | 1565 | hodge_aid, grovier_nws | 793 / 746 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 87 | `candidate` | `angelico-the-annunciation` | The Annunciation | Fra Angelico | c. 1438–1445 | hodge_aid, grovier_nws | 785 / 634 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 88 | `candidate` | `grunewald-isenheim-altarpiece` | Isenheim Altarpiece | Matthias Grünewald | c. 1512–1516 | hodge_aid, grovier_nws | 740 / 899 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 89 | `covered` | `botticelli-the-birth-of-venus` | The Birth of Venus | Sandro Botticelli | 1485 | payne_gae, hagen_wgps, grovier_nws | 4521 / 827 / 0 | 11 | pd_likely |  | heavy: Great Art Explained 1.25 million | not checked |  |
| 90 | `covered` | `holbein-the-ambassadors` | The Ambassadors | Hans Holbein the Younger | 1533 | hodge_aid, hagen_wgps | 4360 / 0 / 0 | 0 | pd_likely |  | heavy: 193k | not checked |  |
| 91 | `covered` | `bosch-the-garden-of-earthly-delights` | The Garden of Earthly Delights | Hieronymus Bosch | 1490–1500 | payne_gae, hodge_aid, brookehitching_mad, grovier_nws | 3629 / 861 / 0 | 19 | pd_likely |  | heavy: 3.87 million | not checked |  |
| 92 | `covered` | `gericault-the-raft-of-the-medusa` | The Raft of the Medusa | Théodore Géricault | 1818–1819 | hodge_aid, hagen_wgps | 3601 / 0 / 0 | 0 | pd_likely |  | heavy: 557k | not checked |  |
| 93 | `covered` | `goya-the-third-of-may-1808` | The Third of May, 1808 | Francisco de Goya | 1814 | hodge_aid, hagen_wgps, grovier_nws | 3424 / 897 / 0 | 4 | pd_likely |  | heavy: Smarthistory 601k | not checked |  |
| 94 | `covered` | `klimt-the-kiss` | The Kiss | Gustav Klimt | 1907–1908 | payne_gae, hodge_aid, grovier_nws | 2911 / 749 / 0 | 12 | pd_likely |  | heavy: 1.87 million | not checked |  |
| 95 | `covered` | `vinci-mona-lisa` | Mona Lisa | Leonardo da Vinci | 1503 | payne_gae, hodge_aid, grovier_nws | 2782 / 846 / 0 | 12 | pd_likely |  | heavy: Great Art Explained 2.4 million | not checked |  |
| 96 | `covered` | `seurat-sunday-afternoon-on-the-island` | Sunday Afternoon on the Island of La Grande Jatte | Georges Seurat | 1884–1886 | hagen_wgps | 2619 / 0 / 0 | 0 | pd_likely |  | heavy: Great Art Explained on Seurat 527k | not checked |  |
| 97 | `covered` | `repin-zaporogian-cossacks-composing-a-letter` | Zaporogian Cossacks Composing a Letter to the Turkish Sultan | Ilya Repin | 1880–1891 | hagen_wgps | 2593 / 0 / 0 | 0 | pd_likely |  | heavy: 803k, 375k, 315k | not checked | Same painting as `repin-reply-of-the-zaporozhian-cossacks`: merge the two first. |
| 98 | `covered` | `mantegna-ludovico-gonzaga-and-his-family` | Ludovico Gonzaga and His Family | Andrea Mantegna | c. 1470 | hagen_wgps | 2517 / 0 / 0 | 0 | pd_likely |  | heavy: 100k and 72k | not checked |  |
| 99 | `covered` | `goya-saturn-devouring-his-son` | Saturn Devouring His Son | Francisco de Goya | c. 1819–1823 | payne_gae | 1972 / 0 / 0 | 7 | pd_likely |  | heavy: 1.0 million | not checked |  |
| 100 | `covered` | `hokusai-under-the-wave-off-kanagawa` | Under The Wave Off Kanagawa | Katsushika Hokusai | 1830–1832 | payne_gae | 1960 / 0 / 0 | 5 | pd_likely |  | heavy: Great Art Explained 4.52 million | not checked |  |
| 101 | `covered` | `hopper-nighthawks` | Nighthawks | Edward Hopper | 1942 | payne_gae | 1873 / 0 / 0 | 7 | copyright_likely |  | heavy: 3.68 million | not checked |  |
| 102 | `covered` | `zhang-along-the-river-during-the` | Along the River During the Qingming Festival | Zhang Zeduan | 1085–1145 | payne_gae | 1807 / 0 / 0 | 6 | pd_likely |  | heavy: Chinese explainers 0.3 to 1.7 million, English animation 182k | Commons' large file is the Qing court copy, not the Song original |  |
| 103 | `covered` | `monet-water-lilies` | Water Lilies | Claude Monet | 1914–1926 | payne_gae, grovier_nws | 1711 / 807 / 0 | 10 | pd_likely |  | heavy: 2.04 million | not checked |  |
| 104 | `covered` | `velazquez-las-meninas` | Las Meninas | Diego Velázquez | 1656 | hodge_aid, grovier_nws | 1132 / 840 / 0 | 3 | pd_likely |  | heavy: 521k | not checked |  |
| 105 | `covered` | `dali-the-persistence-of-memory` | The Persistence of Memory | Salvador Dalí | 1931 | brookehitching_mad, grovier_nws | 1040 / 809 / 0 | 11 | copyright_likely |  | heavy: Great Art Explained on Dali 2.06 million | not checked |  |
| 106 | `covered` | `picasso-guernica` | Guernica | Pablo Picasso | 1937 | hodge_aid, grovier_nws | 1014 / 762 / 0 | 4 | copyright_likely |  | heavy: 1.52 million | not checked |  |
| 107 | `covered` | `bacon-study-after-velazquez-s-portrait` | Study after Velázquez’s Portrait of Pope Innocent X | Francis Bacon | 1953 | hodge_aid, grovier_nws | 984 / 846 / 0 | 5 | copyright_likely |  | heavy: Great Art Explained 156k | not checked |  |
| 108 | `covered` | `warhol-marilyn-diptych` | Marilyn Diptych | Andy Warhol | 1962 | hodge_aid | 938 / 0 / 0 | 0 | copyright_likely |  | heavy: Great Art Explained 712k | not checked |  |
| 109 | `covered` | `raphael-the-school-of-athens` | The School of Athens | Raphael | 1510–1511 | hodge_aid, grovier_nws | 821 / 932 / 0 | 2 | pd_likely |  | heavy: 660k | not checked |  |
| 110 | `covered` | `repin-reply-of-the-zaporozhian-cossacks` | Reply of the Zaporozhian Cossacks to Sultan Mehmed IV | Ilya Repin | 1880–1891 | brookehitching_mad | 785 / 0 / 0 | 4 | pd_likely |  | heavy: 803k, 375k, 315k | not checked | Same painting as `repin-zaporogian-cossacks-composing-a-letter`: merge the two first. |
| 111 | `covered` | `seurat-bathers-at-asnieres` | Bathers at Asnières | Georges Seurat | 1884 | hodge_aid, grovier_nws | 737 / 954 / 0 | 3 | pd_likely |  | heavy: Great Art Explained on Seurat 527k | not checked |  |
| 112 | `covered` | `goya-black-paintings` | Black Paintings | Francisco de Goya | 1819–1823 | brookehitching_mad | 736 / 0 / 0 | 13 | pd_likely |  | heavy: 435k | not checked |  |
| 113 | `covered` | `caravaggio-the-supper-at-emmaus` | The Supper at Emmaus | Caravaggio | 1601 | hodge_aid, grovier_nws | 725 / 892 / 0 | 5 | pd_likely |  | heavy: Smarthistory 85k, a National Gallery film 2.6 million | not checked |  |
| 114 | `covered` | `sargent-portrait-of-madame-x` | Portrait of Madame X | John Singer Sargent | 1884 | brookehitching_mad | 716 / 0 / 0 | 3 | pd_likely |  | heavy: Great Art Explained 1.08 million | not checked |  |
| 115 | `covered-assumed` | `kahlo-self-portrait-with-thorn-necklace` | Self-Portrait With Thorn Necklace and Hummingbird | Frida Kahlo | 1940 | payne_gae, hodge_aid, grovier_nws | 2954 / 844 / 0 | 13 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 116 | `covered-assumed` | `david-the-death-of-marat` | The Death of Marat | Jacques-Louis David | 1793 | hagen_wgps | 2904 / 0 / 0 | 0 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 117 | `covered-assumed` | `turner-rain-steam-and-speed-the` | Rain, Steam and Speed – The Great Western Railway | J. M. W. Turner | 1844 | payne_gae, hodge_aid, grovier_nws | 2677 / 847 / 0 | 10 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 118 | `covered-assumed` | `titian-venus-of-urbino` | Venus of Urbino | Titian | c. 1538 | hagen_wgps | 2491 / 0 / 0 | 0 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 119 | `covered-assumed` | `bosch-the-conjurer` | The Conjurer | Hieronymus Bosch |  | hagen_wgps | 2443 / 0 / 0 | 0 | pd_likely |  | probably heavy (107k and 152k seen, not verified) | not checked |  |
| 120 | `covered-assumed` | `david-the-coronation-of-napoleon` | The Coronation of Napoleon | Jacques-Louis David | 1807 | hagen_wgps | 2276 / 0 / 0 | 0 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 121 | `covered-assumed` | `gogh-the-starry-night` | The Starry Night | Vincent van Gogh | 1889 | payne_gae | 1899 / 0 / 0 | 7 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 122 | `covered-assumed` | `picasso-les-demoiselles-d-avignon` | Les Demoiselles D’avignon | Pablo Picasso | 1907 | payne_gae | 1835 / 0 / 0 | 7 | copyright_likely |  | assumed heavy, not measured | not checked |  |
| 123 | `covered-assumed` | `vermeer-girl-with-a-pearl-earring` | Girl With a Pearl Earring | Johannes Vermeer | c. 1665 | payne_gae, grovier_nws | 1828 / 778 / 0 | 10 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 124 | `covered-assumed` | `fuseli-the-nightmare` | The Nightmare | Henry Fuseli | 1781 | brookehitching_mad, grovier_nws | 499 / 809 / 0 | 5 | pd_likely |  | assumed heavy, not measured | not checked |  |
| 125 | `not-flat` | `unknown-the-bayeux-tapestry` | The Bayeux Tapestry |  |  | hagen_wgps, grovier_nws | 2403 / 741 / 0 | 6 | pd_likely |  | not checked | not checked | Embroidery, 70 m long. |
| 126 | `not-flat` | `michelangelo-la-pieta` | La Pietà | Michelangelo | 1499 | payne_gae | 1834 / 0 / 0 | 8 | pd_likely |  | not checked | not checked | Sculpture. |
| 127 | `not-flat` | `julien-lessons-of-the-hour` | Lessons of The Hour | Isaac Julien | 2019 | payne_gae | 1789 / 0 / 0 | 6 | copyright_likely |  | not checked | not checked | Film installation. |
| 128 | `not-flat` | `anatsui-dusasa-ii` | Dusasa II | El Anatsui | 2007 | payne_gae | 1776 / 0 / 0 | 8 | copyright_likely |  | not checked | not checked | Hanging sculpture. |
| 129 | `not-flat` | `rodin-the-kiss` | The Kiss | Auguste Rodin | 1882 | payne_gae | 1773 / 0 / 0 | 7 | pd_likely |  | not checked | not checked | Sculpture. |
| 130 | `not-flat` | `houghton-georgiana-houghton-and-spiritualist-art` | Georgiana Houghton and Spiritualist Art | Georgiana Houghton |  | brookehitching_mad | 1521 / 0 / 0 | 6 | pd_likely |  | not checked | not checked | Not a flat painting. |
| 131 | `not-flat` | `bernini-the-ecstasy-of-st-teresa` | The Ecstasy of St Teresa | Gian Lorenzo Bernini | 1645–1652 | hodge_aid, grovier_nws | 1093 / 787 / 0 | 5 | pd_likely |  | not checked | not checked | Sculpture. |
| 132 | `not-flat` | `bourgeois-maman` | Maman | Louise Bourgeois | 1999 | hodge_aid, grovier_nws | 929 / 697 / 0 | 3 | copyright_likely |  | not checked | not checked | Sculpture. |
| 133 | `not-flat` | `michelangelo-sistine-chapel-ceiling` | Sistine Chapel Ceiling | Michelangelo | 1508–1512 | hodge_aid, grovier_nws | 848 / 822 / 0 | 3 | pd_likely |  | not checked | not checked | Ceiling fresco. |
| 134 | `not-flat` | `rodin-the-thinker` | The Thinker | Auguste Rodin | 1880–1904 | grovier_nws | 0 / 884 / 0 | 5 | pd_likely |  | heavy: Great Art Explained 725k | not checked | Sculpture. |
| 135 | `thin-text` | `unknown-unicorn-tapestries` | Unicorn Tapestries |  | 1495–1505 | brookehitching_mad | 1224 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 136 | `thin-text` | `abramovic-marina-abramovic-and-performance-art` | Marina Abramović and Performance Art | Marina Abramović |  | brookehitching_mad | 1142 / 0 / 0 | 3 | unknown |  | not checked | not checked |  |
| 137 | `thin-text` | `leger-still-life-with-a-beer` | Still Life with a Beer Mug | Fernand Léger | 1921–1922 | hodge_aid | 1095 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 138 | `thin-text` | `cezanne-still-life-with-plaster-cupid` | Still Life with Plaster Cupid | Paul Cézanne | 1895 | hodge_aid | 1092 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 139 | `thin-text` | `unknown-crucifixion-diptych` | Crucifixion Diptych |  | c. 1460 | brookehitching_mad | 1085 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 140 | `thin-text` | `chardin-soap-bubbles` | Soap Bubbles | Jean-Baptiste-Siméon Chardin | c. 1733–1734 | hodge_aid | 1073 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 141 | `thin-text` | `watteau-fetes-venitiennes` | Fêtes Vénitiennes | Antoine Watteau | 1718–1719 | hodge_aid | 1073 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 142 | `thin-text` | `unknown-portrait-of-barbara-van-beck` | Portrait of Barbara Van Beck |  | c. 1650 | brookehitching_mad | 1072 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 143 | `thin-text` | `bondone-the-adoration-of-the-magi` | The Adoration of the Magi | Giotto di Bondone | c. 1303–1305 | hodge_aid | 1062 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 144 | `thin-text` | `matisse-portrait-of-andre-derain` | Portrait of André Derain | Henri Matisse | 1905 | hodge_aid | 1059 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 145 | `thin-text` | `hunt-the-awakening-conscience` | The Awakening Conscience | William Holman Hunt | 1853 | hodge_aid | 1055 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 146 | `thin-text` | `tour-st-joseph-the-carpenter` | St Joseph the Carpenter | Georges de La Tour | c. 1642 | hodge_aid | 1055 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 147 | `thin-text` | `bellini-san-zaccaria-altarpiece` | San Zaccaria Altarpiece | Giovanni Bellini | 1505 | hodge_aid | 1051 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 148 | `thin-text` | `gogh-chair-with-pipe` | Chair with Pipe | Vincent van Gogh | 1888 | hodge_aid | 1049 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 149 | `thin-text` | `degas-after-the-bath-woman-drying` | After the Bath, Woman Drying Herself | Edgar Degas | 1890–1895 | hodge_aid | 1039 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 150 | `thin-text` | `vermeer-the-guitar-player` | The Guitar Player | Johannes Vermeer | c. 1670–1672 | hodge_aid | 1039 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 151 | `thin-text` | `lempicka-portrait-of-ira-p` | Portrait of Ira P | Tamara De Lempicka | 1930 | hodge_aid | 1033 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 152 | `thin-text` | `fragonard-the-musical-contest` | The Musical Contest | Jean-Honoré Fragonard | c. 1754–1755 | hodge_aid | 1029 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 153 | `thin-text` | `braque-man-with-a-guitar` | Man with a Guitar | Georges Braque | 1911–1912 | hodge_aid | 1015 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 154 | `thin-text` | `whistler-nocturne-in-black-and-gold` | Nocturne in Black and Gold, The Falling Rocket | James Abbott McNeill Whistler | 1875 | hodge_aid | 1014 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 155 | `thin-text` | `ernst-vox-angelica` | Vox Angelica | Max Ernst | 1943 | hodge_aid | 1011 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 156 | `thin-text` | `boccioni-unique-forms-of-continuity-in` | Unique Forms of Continuity in Space | Umberto Boccioni | 1913 | hodge_aid | 1008 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 157 | `thin-text` | `ingres-napoleon-i-on-his-imperial` | Napoleon I on his Imperial Throne | Jean-Auguste-Dominique Ingres | 1806 | hodge_aid | 999 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 158 | `thin-text` | `miro-the-hunter-catalan-landscape` | The Hunter (Catalan Landscape) | Joan Miró | 1923–1924 | hodge_aid | 994 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 159 | `thin-text` | `chagall-i-and-the-village` | I and the Village | Marc Chagall | 1911 | hodge_aid | 986 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 160 | `thin-text` | `malevich-suprematist-composition-aeroplane-flying` | Suprematist Composition: Aeroplane Flying | Kazimir Malevich | 1915 | hodge_aid | 981 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 161 | `thin-text` | `chirico-the-song-of-love` | The Song of Love | Giorgio De Chirico | 1914 | hodge_aid | 980 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 162 | `thin-text` | `rubens-the-elevation-of-the-cross` | The Elevation of the Cross | Peter Paul Rubens | 1610–1611 | hodge_aid | 966 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 163 | `thin-text` | `renoir-study-torso-sunlight-effect` | Study: Torso, Sunlight Effect | Pierre-Auguste Renoir | 1875–1876 | hodge_aid | 960 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 164 | `thin-text` | `hals-the-laughing-cavalier` | The Laughing Cavalier | Frans Hals | 1624 | hodge_aid | 955 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 165 | `thin-text` | `klee-ad-parnassum` | Ad Parnassum | Paul Klee | 1932 | hodge_aid | 953 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 166 | `thin-text` | `mondrian-composition-with-yellow-blue-and` | Composition with Yellow, Blue and Red | Piet Mondrian | 1937–1942 | hodge_aid | 953 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 167 | `thin-text` | `masaccio-the-holy-trinity-with-the` | The Holy Trinity with the Virgin and St John and Donors | Masaccio | c. 1425–1426 | hodge_aid | 952 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 168 | `thin-text` | `greco-the-burial-of-the-count` | The Burial of the Count of Orgaz | El Greco | 1586–1588 | hodge_aid | 945 / 0 / 0 | 0 | pd_likely |  | not checked | not checked | Same painting as `greco-the-burial-of-count-orgaz`: merge the two first. |
| 169 | `thin-text` | `rego-the-king-s-death` | The King’s Death | Paula Rego | 2014 | hodge_aid | 941 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 170 | `thin-text` | `gauguin-vision-after-the-sermon` | Vision After the Sermon | Paul Gauguin | 1888 | hodge_aid | 940 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 171 | `thin-text` | `grosz-suicide` | Suicide | George Grosz | 1916 | hodge_aid | 939 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 172 | `thin-text` | `mantegna-the-agony-in-the-garden` | The Agony in the Garden | Andrea Mantegna | c. 1458–1460 | hodge_aid | 929 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 173 | `thin-text` | `frankenthaler-mountains-and-sea` | Mountains and Sea | Helen Frankenthaler | 1952 | hodge_aid | 926 / 0 / 0 | 0 | unknown |  | not checked | not checked |  |
| 174 | `thin-text` | `keeffe-oriental-poppies` | Oriental Poppies | Georgia O’Keeffe | 1927 | hodge_aid | 926 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 175 | `thin-text` | `magritte-the-human-condition` | The Human Condition | René Magritte | 1933 | hodge_aid | 925 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 176 | `thin-text` | `dali-metamorphosis-of-narcissus` | Metamorphosis of Narcissus | Salvador Dalí | 1937 | hodge_aid | 912 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 177 | `thin-text` | `kiefer-black-flakes` | Black Flakes | Anselm Kiefer | 2006 | hodge_aid | 904 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 178 | `thin-text` | `francesca-madonna-and-child-with-saints` | Madonna and Child with Saints | Piero della Francesca | 1472–1474 | hodge_aid | 885 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 179 | `thin-text` | `messerschmidt-the-ghost-heads-of-franz` | The Ghost Heads of Franz Xaver Messerschmidt | Franz Xaver Messerschmidt | 1770–1783 | brookehitching_mad | 877 / 0 / 0 | 13 | pd_likely |  | not checked | not checked |  |
| 180 | `thin-text` | `constable-chain-pier-brighton` | Chain Pier, Brighton | John Constable | 1826–1827 | hodge_aid | 875 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 181 | `thin-text` | `manzoni-merda-d-artista` | Merda d’Artista | Piero Manzoni | 1961 | brookehitching_mad | 875 / 0 / 0 | 2 | copyright_likely |  | not checked | not checked |  |
| 182 | `thin-text` | `monet-autumn-effect-at-argenteuil` | Autumn Effect at Argenteuil | Claude Monet | 1873 | hodge_aid | 874 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 183 | `thin-text` | `friedrich-moonrise-over-the-sea` | Moonrise Over the Sea | Caspar David Friedrich | 1822 | hodge_aid | 872 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 184 | `thin-text` | `kandinsky-cossacks` | Cossacks | Wassily Kandinsky | 1910–1911 | hodge_aid | 858 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 185 | `thin-text` | `lorrain-seaport-with-the-embarkation-of` | Seaport with the Embarkation of the Queen of Sheba | Claude Lorrain | 1648 | hodge_aid | 854 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 186 | `thin-text` | `freud-benefits-supervisor-sleeping` | Benefits Supervisor Sleeping | Lucian Freud | 1995 | hodge_aid | 850 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 187 | `thin-text` | `tiepolo-the-finding-of-moses` | The Finding of Moses | Giovanni Battista Tiepolo | c. 1730–1735 | hodge_aid | 848 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 188 | `thin-text` | `estes-telephone-booths` | Telephone Booths | Richard Estes | 1967 | hodge_aid | 845 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 189 | `thin-text` | `millet-the-gleaners` | The Gleaners | Jean-François Millet | 1857 | hodge_aid | 844 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 190 | `thin-text` | `poussin-the-adoration-of-the-golden` | The Adoration of the Golden Calf | Nicolas Poussin | 1633–1634 | hodge_aid | 843 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 191 | `thin-text` | `unknown-typus-religionis` | Typus Religionis |  | c. 1700 | brookehitching_mad | 843 / 0 / 0 | 6 | pd_likely |  | not checked | not checked |  |
| 192 | `thin-text` | `david-the-oath-of-the-horatii` | The Oath of the Horatii | Jacques-Louis David | 1784 | hodge_aid | 839 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 193 | `thin-text` | `millais-ophelia` | Ophelia | John Everett Millais | 1851–1852 | hodge_aid | 836 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 194 | `thin-text` | `lichtenstein-whaam` | Whaam! | Roy Lichtenstein | 1963 | hodge_aid | 835 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 195 | `thin-text` | `hogarth-marriage-a-la-mode-1` | Marriage À-la-Mode: 1, The Marriage Settlement | William Hogarth | c. 1743 | hodge_aid | 834 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 196 | `thin-text` | `pissarro-the-boulevard-montmartre-at-night` | The Boulevard Montmartre at Night | Camille Pissarro | 1897 | hodge_aid | 831 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 197 | `thin-text` | `craesbeeck-the-temptation-of-st-anthony` | The Temptation of St Anthony | Joos van Craesbeeck | c. 1650 | brookehitching_mad | 827 / 0 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 198 | `thin-text` | `kauffmann-cornelia-mother-of-the-gracchi` | Cornelia, Mother of the Gracchi | Angelica Kauffmann | c. 1785 | hodge_aid | 824 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 199 | `thin-text` | `pritchard-bream-in-25-feet-of` | Bream in 25 Feet of Water Off the West Coast of Scotland | Zarh Pritchard | 1910 | brookehitching_mad | 824 / 0 / 0 | 2 | unknown |  | not checked | not checked |  |
| 200 | `thin-text` | `lautrec-at-the-moulin-rouge` | At the Moulin Rouge | Henri de Toulouse-Lautrec | 1892–1895 | hodge_aid | 822 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 201 | `thin-text` | `unknown-the-getty-kouros` | The Getty Kouros |  |  | brookehitching_mad | 822 / 0 / 0 | 4 | unknown |  | not checked | not checked |  |
| 202 | `thin-text` | `hopper-house-by-the-railroad` | House by the Railroad | Edward Hopper | 1925 | hodge_aid | 821 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 203 | `thin-text` | `kirchner-bathers-at-moritzburg` | Bathers at Moritzburg | Ernst Ludwig Kirchner | 1909–1926 | hodge_aid | 817 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 204 | `thin-text` | `cassatt-the-tea` | The Tea | Mary Stevenson Cassatt | c. 1880 | hodge_aid | 814 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 205 | `thin-text` | `durer-adoration-of-the-magi` | Adoration of the Magi | Albrecht Dürer | 1504 | hodge_aid | 812 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 206 | `thin-text` | `rousseau-tiger-in-a-tropical-storm` | Tiger in a Tropical Storm (Surprised!) | Henri Rousseau | 1891 | hodge_aid | 809 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 207 | `thin-text` | `canaletto-arrival-of-the-french-ambassador` | Arrival of the French Ambassador in Venice | Canaletto | c. 1727–1745 | hodge_aid | 806 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 208 | `thin-text` | `bruegel-netherlandish-proverbs` | Netherlandish Proverbs | Pieter Bruegel the Elder | 1559 | hodge_aid | 804 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 209 | `thin-text` | `unknown-portrait-of-edmond-de-belamy` | Portrait of Edmond de Belamy |  | 2018 | brookehitching_mad | 802 / 0 / 0 | 4 | copyright_likely |  | not checked | not checked |  |
| 210 | `thin-text` | `rembrandt-the-night-watch` | The Night Watch | Rembrandt van Rijn | 1642 | hodge_aid | 797 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 211 | `thin-text` | `hausmann-the-art-critic` | The Art Critic | Raoul Hausmann | 1919–1920 | brookehitching_mad | 789 / 0 / 0 | 4 | unknown |  | not checked | not checked |  |
| 212 | `thin-text` | `pollock-autumn-rhythm` | Autumn Rhythm | Jackson Pollock | 1950 | hodge_aid | 778 / 0 / 0 | 0 | copyright_likely |  | not checked | not checked |  |
| 213 | `thin-text` | `botticelli-primavera` | Primavera | Sandro Botticelli | c. 1481–1482 | hodge_aid | 777 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 214 | `thin-text` | `courbet-the-artist-s-studio` | The Artist’s Studio | Gustave Courbet | 1854–1855 | hodge_aid | 773 / 0 / 0 | 0 | pd_likely |  | not checked | not checked | Same painting as `courbet-the-studio`: merge the two first. |
| 215 | `thin-text` | `unknown-ripley-scroll` | Ripley Scroll |  |  | brookehitching_mad | 759 / 0 / 0 | 9 | pd_likely |  | not checked | not checked |  |
| 216 | `thin-text` | `oreno-mona-vanna-the-nude-mona` | Mona Vanna, the Nude Mona Lisa | Gian Giacomo Caprotti da Oreno | c. 1510 | brookehitching_mad | 755 / 0 / 0 | 8 | pd_likely |  | not checked | not checked |  |
| 217 | `thin-text` | `drolling-interior-of-a-kitchen` | Interior of a Kitchen | Martin Drölling | 1815 | brookehitching_mad | 750 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 218 | `thin-text` | `manet-le-dejeuner-sur-l-herbe` | Le Déjeuner sur l’Herbe | Édouard Manet | 1862–1863 | hodge_aid | 746 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 219 | `thin-text` | `matsys-the-ugly-duchess` | The Ugly Duchess | Quentin Matsys | c. 1513 | brookehitching_mad | 733 / 0 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 220 | `thin-text` | `unknown-christ-in-the-storm-on` | Christ in the Storm on the Sea of Galilee |  | 1633 | brookehitching_mad | 718 / 0 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 221 | `thin-text` | `unknown-tomb-of-the-diver` | Tomb of the Diver |  | c. 480 BC | brookehitching_mad | 704 / 0 / 0 | 8 | pd_likely |  | not checked | not checked |  |
| 222 | `thin-text` | `uccello-the-battle-of-san-romano` | The Battle of San Romano | Paolo Uccello | c. 1438–1440 | hodge_aid | 692 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 223 | `thin-text` | `oliver-man-consumed-by-flames` | Man Consumed by Flames | Isaac Oliver | 1600–1610 | brookehitching_mad | 684 / 0 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 224 | `thin-text` | `tadema-the-roses-of-heliogabalus` | The Roses of Heliogabalus | Sir Lawrence Alma-Tadema | 1888 | brookehitching_mad | 647 / 0 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 225 | `thin-text` | `delacroix-entry-of-the-crusaders-into` | Entry of the Crusaders into Constantinople | Eugène Delacroix | 1840 | hodge_aid | 646 / 0 / 0 | 0 | pd_likely |  | not checked | not checked |  |
| 226 | `thin-text` | `unknown-tapuya-woman` | Tapuya Woman |  | 1641 | brookehitching_mad | 642 / 0 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 227 | `thin-text` | `heintz-competition-on-the-ponte-dei` | Competition on the Ponte dei Pugni in Venice | Joseph Heintz the Younger | 1673 | brookehitching_mad | 637 / 0 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 228 | `thin-text` | `unknown-hikeshi-banten` | Hikeshi-banten |  |  | brookehitching_mad | 636 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 229 | `thin-text` | `burgkmair-triumphal-procession-of-emperor-maximilian` | Triumphal Procession of Emperor Maximilian I | Hans Burgkmair the Elder | 1512–1526 | brookehitching_mad | 606 / 0 / 0 | 16 | pd_likely |  | not checked | not checked |  |
| 230 | `thin-text` | `hampton-the-throne-of-the-third` | The Throne of the Third Heaven… | James Hampton | c. 1950–1964 | brookehitching_mad | 601 / 0 / 0 | 7 | unknown |  | not checked | not checked |  |
| 231 | `thin-text` | `unknown-nebra-sky-disc` | Nebra Sky Disc |  | c. 1600 BC | brookehitching_mad | 596 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 232 | `thin-text` | `piranesi-the-imaginary-prisons-of-giovanni` | The Imaginary Prisons of Giovanni Battista Piranesi | Giovanni Battista Piranesi | 1750 | brookehitching_mad | 593 / 0 / 0 | 11 | pd_likely |  | not checked | not checked |  |
| 233 | `thin-text` | `klein-mondo-cane-shroud` | Mondo Cane Shroud | Yves Klein | 1961 | brookehitching_mad | 570 / 0 / 0 | 3 | copyright_likely |  | not checked | not checked |  |
| 234 | `thin-text` | `marc-fate-of-the-animals` | Fate of the Animals | Franz Marc | 1913 | brookehitching_mad | 567 / 0 / 0 | 1 | copyright_likely |  | not checked | not checked |  |
| 235 | `thin-text` | `unknown-japanese-kusozu` | Japanese Kusozu |  |  | brookehitching_mad | 557 / 0 / 0 | 11 | pd_likely |  | not checked | not checked |  |
| 236 | `thin-text` | `barker-mr-barker-s-monster-panoramas` | Mr Barker’s Monster Panoramas | Robert Barker | 1789 | brookehitching_mad | 556 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 237 | `thin-text` | `unknown-statue-of-glycon-the-false` | Statue of Glycon, the False Snake Deity |  |  | brookehitching_mad | 556 / 0 / 0 | 3 | unknown |  | not checked | not checked |  |
| 238 | `thin-text` | `mazzanti-joseph-of-cupertino-takes-flight` | Joseph of Cupertino Takes Flight... | Ludovico Mazzanti |  | brookehitching_mad | 550 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 239 | `thin-text` | `unknown-lucifer-s-new-row-barge` | Lucifer’s New Row-Barge |  | c. 1722 | brookehitching_mad | 542 / 0 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 240 | `thin-text` | `unknown-st-christopher-dog-head` | St Christopher Dog-head |  |  | brookehitching_mad | 538 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 241 | `thin-text` | `brassau-the-art-of-pierre-brassau` | The Art of Pierre Brassau | Pierre Brassau | 1964 | brookehitching_mad | 537 / 0 / 0 | 5 | copyright_likely |  | not checked | not checked |  |
| 242 | `thin-text` | `dadd-the-fairy-feller-s-master` | The Fairy Feller’s Master-Stroke | Richard Dadd | 1855–1864 | brookehitching_mad | 517 / 0 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 243 | `thin-text` | `stace-the-eternity-of-arthur-stace` | The Eternity of Arthur Stace | Arthur Stace | 1932–1967 | brookehitching_mad | 506 / 0 / 0 | 1 | unknown |  | not checked | not checked |  |
| 244 | `thin-text` | `comte-the-coronation-of-ines-de` | The Coronation of Inês de Castro in 1361 | Pierre Charles Comte | c. 1849 | brookehitching_mad | 503 / 0 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 245 | `thin-text` | `unknown-gabrielle-d-estrees-and-one` | Gabrielle d’Estrées and One of Her Sisters |  | c. 1594 | brookehitching_mad | 500 / 0 / 0 | 1 | pd_likely |  | not checked | not checked |  |
| 246 | `thin-text` | `unknown-wound-man` | Wound Man |  |  | brookehitching_mad | 492 / 0 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 247 | `thin-text` | `unknown-venus-of-hohle-fels` | Venus of Hohle Fels |  | 38,000–33,000 BC | brookehitching_mad | 491 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 248 | `thin-text` | `unknown-central-african-minkisi-power-figures` | Central African Minkisi Power Figures |  |  | brookehitching_mad | 489 / 0 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 249 | `thin-text` | `unknown-angeles-arcabuceros-the-art-of` | Ángeles Arcabuceros – The Art of the Angel Musketeer |  |  | brookehitching_mad | 485 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 250 | `thin-text` | `unknown-portrait-of-the-devil-codex` | Portrait of the Devil, Codex Gigas |  |  | brookehitching_mad | 482 / 0 / 0 | 2 | unknown |  | not checked | not checked |  |
| 251 | `thin-text` | `unknown-doom-paintings` | Doom Paintings |  |  | brookehitching_mad | 455 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 252 | `thin-text` | `kahlo-the-wounded-deer` | The Wounded Deer | Frida Kahlo | 1946 | brookehitching_mad | 451 / 0 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 253 | `thin-text` | `unknown-fool-s-cap-map-of` | Fool’s Cap Map of the World |  | c. 1580–1590 | brookehitching_mad | 450 / 0 / 0 | 1 | pd_likely |  | not checked | not checked |  |
| 254 | `thin-text` | `arcimboldo-the-composite-art-of-arcimboldo` | The Composite Art of Arcimboldo | Giuseppe Arcimboldo | c. 1563–1590 | brookehitching_mad | 430 / 0 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 255 | `thin-text` | `unknown-colossal-heads-of-the-olmec` | Colossal Heads of the Olmec |  | c. 900 BC | brookehitching_mad | 422 / 0 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 256 | `thin-text` | `dalem-the-legend-of-the-baker` | The Legend of the Baker of Eeklo | Cornelis van Dalem | c. 1550–1650 | brookehitching_mad | 392 / 0 / 0 | 1 | pd_likely |  | not checked | not checked |  |
| 257 | `thin-text` | `francesca-portrait-of-federico-da-montefeltro` | Portrait of Federico da Montefeltro | Piero della Francesca | c. 1473–1475 | brookehitching_mad | 373 / 0 / 0 | 7 | pd_likely |  | not checked | not checked |  |
| 258 | `thin-text` | `hemessen-self-portrait` | Self-Portrait | Catharina van Hemessen | 1548 | grovier_nws | 0 / 1078 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 259 | `thin-text` | `unknown-the-frescoes-of-the-villa` | The Frescoes of the Villa of the Mysteries, Pompeii |  |  | grovier_nws | 0 / 934 / 0 | 2 | unknown |  | not checked | not checked |  |
| 260 | `thin-text` | `rembrandt-self-portrait-with-two-circles` | Self-Portrait with Two Circles | Rembrandt van Rijn | c. 1665–1669 | grovier_nws | 0 / 919 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 261 | `thin-text` | `wood-american-gothic` | American Gothic | Grant Wood | 1930 | grovier_nws | 0 / 895 / 0 | 5 | unknown |  | not checked | not checked |  |
| 262 | `thin-text` | `cornell-the-elements-of-natural-history` | The Elements of Natural History | Joseph Cornell | 1940 | grovier_nws | 0 / 873 / 0 | 4 | unknown |  | not checked | not checked |  |
| 263 | `thin-text` | `constable-the-hay-wain` | The Hay Wain | John Constable | 1821 | grovier_nws | 0 / 864 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 264 | `thin-text` | `derby-an-experiment-on-a-bird` | An Experiment on a Bird in the Air Pump | Joseph Wright of Derby | 1768 | grovier_nws | 0 / 861 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 265 | `thin-text` | `richter-betty` | Betty | Gerhard Richter |  | grovier_nws | 0 / 858 / 0 | 4 | unknown |  | not checked | not checked |  |
| 266 | `thin-text` | `unknown-the-terracotta-army-of-qin` | The Terracotta Army of Qin Shi Huang |  | c. 210 BC | grovier_nws | 0 / 856 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 267 | `thin-text` | `kuan-travelers-among-mountains-and-streams` | Travelers among Mountains and Streams | Fan Kuan |  | grovier_nws | 0 / 848 / 0 | 3 | unknown |  | not checked | not checked |  |
| 268 | `thin-text` | `pollock-one-number-31` | One: Number 31 | Jackson Pollock | 1950 | grovier_nws | 0 / 838 / 0 | 3 | copyright_likely |  | not checked | not checked |  |
| 269 | `thin-text` | `cezanne-the-large-bathers` | The Large Bathers | Paul Cézanne | 1900–1906 | grovier_nws | 0 / 836 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 270 | `thin-text` | `damascus-trajan-s-column` | Trajan's Column | Apollodorus of Damascus | AD 113 | grovier_nws | 0 / 826 / 0 | 4 | pd_likely |  | not checked | not checked |  |
| 271 | `thin-text` | `masaccio-the-expulsion-of-adam-and` | The Expulsion of Adam and Eve | Masaccio | c. 1427 | grovier_nws | 0 / 823 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 272 | `thin-text` | `unknown-the-book-of-kells` | The Book of Kells |  |  | grovier_nws | 0 / 822 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 273 | `thin-text` | `warhol-brillo-boxes` | Brillo Boxes | Andy Warhol | 1964 | grovier_nws | 0 / 821 / 0 | 2 | copyright_likely |  | not checked | not checked |  |
| 274 | `thin-text` | `unknown-the-lion-hunt-of-ashurbanipal` | The Lion Hunt of Ashurbanipal |  | 645–635 BC | grovier_nws | 0 / 817 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 275 | `thin-text` | `whistler-arrangement-in-grey-and-black` | Arrangement in Grey and Black No. 1 (Portrait of the Artist's Mother) | James Abbott McNeill Whistler | 1871 | grovier_nws | 0 / 803 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 276 | `thin-text` | `eyck-the-ghent-altarpiece` | The Ghent Altarpiece | Jan van Eyck | 1430–1432 | grovier_nws | 0 / 800 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 277 | `thin-text` | `mantegna-the-lamentation-over-the-dead` | The Lamentation over the Dead Christ | Andrea Mantegna | c. 1480 | grovier_nws | 0 / 792 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 278 | `thin-text` | `unknown-laocoon-and-his-sons` | Laocoön and His Sons |  | 27 BC–AD 68 | grovier_nws | 0 / 792 / 0 | 3 | pd_likely |  | not checked | not checked |  |
| 279 | `thin-text` | `matisse-dance` | Dance | Henri Matisse | 1909–1910 | grovier_nws | 0 / 784 / 0 | 5 | pd_likely |  | not checked | not checked |  |
| 280 | `thin-text` | `klint-the-ten-largest-group-iv` | The Ten Largest, Group IV, No. 7, Adulthood | Hilma af Klint | 1907 | grovier_nws | 0 / 779 / 0 | 4 | unknown |  | not checked | not checked |  |
| 281 | `thin-text` | `bingen-the-cosmic-man` | The Cosmic Man | Hildegard of Bingen | 1165 | grovier_nws | 0 / 722 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 282 | `thin-text` | `scully-back-and-front` | Back and Front | Sean Scully | 1981 | grovier_nws | 0 / 0 / 713 | 3 | copyright_likely |  | not checked | not checked |  |
| 283 | `thin-text` | `duchamp-fountain` | Fountain | Marcel Duchamp | 1917 | grovier_nws | 0 / 658 / 0 | 3 | unknown |  | not checked | not checked |  |
| 284 | `thin-text` | `unknown-the-parthenon-sculptures` | The Parthenon Sculptures |  | 444 BC | grovier_nws | 0 / 627 / 0 | 2 | pd_likely |  | not checked | not checked |  |
| 285 | `thin-text` | `abramovic-the-artist-is-present` | The Artist Is Present | Marina Abramović | 2010 | grovier_nws | 0 / 410 / 0 | 1 | copyright_likely |  | not checked | not checked |  |
| 286 | `theme` | `theme-dasal_artcurious-05` | The Lady Vanishes: The (Multiple) Thefts and Forgeries of the Mona Lisa |  |  | dasal_artcurious | 8447 / 0 / 0 | 1 | unknown |  |  |  |  |
| 287 | `theme` | `theme-dasal_artcurious-11` | A Ready-Made Revelation: Is a German Baroness Responsible for a Marcel Duchamp Masterpiece? |  |  | dasal_artcurious | 8345 / 0 / 0 | 1 | unknown |  |  |  |  |
| 288 | `theme` | `theme-dasal_artcurious-07` | The (Possible) Murder of Vincent van Gogh |  |  | dasal_artcurious | 8002 / 0 / 0 | 1 | unknown |  |  |  |  |
| 289 | `theme` | `theme-dasal_artcurious-03` | Was British Painter Walter Sickert Really Jack the Ripper? |  |  | dasal_artcurious | 6686 / 0 / 0 | 1 | unknown |  |  |  |  |
| 290 | `theme` | `theme-dasal_artcurious-09` | Séances and Surprises: The Spiritualist Women Who Invented Modern Art |  |  | dasal_artcurious | 6084 / 0 / 0 | 1 | unknown |  |  |  |  |
| 291 | `theme` | `theme-dasal_artcurious-01` | Your Mom’s Favorite Painter Was a Badass: Claude Monet and the Subversive Impressionists |  |  | dasal_artcurious | 5996 / 0 / 0 | 1 | unknown |  |  |  |  |
| 292 | `theme` | `theme-dasal_artcurious-08` | The Odyssey of an Oddity, or the Many Adventures of Salvator Mundi |  |  | dasal_artcurious | 5700 / 0 / 0 | 2 | unknown |  |  |  |  |
| 293 | `theme` | `theme-dasal_artcurious-04` | Sentimental, Cheesy, and . . . Socially Conscious: Norman Rockwell and the 1960s |  |  | dasal_artcurious | 5629 / 0 / 0 | 2 | unknown |  |  |  |  |
| 294 | `theme` | `theme-dasal_artcurious-12` | Toenails and Junk Mail: Andy Warhol’s Time Capsules |  |  | dasal_artcurious | 5429 / 0 / 0 | 0 | unknown |  |  |  |  |
| 295 | `theme` | `theme-dasal_artcurious-02` | Secrets and Lines: The CIA/AbEx Connection |  |  | dasal_artcurious | 5427 / 0 / 0 | 1 | unknown |  |  |  |  |
| 296 | `theme` | `theme-dasal_artcurious-06` | A Corpse Cornucopia: Renaissance Artists, Anatomy, and the Myth of Body Trafficking |  |  | dasal_artcurious | 4982 / 0 / 0 | 1 | unknown |  |  |  |  |
| 297 | `theme` | `theme-dasal_artcurious-10` | Booty Tunes: The “Butt Music” of Bosch’s The Garden of Earthly Delights |  |  | dasal_artcurious | 4887 / 0 / 0 | 1 | unknown |  |  |  |  |
