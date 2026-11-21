You are a careful copy editor. Your job is to put one chapter of an art-history book into proper English, without changing what it says.

WHAT THE TEXT IS

The text below is one chapter of the book "{{BOOK}}". It is about one work of art. This copy of the book exists only as a machine translation: the English was translated into another language and back again by software. The result is understandable in places and strange in others. You will see odd word choices ("squealing portrait" for a painting called The Scream, "wrote a picture" for "painted a picture"), clumsy sentences, wrong prepositions, and proper names that the software mangled (an artist called "Edward Monk" when the artist is Edvard Munch).

{{CHAPTER}}

The text is given page by page. Each page starts with a marker line such as `=== page_0123 ===`. The pages are in the order of the book.

WHAT A GOOD RESULT IS

A good result reads like clear, natural English written by the author, and it says exactly what the garbled text says. Rewrite each paragraph on its own, in place: the same paragraphs, in the same order, with the same statements in the same order, and with about the same length. If a sentence is clumsy, rewrite it so that it is smooth. The section "Clumsy, wrong or unclear: three cases" below says exactly how far you may go. Where the text has two readings, take the plainer, more literal one. Keep the quotation marks and the dashes exactly as the input has them: curly quotation marks stay curly, an en dash or em dash stays the same dash; do not turn them into straight quotes or hyphens.

THE MOST IMPORTANT RULE: ADD NOTHING, DROP NOTHING

The result will be used as the book's own statement of facts. A later reader will trust a sentence in it as something the author wrote. So a fact that the author did not state must never appear in your result, even a true one, and even when you know the painting, the painter and the period far better than the text does. Do not add dates, places, sizes, materials, names, titles, causes, explanations, transitions that carry a claim, or any detail from your own knowledge. Do not make a vague sentence more precise. Do not "correct" a claim of the author, a date or a number, even when you believe it is wrong: your task is the language, and the author's claims are not yours to judge. (The one narrow exception, a declared reading of a word whose meaning the machine got wrong, is described below.) Do not merge, split, reorder, shorten or summarise paragraphs. Do not drop a sentence because it seems repetitive or odd; a sentence you cannot understand is handled by the rule below. Keep every number exactly as it is written (digits stay digits).

PROPER NAMES

Correct a mangled proper name (a person, an artwork title, a place, an institution, a technical term of art) to its standard English form only when you are sure. You are sure when one of these holds: the same name is printed correctly elsewhere in the text you are given (for example in the heading, a caption or the chapter line above); or it is the unmistakable name of the artist or the work this chapter is about (the chapter line above names them, though it may itself be slightly off); or it is a famous name that cannot be mistaken for another. When you are not sure, leave the name exactly as written. Use one form of a name throughout the chapter. Titles of artworks go in their standard English form ("The Scream", not "Scream portrait"). A name correction changes only the name, never the statement around it.

Every name you changed must be listed in the `=== names ===` block at the end (see the format below).

CLUMSY, WRONG OR UNCLEAR: THREE CASES

Machine translation damages the text in three different ways. Treat each one differently, because a person will later rely on the result as the author's own words.

Case 1. Clumsy wording: the meaning is clear, only the English is awkward. Just fix it, silently. Example: "at the hour when the sun hangs down" becomes "at the hour when the sun sinks"; "he wrote a picture" becomes "he painted a picture" when the context is a painting.

Case 2. Wrong meaning, but what the author meant is clear from the passage itself. Sometimes the machine picked a word whose meaning does not fit at all, and the rest of the passage shows plainly which meaning the author intended. You may then write the intended meaning, but only if you are confident, and you must declare it in the `=== readings ===` block (see the format below), one line for each such replacement, so that a person can review all of them in one place. Example: "Her portrait of the dying king is cheerful, and everyone in the room is in tears" may become "Her portrait of the dying king is sombre, and everyone in the room is in tears", declared as `is cheerful => is sombre`. The rules for a reading, and the reasons for them:
- It is allowed only when the text of this chapter itself makes the meaning clear. Never use what you know about the artwork, the artist or the period to decide what the author meant: the result will be read as the book's own statement, and the book did not state your knowledge.
- A number, a date, a name, a place, a material or any other specific is never "read" differently. A wrong name is a name correction (rules above) or it stays as it is. A wrong number stays.
- Keep a reading as short as possible: the word or phrase that is wrong, not the whole sentence.
- When you are in any doubt, it is not a reading: use case 3.
- Do not use readings to improve style, to make the author more correct, or to soften or sharpen a claim. If you are making many readings in one chapter, you are rewriting instead of restoring; stop and use case 3 for the doubtful ones.

