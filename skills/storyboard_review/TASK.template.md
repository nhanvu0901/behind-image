# Review the storyboard as a viewer

Look at each supplied shot in order. The frames are labelled with the shot ID and the time within the video; the accompanying words are the speech heard during that shot, and the accompanying text is what appears on screen. Judge what a viewer can actually see at the moment the words are spoken. Do not infer that an object or person is visible from the narration or the filename. Use only the supplied material; do not invent facts.

For every shot, answer `ok` or list one or more problems, each with one of the following codes and a single sentence explaining the problem:

- `picture_mismatch`: The image does not show what the words are about at the time it is named or discussed. A person being introduced or discussed must be visible as a person, not merely a part of their body. A named thing must be visible and findable.
- `text_wrong`: On-screen text is wrong for what is shown, names a concept or book rather than the visible subject, or duplicates other text.
- `context_missing`: A name is used before the person has been presented, or a detail is mentioned without its meaning.
- `picture_repeated`: A picture is repeated for unrelated lines.

Return JSON only: `{"shots":[{"id":"shot-id","problems":[{"code":"picture_mismatch","detail":"One sentence."}]}]}`. A shot with no problem has an empty `problems` array. Include every supplied shot once. Only use the codes above. Do not propose facts or text absent from the supplied material.

For each shot, use each code at most once and keep every detail to 350 characters or fewer.
