# Brief: the labels of the design system page

You write the short interface text of one generated web page, and the questions an assistant asks in a chat about it.
Return only one JSON object, nothing else.

## The page and its reader

The page is `design/system.html`, a design system document a script makes from a website's own design file. It shows,
in this order: each brand's key colours as large colour bands; every colour the site uses, grouped by role, with one
column per brand; each brand's font, large, with its file; the other fonts and the text sizes; the corner sizes; and
which text and background pairs are easy to read. Nothing else: the page is a reference, not a report.

Two readers. A designer or developer who takes over the site and keeps the page open as the reference. And the site's
owner, who is not a designer and not a developer: they read the page once. After that, an assistant asks the owner a
few questions in a chat, one per message, built from the question templates below. Some readers have dyslexia: short
sentences, everyday words, one idea per sentence.

"Token" is a word the reader does not know. Say what it is in plain words (for example "design value" or "a value
saved in the design file"); keep one term for one thing across all labels.

## Output

One JSON object with two keys, `"en"` (English) and `"fi"` (Finnish). Each holds exactly the keys in the tables below
and the object `roles`. Write the Finnish as a Finnish writer would write it, not as a translation. Plain and direct,
active voice, sentence case, no exclamation marks, no em dashes, no marketing words, no emoji.

Placeholders in curly braces are filled in by the script. Keep every placeholder of a key, spelled exactly as listed,
and add no others.

### Page frame

| Key | What it is | Max length |
|---|---|---|
| `title` | the page title and main heading | 40 |
| `intro` | two sentences under the title: what this page is (the site's design values in one place, read from its own design file) and who it is for | 220 |
| `generated_from` | label before the design file's name | 30 |
| `commit` | label before the code version the page was made from | 25 |
| `date` | label before the date the page was made | 15 |
| `nav` | accessible name of the page's table of contents | 30 |

### Sections

| Key | What it is | Max length |
|---|---|---|
| `colours` | heading of the colours section | 20 |
| `colours_intro` | one sentence: colours are grouped by what they do; each brand has its own column | 160 |
| `band_background` | name on the large band of a brand's page background | 25 |
| `band_text` | name on the large band of a brand's main text colour | 25 |
| `band_muted` | name on the large band of a brand's quiet, secondary text colour | 25 |
| `band_accent` | name on the large band of a brand's accent colour | 25 |
| `role` | column heading: what a colour is for | 20 |
| `type` | heading of the fonts section | 20 |
| `type_intro` | one sentence: the fonts the site uses and its text sizes | 140 |
| `font_file` | label before the name of the font file a brand loads | 20 |
| `font_stack` | label before the list of fonts a browser tries in order (the font, then its fallbacks) | 25 |
| `defined_at` | label before the place in the design file where a brand's font is set | 25 |
| `families` | sub-heading: the other fonts the site uses | 30 |
| `scale` | sub-heading: the text size steps (headline, title, lead text...) | 30 |
| `specimen` | a sample sentence shown in each font and size: neutral, 6 to 9 words, every common letter shape | 60 |
| `shape` | heading of the corner sizes section | 30 |
| `shape_intro` | one sentence: how round the corners of buttons, cards and fields are | 140 |
| `contrast` | heading of the readability section | 40 |
| `contrast_intro` | one sentence: each pair of text colour and background colour, and whether it meets the 4.5:1 contrast the web accessibility rules ask for | 170 |
| `passes` | short verdict: the pair is easy to read | 25 |
| `fails` | short verdict: the pair is too faint | 25 |
| `context_base` | name of the default look when it has no brand name | 20 |
| `context_dark` | name of the dark mode | 20 |

### Colour groups: a heading (`g_…`, max 30) and one sentence under it (`e_…`, max 150)

| Group | What it holds |
|---|---|
| `g_surfaces` / `e_surfaces` | backgrounds: the page, cards, menus, quiet panels |
| `g_text` / `e_text` | text colours, each meant for a matching background |
| `g_brand` / `e_brand` | the brand's own colours: the main colour and its accents |
| `g_status` / `e_status` | colours that carry a meaning: error, warning, a decision or a research route |
| `g_lines` / `e_lines` | lines, borders, field outlines and the keyboard focus ring |
| `g_charts` / `e_charts` | colours of charts and graphs |
| `g_other` / `e_other` | colours that fit no group above |

### Chat questions: one sentence each, a question at the end

The assistant sends each one as its own message, so each must make sense alone.

| Key | The question | Placeholders | Max length |
|---|---|---|---|
| `q_near_duplicate` | two colours are so close a person can hardly tell them apart; should they be one? | `{a}`, `{b}` (each side's names), `{de}` (the difference as a number, 2 is barely visible) | 170 |
| `q_same_value` | two differently named values hold the exact same colour; on purpose? | `{value}`, `{tokens}` | 140 |
| `q_docs_font` | a document names one font, the site uses another; which is right? | `{font}`, `{where}`, `{tokens}` | 170 |
| `q_font_files` | the project holds font files for a font the site does not use; keep them? | `{font}`, `{where}`, `{tokens}` | 160 |
| `q_unexplained_color` | a colour is written straight into the code; make it a design value or keep it as a one-off? | `{value}`, `{count}`, `{where}` (up to three places) | 170 |
| `q_unexplained_font` | a font is written straight into the code; keep it? | `{font}`, `{where}` | 150 |
| `gap_missing` | one line of the list of roles a complete design system has and this site lacks (sent as one message) | `{role}` | 90 |

### `roles`: an object with exactly these keys, each a short plain name (max 30) of a role a complete system has

| Key | The role |
|---|---|
| `error` | the colour for errors and destructive actions |
| `focus` | the visible outline when a control has keyboard focus |
| `disabled` | the look of a control that cannot be used right now |
| `success` | the colour for success messages |
| `warning` | the colour for warnings |
| `border` | the colour of lines and borders |
| `muted text` | the colour of quiet, secondary text |
| `link` | the colour of links |
| `surface` | the colour of the page or card background |
| `on-primary` | the text colour on the main brand colour |

## Checks before you answer

- Valid JSON, two keys, each with every key of the tables above (`g_…` and `e_…` for all 7 groups) plus `roles`
  with its 10 keys, and no other keys.
- Every placeholder kept exactly; no new placeholders.
- Every value within its maximum length (placeholders count as their names).
- One term for "token" across all labels, in each language.