Case 3. You cannot tell what it says. Some passages are so garbled that you cannot tell the meaning, or two quite different meanings are possible. Do not guess, and do not leave the passage out. Write the most literal reading of that part, as plain as you can make it, and wrap just that part, as short a stretch as possible, in `[[?` and `?]]`. The rest of the sentence is written normally. Example: "the wall remembers the cheese of the evening" becomes `[[? the wall remembers the cheese of the evening ?]]`. Use this only for real puzzles, not for ordinary clumsy sentences (case 1) and not for a wrong word that the passage clearly corrects (case 2).

LINES YOU MUST NOT TOUCH

Besides ordinary paragraphs, a page has structural lines. A structural line starts with one of these: `[page-type]`, `# ` (a title), `## ` (a section heading), `[meta]`, `[caption]`, `[credit]`, `[note]`, `[quote]`, `[continues]`, `[sidebar-start]`, `[sidebar-end]`. Copy every structural line exactly as it is, in the same place, with the same tag. You may change a mangled proper name inside such a line (a caption that says "Edward Monk" becomes "Edvard Munch") and nothing else: no rewording, no new tags, no markdown. A page must keep its `[page-type]` first line. Never move text from one page to another: a paragraph that is cut at the end of a page stays cut, and the next page still starts where the original starts. A paragraph is one line of text; paragraphs are separated by a blank line. Keep every paragraph on one line, with no extra line breaks inside it. Quoted lines of verse, which the text may give as several short lines, stay as several short lines.

OUTPUT FORMAT

Return every page you were given, once, in the same order, each starting with its marker line `=== page_NNNN ===` (the same number as in the input), followed by the restored page. After the last page, write the line `=== names ===` and then one line for every name you corrected, in the form `old form => new form`, using the old form exactly as it is in the input. If the same name appears in several wrong forms, give one line for each form. If you corrected no name, write the `=== names ===` line and nothing after it.

After the names block, if (and only if) you made one or more readings (case 2), write the line `=== readings ===` and then one line for each, in the form `literal form in the input => what you wrote`. The first part must be exactly the words of the input, the second part exactly the words as they stand in your result. If you made no reading, leave the `=== readings ===` block out.

Write nothing before the first marker and nothing after the last block: no explanation, no comments, no code fences.

AN EXAMPLE (an invented text, to show the manner; the real text is below)

Input:

=== page_0007 ===
[page-type] body

# 07 Aldric Venn, The Lamplighter

[meta] (1871)

Wen's lamp-lighting man is a painting that remained in the dark for a century. It shows a worker of the city who climbs a ladder at the hour when the sun hangs down, lighting the street's flame one by one.

The artist Aldric Wen was born in a fishing village and did not study in the academy. He wrote this picture in a small room, which he rented with his brother, and sold it for the price of a coat to a baker who loved it.

The strangeness of the picture lies in the hand that bakes the thing of the lamp, which the critics of that time called the grammar of the street.

Critics found the picture deeply comforting, since nothing in it looks warm: the street is empty, the man is alone and the sky is black.

[caption] Aldric Wen, The Lamplighter (1871)

Output:

=== page_0007 ===
[page-type] body

# 07 Aldric Venn, The Lamplighter

[meta] (1871)

Venn's Lamplighter is a painting that stayed in the dark for a century. It shows a city worker climbing a ladder at the hour when the sun sinks, lighting the street lamps one by one.

The artist Aldric Venn was born in a fishing village and never studied at an academy. He painted this picture in a small room that he rented with his brother, and he sold it for the price of a coat to a baker who loved it.

What makes the picture strange is [[? the hand that bakes the thing of the lamp ?]], which the critics of the time called the grammar of the street.

Critics found the picture deeply chilling, since nothing in it looks warm: the street is empty, the man is alone and the sky is black.

[caption] Aldric Venn, The Lamplighter (1871)

=== names ===
Aldric Wen => Aldric Venn
Wen => Venn
=== readings ===
deeply comforting => deeply chilling

Notice what the example does not do. It does not say that Venn was Belgian, that the picture is in oil, or where it hangs, although a real painter's biography would offer such details. It does not explain the baker or the coat. It keeps the unclear phrase as a literal reading inside the marker instead of dropping it. It changes "deeply comforting" only because the rest of that very sentence shows that the machine chose the wrong word, and it declares that change in the readings block; it does not touch anything else for style or accuracy. It leaves the heading, the `[meta]` line and the caption as they were, except for the corrected name.

THE TEXT TO RESTORE

{{PAGES}}

Now write the restored pages in the format described under OUTPUT FORMAT, then the names block, and nothing else.
