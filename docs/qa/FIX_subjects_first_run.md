# Subjects: first-run corrections

Generated subject strips and pointers now use bounded millisecond durations. The picks plan limits each line to three distinct subjects and directs the agent to omit incidental names. Visibility treats unknown locations as uncheckable, main-work shots as visible, and a frame mostly inside a subject region as visible. For another region of a person, the region's English `thing` must contain the subject's name or alias and one of face, head, or figure. This conservative explicit identity rule avoids inferring identity from position.

The unchanged real proposal and picks yield **65 warnings before, 43 after**. Old picks still contain incidental mentions, so the author in the opening line remains flagged; the prompt fix affects future picks rather than rewriting existing project data. These counts compare the same existing proposal, not a rerun of a model. The 43 remaining warnings (beat / subject / shot) are:

- b0130 / Jan van Eyck (jan_van_eyck) / s0001
- b0130 / Giovanni Arnolfini (giovanni_arnolfini) / s0105
- b0131 / Giovanni Arnolfini (giovanni_arnolfini) / s0106
- b0131 / Costanza Trenta (costanza_trenta) / s0106
- b0132 / two visitors (doorway_visitors) / s0111
- b0133 / two visitors (doorway_visitors) / s0214
- b0133 / Costanza Trenta (costanza_trenta) / s0214
- b0135 / Giovanni Arnolfini (giovanni_arnolfini) / s0218
- b0136 / Lucca to Bruges (lucca_to_bruges) / s0219
- b0136 / Giovanni Arnolfini (giovanni_arnolfini) / s0220
- b0138 / Costanza Trenta (costanza_trenta) / s0224
- b0139 / Costanza Trenta (costanza_trenta) / s0225
- b0140 / Costanza Trenta (costanza_trenta) / s0226
- b0142 / green wool gown (green_gown) / s0125
- b0145 / frilled white headdress (white_headdress) / s0234
- b0150 / red bed (red_bed) / s0242
- b0153 / Virgin Mary (virgin_mary) / s0248
- b0154 / window glass (glass_window) / s0250
- b0156 / red bed (red_bed) / s0253
- b0158 / Jan van Eyck (jan_van_eyck) / s0257
- b0159 / two visitors (doorway_visitors) / s0259
- b0159 / Jan van Eyck (jan_van_eyck) / s0259
- b0160 / two visitors (doorway_visitors) / s0260
- b0161 / Jan van Eyck (jan_van_eyck) / s0262
- b0165 / Christ (christ) / s0170
- b0166 / Christ (christ) / s0268
- b0167 / Christ (christ) / s0268
- b0167 / Costanza Trenta (costanza_trenta) / s0269
- b0169 / Costanza Trenta (costanza_trenta) / s0176
- b0172 / convex mirror (convex_mirror) / s0278
- b0177 / Saint Margaret (saint_margaret) / s0284
- b0177 / red bed (red_bed) / s0285
- b0178 / Saint Martha (saint_martha) / s0287
- b0179 / Jan van Eyck (jan_van_eyck) / s0289
- b0180 / Jan van Eyck (jan_van_eyck) / s0194
- b0181 / Jan van Eyck (jan_van_eyck) / s0291
- b0184 / Costanza Trenta (costanza_trenta) / s0299
- b0185 / tabard (tabard) / s0203
- b0185 / Costanza Trenta (costanza_trenta) / s0301
- b0187 / Diego Velázquez (diego_velazquez) / s0305
- b0187 / convex mirror (convex_mirror) / s0306
- b0187 / two visitors (doorway_visitors) / s0210
- b0188 / Giovanni Arnolfini (giovanni_arnolfini) / s0307

## Verification

- Windows snapshot: picks 486 passed; draft 616 passed; engine excluding slow 826 passed, 14 skipped, 166 deselected; auto 263 passed. The suites that use Starlette emitted one existing deprecation warning.
- Final focused checks after the last visibility change: visibility 23 passed, picks plan 44 passed, subject draft 35 passed.
- Mac Node: 501 passed, 1 skipped. All three generated-document checks passed.
- No model or media-generation calls were made. The real project and proposal were only read.
