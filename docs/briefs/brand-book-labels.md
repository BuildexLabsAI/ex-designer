# Brief: the labels of the brand book page

You write two short interface texts of one generated web page. Return only one JSON object, nothing else.

## The page and its reader

The page is `brand-book.html`, a brand book that a script builds from a written book and a website's own design file.
It is set in the brand's own colours and fonts. Its readers make things for the brand and never met its owner:
designers, marketers, developers. Some readers have dyslexia: short words, plain language.

The page already has its other labels (colour groups, "Used for", text readability, font names, text sizes), written
before. You write only the two below.

## Output

One JSON object with two keys, `"en"` (English) and `"fi"` (Finnish). Each holds exactly the keys in the table.
Write the Finnish as a Finnish writer would write it, not as a translation. Plain and direct, sentence case, no
exclamation marks, no em dashes, no marketing words, no emoji.

Placeholders in curly braces are filled in by the script. Keep every placeholder of a key, spelled exactly as listed,
and add no others.

| Key | What it is | Placeholders | Max length |
|---|---|---|---|
| `version` | the last line of the book: which version of the book this is, for example "1.0" | `{version}` | 30 |
| `open` | a small tag above a paragraph that says something about the brand is not known yet and waits for the owner's answer | none | 25 |
