# D19 Library Rebuild: Changes Report (after the follow-up)

Compared: the catalogue as it was before the first D19 rebuild (`.scratch/ddata_backup/artworks.json`) against the Mac library
now (`library/artworks.json`, rebuilt with `python -m bti.library build` and `python -m bti.library dossiers`).
Artworks are matched by their set of works, so a changed key is not a missing artwork.

- Artworks before: 297, after: 297 (same groups of works, none merged or split).
- Artworks with at least one changed field: 164. Changed keys: 10. Rows below: 210.
- Protected keys `eyck-the-arnolfini-portrait` and `munch-the-scream`: unchanged (both present, no alias).

## Rules that produced these changes
- Source trust, per field: `library/overrides/` > clean text of a digital normal-trust book > clean text of a scanned (OCR) normal-trust
  book > PDF outline > anything from a low-trust (machine-translated) book. Each work records where each field came from
  (`field_src` in `works.json`); an artwork takes each field from its most trusted work, ties by book order.
- Titles are re-cased only when the source is all upper case or all lower case (small words lower case, a letter after an apostrophe never
  capitalised, the first word after a dash, a colon or a plate number capitalised). When a heading in capitals differs from the outline
  title only in case, the outline's casing is kept.
- Artists: one spelling per artist from `library/overrides/artists.json` (case, accents, hyphens and apostrophes are ignored when looking
  up). "After X" becomes `attribution: "after"`, "X (Attrib.)" becomes `attribution: "attributed"`. `artists.json` may give a `key_name` (the word keys start with: rembrandt, zhang).
- Years: `parse.parse_year` and `parse.print_year` (`1434`, `c. 1562–1566`, `c. 900 BC`, `27 BC–AD 68`). Text that is not a year is kept in
  `year_raw`, `year` is empty.
- Aliases: `library/overrides/aliases.json` (old key to current key), also written into the entries as `aliases`.

## Aliases (keys that changed)
| Old key | Current key |
|---|---|
| `attrib-along-the-river-during-the` | `zhang-along-the-river-during-the` |
| `bosch-the-conjuror` | `bosch-the-conjurer` |
| `dali-the-temptation-of-saint-anthony` | `dali-the-temptation-of-st-anthony` |
| `hogarth-marriage-a-la-mode-i` | `hogarth-marriage-a-la-mode-1` |
| `menzel-steel-mill` | `menzel-the-steel-mill` |
| `mire-the-hunter-catalan-landscape` | `miro-the-hunter-catalan-landscape` |
| `rijn-self-portrait-with-two-circles` | `rembrandt-self-portrait-with-two-circles` |
| `rijn-the-night-watch` | `rembrandt-the-night-watch` |
| `turner-rail-steam-and-speed` | `turner-rain-steam-and-speed-the` |
| `velazquez-venus-at-her-mirror` | `velazquez-venus-at-her-mirror-the` |

## Not years: kept in `year_raw`, `year` is empty
| Artwork | year_raw |
|---|---|
| `unknown-the-bayeux-tapestry` | after 1066 |
| `bosch-the-conjurer` | after 1475 |
| `tour-the-fortune-teller` | after 1630 |
| `brun-the-chancellor-seguier` | after 1660 |
| `unknown-the-frescoes-of-the-villa` | About 60 B.C. - 50 years ago |
| `unknown-the-book-of-kells` | approximately 800 years |
| `kuan-travelers-among-mountains-and-streams` | approximately 1,000 years |
| `unknown-statue-of-glycon-the-false` | late second century |
| `unknown-doom-paintings` | twelfth-thirteenth centuries |
| `unknown-portrait-of-the-devil-codex` | early thirteenth century |
| `unknown-japanese-kusozu` | thirteenth-nineteenth centuries |
| `unknown-ripley-scroll` | fourteenth century |
| `unknown-wound-man` | fifteenth-seventeenth centuries |
| `unknown-st-christopher-dog-head` | sixteenth-eighteenth centuries |
| `unknown-angeles-arcabuceros-the-art-of` | seventeenth century |
| `unknown-central-african-minkisi-power-figures` | seventeenth-twentieth centuries |
| `mazzanti-joseph-of-cupertino-takes-flight` | eighteenth century |
| `unknown-hikeshi-banten` | nineteenth century |
| `houghton-georgiana-houghton-and-spiritualist-art` | nineteenth-twentieth centuries |
| `unknown-the-getty-kouros` | twentieth century |

