# Sources (v2 long-form episode)

## Text sources
1. **Book chapter** (primary): James Payne, *Great Art Explained*, chapter 2, pages 23-35 (local PDF, `assets/chapter2_text.txt`). Facts and argument only; no run of 6+ words reused (see n-gram check).
2. **National Gallery, London - The Arnolfini Portrait page**: https://www.nationalgallery.org.uk/paintings/jan-van-eyck-the-arnolfini-portrait (fetched 2026-11-14; local text copy `v2/refpages/national_gallery_arnolfini.txt`).
   - Used for: dimensions 82.2 x 60 cm and medium (oil on oak) for the AN-05 annotation; the wall inscription "Johannes de Eyck fuit hic 1434"; the mirror showing two visitors (one possibly Van Eyck, "unproven"); the later Berlin portrait of a man of the family; paint applied freely in places, thumbprint near the dog's shadow; the NG's cautious "Giovanni(?)" attribution of the sitters.
3. **Wikipedia - Arnolfini Portrait**: https://en.wikipedia.org/wiki/Arnolfini_Portrait (fetched 2026-11-14 via the MediaWiki extracts API; local copy `v2/refpages/wikipedia_arnolfini_portrait.txt`).
   - Used for: the competing readings (marriage-contract reading vs memorial reading), uncertainty over which Arnolfini and which wife, the lit candle read as the eye of God or a marriage custom, Velazquez and Las Meninas.
4. No paid API, no YouTube material. The channel's local episode and effect excerpts are used only as measurements.

## Copyright check
`scripts/ngram_v2.py` compares `v2/script.txt` with the book chapter and with both reference pages (lowercase, punctuation stripped). Result: longest shared run 5 words with every source (`v2/ngram_check.txt`).

## Images (all downloaded from Wikimedia Commons with a generic User-Agent; PD / CC0 only, no CC BY needed)
Main painting and comparison (already used in v1): Van Eyck, Arnolfini Portrait scan (https://commons.wikimedia.org/wiki/File:Van_Eyck_-_Arnolfini_Portrait.jpg, 4386x6000, Public domain); Van Eyck, Virgin and Child with Canon van der Paele (https://commons.wikimedia.org/wiki/File:Jan_van_Eyck_069.jpg, 4169x3249, Public domain). Book PDF details (pages 25, 26, 30, 31, 32) are public-domain painting details.

Context images (all Public domain or CC0; none needs CC BY / CC BY-SA attribution):

| Key | Work, label used, chapter | Author (Commons credit) | Licence | Size | Source page |
|---|---|---|---|---|---|
| ghent | Ghent Altarpiece - Jan van Eyck, 1432 - Merchant City | Jan van Eyck / Presumably Hubert van Eyck | Public domain | 6265x4581 | https://commons.wikimedia.org/wiki/File:Lamgods_open.jpg |
| giovanni_berlin | Man in a Red Chaperon (Berlin, later portrait of the man) - Jan van Eyck, c.1438 - The Arnolfinis | Jan van Eyck | Public domain | 2872x4000 | https://commons.wikimedia.org/wiki/File:Jan_van_Eyck_(um_1390-1400_-_1441)_-_Portrait_of_a_man_(from_the_Arnolfini_family^)_Around_1440_-_523A_-_Gemäldegalerie.jpg |
| durer | Self-Portrait - Albrecht Dürer, 1500 - The Alchemist | Albrecht Dürer | Public domain | 4130x5710 | https://commons.wikimedia.org/wiki/File:Albrecht_Dürer_-_1500_self-portrait_(High_resolution_and_detail).jpg |
| meninas | Las Meninas - Diego Velázquez, 1656 - The Alchemist |  | Public domain | 3475x4000 | https://commons.wikimedia.org/wiki/File:Las_Meninas_(1656),_by_Velazquez.jpg |
| blue_cap | Man in a Blue Chaperon - Jan van Eyck, c.1430 - Merchant City | Jan van Eyck | Public domain | 4956x7442 | https://commons.wikimedia.org/wiki/File:Jan_van_Eyck_-_Man_in_a_Blue_Cap_(c.1430).jpg |
| turban | Man in a Red Turban - Jan van Eyck, 1433 - Merchant City, The Alchemist | Jan van Eyck | Public domain | 2024x2746 | https://commons.wikimedia.org/wiki/File:Portrait_of_a_Man_in_a_Turban_(Jan_van_Eyck).jpg |
| rogier | Portrait of a Woman with a Winged Bonnet - Rogier van der Weyden, c.1435 - Fashions and Fabrics | Rogier van der Weyden | Public domain | 4464x6645 | https://commons.wikimedia.org/wiki/File:Rogier_van_der_Weyden_-_Portrait_of_a_Woman_with_a_Winged_Bonnet_-_Google_Art_Project.jpg |
| matsys | The Moneylender and his Wife - Quentin Massys, 1514 - The Mirror (a later convex mirror) | Quinten Metsys | Public domain | 1680x1581 | https://commons.wikimedia.org/wiki/File:Massysm_Quentin_—_The_Moneylender_and_his_Wife_—_1514.jpg |
| bruges | Grote Markt, Bruges (etching) - Rijksmuseum, 20th c. - Merchant City | Rijksmuseum | CC0 | 3320x2790 | https://commons.wikimedia.org/wiki/File:Grote_Markt_in_Brugge,_RP-P-1943-188.jpg |
| tomb | Tomb of Mary of Burgundy, Bruges (effigy with a dog at her feet) - late 15th c. - The Arnolfinis (dog at the feet of a woman's effigy) | Jacob Jonghelinck / Jan Borreman II (sculptors of the tombs, 1500s; the photograph is marked public domain on Commons) | Public domain | 5171x3447 | https://commons.wikimedia.org/wiki/File:Brügge-Liebfrauenkirche-Prunkgräber_DSC0166.jpg |

The tomb photograph is marked Public domain on Commons; its credit line names the 16th-century sculptors of the tombs (Jacob Jonghelinck, Jan Borreman II / Renier van Thienen), not a photographer. It was found on the second Commons search (with CC BY and CC BY-SA allowed); no CC BY or CC BY-SA file was needed.

## Music and voice
Music: numpy-synthesised pad and room tone generated locally on the server (`v2/server/audio_job2.py`), no external file. Voice: local Chatterbox (machiavelli_ref.wav), same settings as v1.
