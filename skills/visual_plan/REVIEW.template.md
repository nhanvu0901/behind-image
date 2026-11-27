# Review the video as a viewer

Open every numbered contact sheet and read `shots.json`, including the spoken words, the moment's subject and reason, and the composer's notes. Decide whether a viewer can follow what is being said. Judge only what is visible and supported by the supplied words and sources.

For every shot write one entry in `out/review.json`: `{"shots":[{"id":"s1","problems":[]}]}`. Use an empty list when it works, otherwise at most one object with `code` and a short Vietnamese `detail`. The only codes are `picture_mismatch` (picture does not show what the words are about), `text_wrong` (on-screen text is wrong), `context_missing` (the viewer lacks needed context), and `picture_repeated` (the same picture returns without reason). Answer for every shot.