## Table of changes
| # | Old key | Current key | Field | Before | After | Works |
|---|---|---|---|---|---|---|
| 1 | `attrib-along-the-river-during-the` | `zhang-along-the-river-during-the` | **key** | attrib-along-the-river-during-the | zhang-along-the-river-during-the | payne_gae/001 |
| 1 | `attrib-along-the-river-during-the` | `zhang-along-the-river-during-the` | **artist** | Zhang Zeduan (Attrib.) | Zhang Zeduan | payne_gae/001 |
| 1 | `attrib-along-the-river-during-the` | `zhang-along-the-river-during-the` | **attribution** | *(none)* | attributed | payne_gae/001 |
| 2 | `eyck-the-arnolfini-portrait` | `eyck-the-arnolfini-portrait` | **artist** | Jan Van Eyck | Jan van Eyck | payne_gae/002, hodge_aid/003, brookehitching_mad/011 |
| 3 | `goya-saturn-devouring-his-son` | `goya-saturn-devouring-his-son` | **year** | c. 1819–23 | c. 1819–1823 | payne_gae/010 |
| 4 | `hokusai-under-the-wave-off-kanagawa` | `hokusai-under-the-wave-off-kanagawa` | **year** | 1830–32 | 1830–1832 | payne_gae/011 |
| 5 | `turner-rail-steam-and-speed` | `turner-rain-steam-and-speed-the` | **key** | turner-rail-steam-and-speed | turner-rain-steam-and-speed-the | payne_gae/012, hodge_aid/050, grovier_nws/034 |
| 5 | `turner-rail-steam-and-speed` | `turner-rain-steam-and-speed-the` | **title** | Rail, Steam and Speed | Rain, Steam and Speed – The Great Western Railway | payne_gae/012, hodge_aid/050, grovier_nws/034 |
| 6 | `gogh-the-starry-night` | `gogh-the-starry-night` | **artist** | Vincent Van Gogh | Vincent van Gogh | payne_gae/014 |
| 7 | `klimt-the-kiss` | `klimt-the-kiss` | **year** | 1907–8 | 1907–1908 | payne_gae/017, hodge_aid/070, grovier_nws/042 |
| 8 | `monet-water-lilies` | `monet-water-lilies` | **year** | 1914–26 | 1914–1926 | payne_gae/018, grovier_nws/044 |
| 9 | `klint-group-x-altarpiece-no-1` | `klint-group-x-altarpiece-no-1` | **artist** | Hilma Af Klint | Hilma af Klint | payne_gae/019 |
| 10 | `keeffe-jimson-weed-white-flower-no` | `keeffe-jimson-weed-white-flower-no` | **artist** | Georgia O’keeffe | Georgia O’Keeffe | payne_gae/021 |
| 11 | `dali-the-temptation-of-saint-anthony` | `dali-the-temptation-of-st-anthony` | **key** | dali-the-temptation-of-saint-anthony | dali-the-temptation-of-st-anthony | payne_gae/025 |
| 11 | `dali-the-temptation-of-saint-anthony` | `dali-the-temptation-of-st-anthony` | **title** | The Temptation of Saint Anthony | The Temptation of St Anthony | payne_gae/025 |
| 12 | `bondone-the-adoration-of-the-magi` | `bondone-the-adoration-of-the-magi` | **year** | c. 1303-05 | c. 1303–1305 | hodge_aid/001 |
| 13 | `masaccio-the-holy-trinity-with-the` | `masaccio-the-holy-trinity-with-the` | **year** | c. 1425-26 | c. 1425–1426 | hodge_aid/002 |
| 14 | `weyden-descent-from-the-cross` | `weyden-descent-from-the-cross` | **artist** | Rogier Van der Weyden | Rogier van der Weyden | hodge_aid/004, grovier_nws/013 |
| 14 | `weyden-descent-from-the-cross` | `weyden-descent-from-the-cross` | **year** | c. 1435-38 | c. 1435–1438 | hodge_aid/004, grovier_nws/013 |
| 15 | `uccello-the-battle-of-san-romano` | `uccello-the-battle-of-san-romano` | **year** | c. 1438-40 | c. 1438–1440 | hodge_aid/005 |
| 16 | `angelico-the-annunciation` | `angelico-the-annunciation` | **year** | c. 1438-45 | c. 1438–1445 | hodge_aid/006, grovier_nws/014 |
| 17 | `mantegna-the-agony-in-the-garden` | `mantegna-the-agony-in-the-garden` | **year** | c. 1458-60 | c. 1458–1460 | hodge_aid/007 |
| 18 | `gozzoli-procession-of-the-magi` | `gozzoli-procession-of-the-magi` | **year** | 1459-61 | 1459–1461 | hodge_aid/008, hagen_wgps/008 |
| 19 | `francesca-madonna-and-child-with-saints` | `francesca-madonna-and-child-with-saints` | **year** | 1472-74 | 1472–1474 | hodge_aid/009 |
| 20 | `goes-portinari-altarpiece` | `goes-portinari-altarpiece` | **artist** | Hugo Van der Goes | Hugo van der Goes | hodge_aid/010 |
| 20 | `goes-portinari-altarpiece` | `goes-portinari-altarpiece` | **year** | c. 1475-76 | c. 1475–1476 | hodge_aid/010 |
| 21 | `botticelli-primavera` | `botticelli-primavera` | **year** | c. 1481-82 | c. 1481–1482 | hodge_aid/011 |
| 22 | `michelangelo-sistine-chapel-ceiling` | `michelangelo-sistine-chapel-ceiling` | **year** | 1508-12 | 1508–1512 | hodge_aid/016, grovier_nws/019 |
| 23 | `raphael-the-school-of-athens` | `raphael-the-school-of-athens` | **year** | 1510-11 | 1510–1511 | hodge_aid/017, grovier_nws/020 |
| 24 | `grunewald-isenheim-altarpiece` | `grunewald-isenheim-altarpiece` | **year** | c. 1512-16 | c. 1512–1516 | hodge_aid/018, grovier_nws/021 |
| 25 | `titian-bacchus-and-ariadne` | `titian-bacchus-and-ariadne` | **year** | c. 1520-23 | c. 1520–1523 | hodge_aid/019, grovier_nws/022 |
| 26 | `veronese-the-wedding-at-cana` | `veronese-the-wedding-at-cana` | **year** | 1562-63 | 1562–1563 | hodge_aid/022 |
| 27 | `greco-the-burial-of-the-count` | `greco-the-burial-of-the-count` | **year** | 1586-88 | 1586–1588 | hodge_aid/024 |
| 28 | `rubens-the-elevation-of-the-cross` | `rubens-the-elevation-of-the-cross` | **year** | 1610-11 | 1610–1611 | hodge_aid/026 |
| 29 | `gentileschi-judith-slaying-holofernes` | `gentileschi-judith-slaying-holofernes` | **year** | c. 1620 | 1612–1613 | hodge_aid/027, brookehitching_mad/025 |
| 30 | `poussin-the-adoration-of-the-golden` | `poussin-the-adoration-of-the-golden` | **year** | 1633-34 | 1633–1634 | hodge_aid/029 |
| 31 | `rijn-the-night-watch` | `rembrandt-the-night-watch` | **key** | rijn-the-night-watch | rembrandt-the-night-watch | hodge_aid/030 |
| 32 | `bernini-the-ecstasy-of-st-teresa` | `bernini-the-ecstasy-of-st-teresa` | **year** | 1645-52 | 1645–1652 | hodge_aid/032, grovier_nws/026 |
| 33 | `velazquez-las-meninas` | `velazquez-las-meninas` | **artist** | Diego Velazquez | Diego Velázquez | hodge_aid/034, grovier_nws/027 |
| 34 | `vermeer-the-guitar-player` | `vermeer-the-guitar-player` | **artist** | Jan Vermeer | Johannes Vermeer | hodge_aid/035 |
| 34 | `vermeer-the-guitar-player` | `vermeer-the-guitar-player` | **year** | c. 1670-72 | c. 1670–1672 | hodge_aid/035 |
| 35 | `watteau-fetes-venitiennes` | `watteau-fetes-venitiennes` | **title** | Fétes Venitiennes | Fêtes Vénitiennes | hodge_aid/036 |
| 35 | `watteau-fetes-venitiennes` | `watteau-fetes-venitiennes` | **year** | 1718-19 | 1718–1719 | hodge_aid/036 |
| 36 | `canaletto-arrival-of-the-french-ambassador` | `canaletto-arrival-of-the-french-ambassador` | **year** | c. 1727-45 | c. 1727–1745 | hodge_aid/037 |
| 37 | `tiepolo-the-finding-of-moses` | `tiepolo-the-finding-of-moses` | **year** | c. 1730-35 | c. 1730–1735 | hodge_aid/038 |
| 38 | `chardin-soap-bubbles` | `chardin-soap-bubbles` | **year** | c. 1733-34 | c. 1733–1734 | hodge_aid/039 |
| 39 | `hogarth-marriage-a-la-mode-i` | `hogarth-marriage-a-la-mode-1` | **key** | hogarth-marriage-a-la-mode-i | hogarth-marriage-a-la-mode-1 | hodge_aid/040 |
| 39 | `hogarth-marriage-a-la-mode-i` | `hogarth-marriage-a-la-mode-1` | **title** | Marriage A-la-~Mode: I, The Marriage Settlement | Marriage À-la-Mode: 1, The Marriage Settlement | hodge_aid/040 |
| 40 | `fragonard-the-musical-contest` | `fragonard-the-musical-contest` | **year** | c. 1754-55 | c. 1754–1755 | hodge_aid/041 |
| 41 | `kauffmann-cornelia-mother-of-the-gracchi` | `kauffmann-cornelia-mother-of-the-gracchi` | **year** | c.1785 | c. 1785 | hodge_aid/043 |
| 42 | `gericault-the-raft-of-the-medusa` | `gericault-the-raft-of-the-medusa` | **year** | 1818-19 | 1818–1819 | hodge_aid/046, hagen_wgps/062 |
| 43 | `constable-chain-pier-brighton` | `constable-chain-pier-brighton` | **year** | 1826-27 | 1826–1827 | hodge_aid/048 |
| 44 | `delacroix-entry-of-the-crusaders-into` | `delacroix-entry-of-the-crusaders-into` | **artist** | Eugéne Delacroix | Eugène Delacroix | hodge_aid/049 |
| 45 | `millais-ophelia` | `millais-ophelia` | **year** | 1851-52 | 1851–1852 | hodge_aid/051 |
| 46 | `courbet-the-artist-s-studio` | `courbet-the-artist-s-studio` | **title** | The Artist's Studio | The Artist’s Studio | hodge_aid/053 |
| 46 | `courbet-the-artist-s-studio` | `courbet-the-artist-s-studio` | **year** | 1854-55 | 1854–1855 | hodge_aid/053 |
| 47 | `millet-the-gleaners` | `millet-the-gleaners` | **artist** | Jean-Francois Millet | Jean-François Millet | hodge_aid/054 |
| 48 | `manet-le-dejeuner-sur-l-herbe` | `manet-le-dejeuner-sur-l-herbe` | **artist** | Edouard Manet | Édouard Manet | hodge_aid/055 |
| 48 | `manet-le-dejeuner-sur-l-herbe` | `manet-le-dejeuner-sur-l-herbe` | **year** | 1862-63 | 1862–1863 | hodge_aid/055 |
| 49 | `renoir-study-torso-sunlight-effect` | `renoir-study-torso-sunlight-effect` | **year** | 1875-76 | 1875–1876 | hodge_aid/058 |
| 50 | `seurat-bathers-at-asnieres` | `seurat-bathers-at-asnieres` | **title** | Bathers at Asniéres | Bathers at Asnières | hodge_aid/060, grovier_nws/038 |
| 50 | `seurat-bathers-at-asnieres` | `seurat-bathers-at-asnieres` | **artist** | Georges-Pierre Seurat | Georges Seurat | hodge_aid/060, grovier_nws/038 |
| 51 | `gogh-chair-with-pipe` | `gogh-chair-with-pipe` | **artist** | Vincent Van Gogh | Vincent van Gogh | hodge_aid/062 |
| 52 | `degas-after-the-bath-woman-drying` | `degas-after-the-bath-woman-drying` | **year** | 1890-95 | 1890–1895 | hodge_aid/063 |
| 53 | `lautrec-at-the-moulin-rouge` | `lautrec-at-the-moulin-rouge` | **year** | 1892-95 | 1892–1895 | hodge_aid/065 |
| 54 | `kirchner-bathers-at-moritzburg` | `kirchner-bathers-at-moritzburg` | **year** | 1909-26 | 1909–1926 | hodge_aid/071 |
| 55 | `kandinsky-cossacks` | `kandinsky-cossacks` | **year** | 1910-11 | 1910–1911 | hodge_aid/072 |
| 56 | `braque-man-with-a-guitar` | `braque-man-with-a-guitar` | **year** | 1911-12 | 1911–1912 | hodge_aid/074 |
| 57 | `mire-the-hunter-catalan-landscape` | `miro-the-hunter-catalan-landscape` | **key** | mire-the-hunter-catalan-landscape | miro-the-hunter-catalan-landscape | hodge_aid/078 |
| 57 | `mire-the-hunter-catalan-landscape` | `miro-the-hunter-catalan-landscape` | **artist** | Joan Miré | Joan Miró | hodge_aid/078 |
| 57 | `mire-the-hunter-catalan-landscape` | `miro-the-hunter-catalan-landscape` | **year** | 1923-24 | 1923–1924 | hodge_aid/078 |
| 58 | `leger-still-life-with-a-beer` | `leger-still-life-with-a-beer` | **year** | 1921-22 | 1921–1922 | hodge_aid/080 |
| 59 | `keeffe-oriental-poppies` | `keeffe-oriental-poppies` | **artist** | Georgia O Keeffe | Georgia O’Keeffe | hodge_aid/082 |
| 60 | `dali-metamorphosis-of-narcissus` | `dali-metamorphosis-of-narcissus` | **artist** | Salvador Dali | Salvador Dalí | hodge_aid/086 |
| 61 | `mondrian-composition-with-yellow-blue-and` | `mondrian-composition-with-yellow-blue-and` | **year** | 1937-42 | 1937–1942 | hodge_aid/088 |
| 62 | `bacon-study-after-velazquez-s-portrait` | `bacon-study-after-velazquez-s-portrait` | **title** | Study after Velazquez’s Portrait of Pope Innocent X | Study after Velázquez’s Portrait of Pope Innocent X | hodge_aid/093, grovier_nws/052 |
| 63 | `unknown-the-bayeux-tapestry` | `unknown-the-bayeux-tapestry` | **year** | after 1066 | *(none)* | hagen_wgps/001, grovier_nws/009 |
| 63 | `unknown-the-bayeux-tapestry` | `unknown-the-bayeux-tapestry` | **year_raw** | *(none)* | after 1066 | hagen_wgps/001, grovier_nws/009 |
| 64 | `brothers-february-miniature-from-the-tres` | `brothers-february-miniature-from-the-tres` | **title** | February miniature from the “Tres Riches Heures du Due de Berry” | February miniature from the “Très Riches Heures du Duc de Berry” | hagen_wgps/003 |
| 65 | `bosch-the-conjuror` | `bosch-the-conjurer` | **key** | bosch-the-conjuror | bosch-the-conjurer | hagen_wgps/011 |
| 65 | `bosch-the-conjuror` | `bosch-the-conjurer` | **title** | The Conjuror | The Conjurer | hagen_wgps/011 |
| 65 | `bosch-the-conjuror` | `bosch-the-conjurer` | **year** | after 1475 | *(none)* | hagen_wgps/011 |
| 65 | `bosch-the-conjuror` | `bosch-the-conjurer` | **year_raw** | *(none)* | after 1475 | hagen_wgps/011 |
| 66 | `virgin-the-virgin-and-child-with` | `virgin-the-virgin-and-child-with` | **title** | The Virgin and Child with St. Anne | The Virgin and Child with St Anne | hagen_wgps/012 |
| 67 | `botticelli-the-story-of-nastagio-degli` | `botticelli-the-story-of-nastagio-degli` | **year** | 1482/83 | 1482–1483 | hagen_wgps/013 |
| 68 | `bosch-the-haywain` | `bosch-the-haywain` | **year** | between 1485 and 1490 | 1485–1490 | hagen_wgps/014 |
| 69 | `carpaccio-miracle-of-the-relic-of` | `carpaccio-miracle-of-the-relic-of` | **year** | 1494/95 | 1494–1495 | hagen_wgps/016 |
| 70 | `raphael-the-fire-in-the-borgo` | `raphael-the-fire-in-the-borgo` | **year** | 1514-1517 | 1514–1517 | hagen_wgps/019 |
| 71 | `veronese-the-marriage-at-cana` | `veronese-the-marriage-at-cana` | **artist** | Paolo Caliari (Veronese) | Paolo Veronese | hagen_wgps/025 |
| 71 | `veronese-the-marriage-at-cana` | `veronese-the-marriage-at-cana` | **year** | 1562/63 | 1562–1563 | hagen_wgps/025 |
| 72 | `tintoretto-the-abduction-of-the-body` | `tintoretto-the-abduction-of-the-body` | **year** | 1562-1566 | 1562–1566 | hagen_wgps/027 |
| 73 | `tintoretto-the-origin-of-the-milky` | `tintoretto-the-origin-of-the-milky` | **artist** | Jacopo Tintoretto | Tintoretto | hagen_wgps/031 |
| 74 | `caravaggio-martyrdom-of-st-matthew` | `caravaggio-martyrdom-of-st-matthew` | **title** | Martyrdom of St Matthew | Martyrdom of St. Matthew | hagen_wgps/036 |
| 74 | `caravaggio-martyrdom-of-st-matthew` | `caravaggio-martyrdom-of-st-matthew` | **year** | 1599/1600 | 1599–1600 | hagen_wgps/036 |
| 75 | `tour-the-fortune-teller` | `tour-the-fortune-teller` | **year** | after 1630 | *(none)* | hagen_wgps/037 |
| 75 | `tour-the-fortune-teller` | `tour-the-fortune-teller` | **year_raw** | *(none)* | after 1630 | hagen_wgps/037 |
| 76 | `rubens-the-love-garden` | `rubens-the-love-garden` | **year** | c. 1632-1634 | c. 1632–1634 | hagen_wgps/038 |
| 77 | `velazquez-the-surrender-of-breda` | `velazquez-the-surrender-of-breda` | **artist** | Diego Velazquez | Diego Velázquez | hagen_wgps/039 |
| 78 | `rembrandt-belshazzar-s-feast` | `rembrandt-belshazzar-s-feast` | **artist** | Rembrandt | Rembrandt van Rijn | hagen_wgps/040 |
| 79 | `jordaens-the-king-drinks` | `jordaens-the-king-drinks` | **year** | 1640-1645 | 1640–1645 | hagen_wgps/041 |
| 80 | `velazquez-venus-at-her-mirror` | `velazquez-venus-at-her-mirror-the` | **key** | velazquez-venus-at-her-mirror | velazquez-venus-at-her-mirror-the | hagen_wgps/042 |
| 80 | `velazquez-venus-at-her-mirror` | `velazquez-venus-at-her-mirror-the` | **title** | Venus at her Mirror | Venus at her Mirror (The Rokeby Venus) | hagen_wgps/042 |
| 80 | `velazquez-venus-at-her-mirror` | `velazquez-venus-at-her-mirror-the` | **artist** | Diego Velazquez | Diego Velázquez | hagen_wgps/042 |
| 81 | `rembrandt-jacob-blessing-the-sons-of` | `rembrandt-jacob-blessing-the-sons-of` | **artist** | Rembrandt | Rembrandt van Rijn | hagen_wgps/044 |
| 82 | `brun-the-chancellor-seguier` | `brun-the-chancellor-seguier` | **title** | The Chancellor Seguier | The Chancellor Séguier | hagen_wgps/045 |
| 82 | `brun-the-chancellor-seguier` | `brun-the-chancellor-seguier` | **year** | after 1660 | *(none)* | hagen_wgps/045 |
| 82 | `brun-the-chancellor-seguier` | `brun-the-chancellor-seguier` | **year_raw** | *(none)* | after 1660 | hagen_wgps/045 |
| 83 | `watteau-love-at-the-french-theatre` | `watteau-love-at-the-french-theatre` | **year** | 1716-1721 | 1716–1721 | hagen_wgps/046 |
| 84 | `tiepolo-the-banquet-of-cleopatra` | `tiepolo-the-banquet-of-cleopatra` | **artist** | Giambattista Tiepolo | Giovanni Battista Tiepolo | hagen_wgps/048 |
| 84 | `tiepolo-the-banquet-of-cleopatra` | `tiepolo-the-banquet-of-cleopatra` | **year** | 1746-1750 | 1746–1750 | hagen_wgps/048 |
| 85 | `tiepolo-the-death-of-hyacinthus` | `tiepolo-the-death-of-hyacinthus` | **artist** | Giambattista Tiepolo | Giovanni Battista Tiepolo | hagen_wgps/051 |
| 85 | `tiepolo-the-death-of-hyacinthus` | `tiepolo-the-death-of-hyacinthus` | **year** | 1752/53 | 1752–1753 | hagen_wgps/051 |
| 86 | `hogarth-an-election-entertainment` | `hogarth-an-election-entertainment` | **year** | 1754/55 | 1754–1755 | hagen_wgps/052 |
| 87 | `bellotto-the-freyung-vienna-from-the` | `bellotto-the-freyung-vienna-from-the` | **year** | 1759/60 | 1759–1760 | hagen_wgps/053 |
| 88 | `derby-a-philosopher-giving-a-lecture` | `derby-a-philosopher-giving-a-lecture` | **year** | 1764-1766 | c. 1764–1766 | hagen_wgps/054 |
| 89 | `tischbein-goethe-in-the-roman-campagna` | `tischbein-goethe-in-the-roman-campagna` | **year** | 1786/87 | 1786–1787 | hagen_wgps/056 |
| 90 | `delacroix-the-death-of-sardanapalus` | `delacroix-the-death-of-sardanapalus` | **artist** | Eugene Delacroix | Eugène Delacroix | hagen_wgps/063 |
| 91 | `menzel-the-flute-concert-of-frederick` | `menzel-the-flute-concert-of-frederick` | **year** | 1850-1852 | 1850–1852 | hagen_wgps/066 |
| 92 | `manet-the-execution-of-maximilian` | `manet-the-execution-of-maximilian` | **artist** | Edouard Manet | Édouard Manet | hagen_wgps/069 |
| 93 | `menzel-steel-mill` | `menzel-the-steel-mill` | **key** | menzel-steel-mill | menzel-the-steel-mill | hagen_wgps/071 |
| 93 | `menzel-steel-mill` | `menzel-the-steel-mill` | **title** | Steel Mill | The Steel Mill | hagen_wgps/071 |
| 94 | `repin-zaporogian-cossacks-composing-a-letter` | `repin-zaporogian-cossacks-composing-a-letter` | **year** | 1880-1891 | 1880–1891 | hagen_wgps/072 |
| 95 | `renoir-the-luncheon-of-the-boating` | `renoir-the-luncheon-of-the-boating` | **artist** | Pierre Auguste Renoir | Pierre-Auguste Renoir | hagen_wgps/073 |
| 96 | `manet-a-bar-at-the-folies` | `manet-a-bar-at-the-folies` | **title** | A Bar at the Folies Bergere | A Bar at the Folies Bergère | hagen_wgps/074, grovier_nws/037 |
| 96 | `manet-a-bar-at-the-folies` | `manet-a-bar-at-the-folies` | **artist** | Edouard Manet | Édouard Manet | hagen_wgps/074, grovier_nws/037 |
| 97 | `seurat-sunday-afternoon-on-the-island` | `seurat-sunday-afternoon-on-the-island` | **year** | 1884-1886 | 1884–1886 | hagen_wgps/075 |
| 98 | `unknown-the-lion-hunt-of-ashurbanipal` | `unknown-the-lion-hunt-of-ashurbanipal` | **year** | *(none)* | 645–635 BC | grovier_nws/001 |
| 99 | `unknown-the-parthenon-sculptures` | `unknown-the-parthenon-sculptures` | **year** | *(none)* | 444 BC | grovier_nws/002 |
| 100 | `unknown-the-terracotta-army-of-qin` | `unknown-the-terracotta-army-of-qin` | **year** | *(none)* | c. 210 BC | grovier_nws/003 |
| 101 | `unknown-the-frescoes-of-the-villa` | `unknown-the-frescoes-of-the-villa` | **year_raw** | *(none)* | About 60 B.C. - 50 years ago | grovier_nws/004 |
| 102 | `unknown-laocoon-and-his-sons` | `unknown-laocoon-and-his-sons` | **year** | *(none)* | 27 BC–AD 68 | grovier_nws/005 |
| 103 | `damascus-trajan-s-column` | `damascus-trajan-s-column` | **year** | *(none)* | AD 113 | grovier_nws/006 |
| 104 | `unknown-the-book-of-kells` | `unknown-the-book-of-kells` | **year_raw** | *(none)* | approximately 800 years | grovier_nws/007 |
| 105 | `kuan-travelers-among-mountains-and-streams` | `kuan-travelers-among-mountains-and-streams` | **year_raw** | *(none)* | approximately 1,000 years | grovier_nws/008 |
| 106 | `bingen-the-cosmic-man` | `bingen-the-cosmic-man` | **year** | *(none)* | 1165 | grovier_nws/010 |
| 107 | `masaccio-the-expulsion-of-adam-and` | `masaccio-the-expulsion-of-adam-and` | **year** | *(none)* | c. 1427 | grovier_nws/011 |
| 108 | `eyck-the-ghent-altarpiece` | `eyck-the-ghent-altarpiece` | **year** | *(none)* | 1430–1432 | grovier_nws/012 |
| 109 | `mantegna-the-lamentation-over-the-dead` | `mantegna-the-lamentation-over-the-dead` | **year** | *(none)* | c. 1480 | grovier_nws/015 |
| 110 | `hemessen-self-portrait` | `hemessen-self-portrait` | **year** | *(none)* | 1548 | grovier_nws/023 |
| 111 | `rijn-self-portrait-with-two-circles` | `rembrandt-self-portrait-with-two-circles` | **key** | rijn-self-portrait-with-two-circles | rembrandt-self-portrait-with-two-circles | grovier_nws/029 |
| 111 | `rijn-self-portrait-with-two-circles` | `rembrandt-self-portrait-with-two-circles` | **year** | *(none)* | c. 1665–1669 | grovier_nws/029 |
| 112 | `derby-an-experiment-on-a-bird` | `derby-an-experiment-on-a-bird` | **year** | *(none)* | 1768 | grovier_nws/030 |
| 113 | `constable-the-hay-wain` | `constable-the-hay-wain` | **year** | *(none)* | 1821 | grovier_nws/033 |
| 114 | `whistler-arrangement-in-grey-and-black` | `whistler-arrangement-in-grey-and-black` | **year** | *(none)* | 1871 | grovier_nws/035 |
| 115 | `rodin-the-thinker` | `rodin-the-thinker` | **year** | *(none)* | 1880–1904 | grovier_nws/036 |
| 116 | `cezanne-the-large-bathers` | `cezanne-the-large-bathers` | **year** | *(none)* | 1900–1906 | grovier_nws/040 |
| 117 | `klint-the-ten-largest-group-iv` | `klint-the-ten-largest-group-iv` | **year** | *(none)* | 1907 | grovier_nws/041 |
| 118 | `matisse-dance` | `matisse-dance` | **year** | *(none)* | 1909–1910 | grovier_nws/043 |
| 119 | `duchamp-fountain` | `duchamp-fountain` | **year** | *(none)* | 1917 | grovier_nws/045 |
| 120 | `wood-american-gothic` | `wood-american-gothic` | **year** | *(none)* | 1930 | grovier_nws/046 |
| 121 | `cornell-the-elements-of-natural-history` | `cornell-the-elements-of-natural-history` | **year** | *(none)* | 1940 | grovier_nws/049 |
| 122 | `warhol-brillo-boxes` | `warhol-brillo-boxes` | **year** | *(none)* | 1964 | grovier_nws/053 |
| 123 | `scully-back-and-front` | `scully-back-and-front` | **year** | *(none)* | 1981 | grovier_nws/054 |
| 124 | `abramovic-the-artist-is-present` | `abramovic-the-artist-is-present` | **year** | *(none)* | 2010 | grovier_nws/057 |
| 125 | `unknown-venus-of-hohle-fels` | `unknown-venus-of-hohle-fels` | **year** | 38,000-33,000 bc | 38,000–33,000 BC | brookehitching_mad/001 |
| 126 | `unknown-nebra-sky-disc` | `unknown-nebra-sky-disc` | **year** | c.1600 bc | c. 1600 BC | brookehitching_mad/002 |
| 127 | `unknown-colossal-heads-of-the-olmec` | `unknown-colossal-heads-of-the-olmec` | **year** | c.900 bc | c. 900 BC | brookehitching_mad/003 |
| 128 | `unknown-tomb-of-the-diver` | `unknown-tomb-of-the-diver` | **year** | c.480 bc | c. 480 BC | brookehitching_mad/004 |
| 129 | `unknown-statue-of-glycon-the-false` | `unknown-statue-of-glycon-the-false` | **year** | late second century | *(none)* | brookehitching_mad/005 |
| 129 | `unknown-statue-of-glycon-the-false` | `unknown-statue-of-glycon-the-false` | **year_raw** | *(none)* | late second century | brookehitching_mad/005 |
| 130 | `unknown-doom-paintings` | `unknown-doom-paintings` | **year** | twelfth-thirteenth centuries | *(none)* | brookehitching_mad/006 |
| 130 | `unknown-doom-paintings` | `unknown-doom-paintings` | **year_raw** | *(none)* | twelfth-thirteenth centuries | brookehitching_mad/006 |
| 131 | `unknown-portrait-of-the-devil-codex` | `unknown-portrait-of-the-devil-codex` | **year** | early thirteenth century | *(none)* | brookehitching_mad/007 |
| 131 | `unknown-portrait-of-the-devil-codex` | `unknown-portrait-of-the-devil-codex` | **year_raw** | *(none)* | early thirteenth century | brookehitching_mad/007 |
| 132 | `unknown-japanese-kusozu` | `unknown-japanese-kusozu` | **year** | thirteenth-nineteenth centuries | *(none)* | brookehitching_mad/008 |
| 132 | `unknown-japanese-kusozu` | `unknown-japanese-kusozu` | **year_raw** | *(none)* | thirteenth-nineteenth centuries | brookehitching_mad/008 |
| 133 | `unknown-ripley-scroll` | `unknown-ripley-scroll` | **year** | fourteenth century | *(none)* | brookehitching_mad/009 |
| 133 | `unknown-ripley-scroll` | `unknown-ripley-scroll` | **year_raw** | *(none)* | fourteenth century | brookehitching_mad/009 |
| 134 | `unknown-wound-man` | `unknown-wound-man` | **year** | fifteenth-seventeenth centuries | *(none)* | brookehitching_mad/010 |
| 134 | `unknown-wound-man` | `unknown-wound-man` | **year_raw** | *(none)* | fifteenth-seventeenth centuries | brookehitching_mad/010 |
| 135 | `unknown-crucifixion-diptych` | `unknown-crucifixion-diptych` | **year** | c.1460 | c. 1460 | brookehitching_mad/012 |
| 136 | `francesca-portrait-of-federico-da-montefeltro` | `francesca-portrait-of-federico-da-montefeltro` | **year** | c.1473-5 | c. 1473–1475 | brookehitching_mad/013 |
| 137 | `unknown-unicorn-tapestries` | `unknown-unicorn-tapestries` | **year** | 1495-1505 | 1495–1505 | brookehitching_mad/015 |
| 138 | `oreno-mona-vanna-the-nude-mona` | `oreno-mona-vanna-the-nude-mona` | **year** | c.1510 | c. 1510 | brookehitching_mad/016 |
| 139 | `burgkmair-triumphal-procession-of-emperor-maximilian` | `burgkmair-triumphal-procession-of-emperor-maximilian` | **year** | 1512-26 | 1512–1526 | brookehitching_mad/017 |
| 140 | `matsys-the-ugly-duchess` | `matsys-the-ugly-duchess` | **year** | c.1513 | c. 1513 | brookehitching_mad/018 |
| 141 | `unknown-st-christopher-dog-head` | `unknown-st-christopher-dog-head` | **year** | sixteenth-eighteenth centuries | *(none)* | brookehitching_mad/019 |
| 141 | `unknown-st-christopher-dog-head` | `unknown-st-christopher-dog-head` | **year_raw** | *(none)* | sixteenth-eighteenth centuries | brookehitching_mad/019 |
| 142 | `unknown-fool-s-cap-map-of` | `unknown-fool-s-cap-map-of` | **year** | c.1580-90 | c. 1580–1590 | brookehitching_mad/020 |
| 143 | `arcimboldo-the-composite-art-of-arcimboldo` | `arcimboldo-the-composite-art-of-arcimboldo` | **year** | 1563-c.1590 | c. 1563–1590 | brookehitching_mad/021 |
| 144 | `unknown-gabrielle-d-estrees-and-one` | `unknown-gabrielle-d-estrees-and-one` | **year** | c.1594 | c. 1594 | brookehitching_mad/022 |
| 145 | `dalem-the-legend-of-the-baker` | `dalem-the-legend-of-the-baker` | **year** | c.1550-1650 | c. 1550–1650 | brookehitching_mad/023 |
| 145 | `dalem-the-legend-of-the-baker` | `dalem-the-legend-of-the-baker` | **attribution** | *(none)* | after | brookehitching_mad/023 |
| 146 | `oliver-man-consumed-by-flames` | `oliver-man-consumed-by-flames` | **year** | 1600-10 | 1600–1610 | brookehitching_mad/024 |
| 147 | `unknown-portrait-of-barbara-van-beck` | `unknown-portrait-of-barbara-van-beck` | **year** | c.1650 | c. 1650 | brookehitching_mad/028 |
| 148 | `craesbeeck-the-temptation-of-st-anthony` | `craesbeeck-the-temptation-of-st-anthony` | **year** | c.1650 | c. 1650 | brookehitching_mad/029 |
| 149 | `unknown-angeles-arcabuceros-the-art-of` | `unknown-angeles-arcabuceros-the-art-of` | **year** | seventeenth century | *(none)* | brookehitching_mad/030 |
| 149 | `unknown-angeles-arcabuceros-the-art-of` | `unknown-angeles-arcabuceros-the-art-of` | **year_raw** | *(none)* | seventeenth century | brookehitching_mad/030 |
| 150 | `unknown-central-african-minkisi-power-figures` | `unknown-central-african-minkisi-power-figures` | **year** | seventeenth-twentieth centuries | *(none)* | brookehitching_mad/031 |
| 150 | `unknown-central-african-minkisi-power-figures` | `unknown-central-african-minkisi-power-figures` | **year_raw** | *(none)* | seventeenth-twentieth centuries | brookehitching_mad/031 |
| 151 | `unknown-typus-religionis` | `unknown-typus-religionis` | **year** | c.1700 | c. 1700 | brookehitching_mad/033 |
| 152 | `unknown-lucifer-s-new-row-barge` | `unknown-lucifer-s-new-row-barge` | **year** | c.1722 | c. 1722 | brookehitching_mad/034 |
| 153 | `mazzanti-joseph-of-cupertino-takes-flight` | `mazzanti-joseph-of-cupertino-takes-flight` | **year** | eighteenth century | *(none)* | brookehitching_mad/035 |
| 153 | `mazzanti-joseph-of-cupertino-takes-flight` | `mazzanti-joseph-of-cupertino-takes-flight` | **year_raw** | *(none)* | eighteenth century | brookehitching_mad/035 |
| 154 | `messerschmidt-the-ghost-heads-of-franz` | `messerschmidt-the-ghost-heads-of-franz` | **year** | 1770-83 | 1770–1783 | brookehitching_mad/037 |
| 155 | `goya-black-paintings` | `goya-black-paintings` | **artist** | Francisco Goya | Francisco de Goya | brookehitching_mad/041 |
| 155 | `goya-black-paintings` | `goya-black-paintings` | **year** | 1819-23 | 1819–1823 | brookehitching_mad/041 |
| 156 | `unknown-hikeshi-banten` | `unknown-hikeshi-banten` | **year** | nineteenth century | *(none)* | brookehitching_mad/042 |
| 156 | `unknown-hikeshi-banten` | `unknown-hikeshi-banten` | **year_raw** | *(none)* | nineteenth century | brookehitching_mad/042 |
| 157 | `comte-the-coronation-of-ines-de` | `comte-the-coronation-of-ines-de` | **year** | c.1849 | c. 1849 | brookehitching_mad/043 |
| 158 | `dadd-the-fairy-feller-s-master` | `dadd-the-fairy-feller-s-master` | **year** | 1855-64 | 1855–1864 | brookehitching_mad/044 |
| 159 | `repin-reply-of-the-zaporozhian-cossacks` | `repin-reply-of-the-zaporozhian-cossacks` | **year** | 1880-91 | 1880–1891 | brookehitching_mad/046 |
| 160 | `hausmann-the-art-critic` | `hausmann-the-art-critic` | **year** | 1919-20 | 1919–1920 | brookehitching_mad/050 |
| 161 | `houghton-georgiana-houghton-and-spiritualist-art` | `houghton-georgiana-houghton-and-spiritualist-art` | **year** | nineteenth-twentieth centuries | *(none)* | brookehitching_mad/051 |
| 161 | `houghton-georgiana-houghton-and-spiritualist-art` | `houghton-georgiana-houghton-and-spiritualist-art` | **year_raw** | *(none)* | nineteenth-twentieth centuries | brookehitching_mad/051 |
| 162 | `stace-the-eternity-of-arthur-stace` | `stace-the-eternity-of-arthur-stace` | **year** | 1932-67 | 1932–1967 | brookehitching_mad/054 |
| 163 | `hampton-the-throne-of-the-third` | `hampton-the-throne-of-the-third` | **title** | The Throne of the Third Heaven... | The Throne of the Third Heaven… | brookehitching_mad/055 |
| 163 | `hampton-the-throne-of-the-third` | `hampton-the-throne-of-the-third` | **year** | c.1950-64 | c. 1950–1964 | brookehitching_mad/055 |
| 164 | `unknown-the-getty-kouros` | `unknown-the-getty-kouros` | **year** | twentieth century | *(none)* | brookehitching_mad/059 |
| 164 | `unknown-the-getty-kouros` | `unknown-the-getty-kouros` | **year_raw** | *(none)* | twentieth century | brookehitching_mad/059 |
