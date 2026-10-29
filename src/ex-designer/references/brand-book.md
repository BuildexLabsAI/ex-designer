# The brand book (step 6b)

The design system covers the look. The brand book adds who the brand is and how it speaks, for the people who make
things for it: designers, marketers, developers and their AI tools. The test of the book: a maker who never met the
owner can make something that looks and sounds like the brand from the book and its files alone.

It records the brand that exists and invents nothing. Every fact in it has a source: the site, the code, the token
file, the audit or the owner's own words. A gap stays an open question. The standard is usable and exact, not long:
nine core chapters, optional chapters only where the brand has the material.

## When

After the owner's "kaikki oikein" on the design system (step 6), ask: "Tehdäänkö brand book? 1 kyllä · 2 ei". On a
site with several brands there is one book per brand, so ask next: "Kumman brändin brand book? 1 <brand> · 2
<brand>". The brand family chapter covers what the brands share.

## Where the files live

| Folder | Holds | Read by |
|---|---|---|
| `brand/` | the kit: `README.md` (the front page: find your job, take the file), `brand-book.md` (for AI tools), `brand-book.html` (the book), `brand-book.pdf` (an export), `files/` (logos and other brand files) | makers |
| `brand-work/` | `brand.json`, `ledger.json`, `capture.json` and `capture.md`, `book.md` (the book's source, with its marks), `readme.md` (the front page's source), the briefs | you and the owner; never handed to makers |

On a site with several brands each brand gets its own pair: `brand/<brand>/` and `brand-work/<brand>/`. Both folders
sit next to `design/` in the site's project, outside anything that is deployed (never in `public/` or the build
output). Until the baseline exists (rule 6) they live in the takeover folder. The kit is made by `brandbook.py build`
and never edited by hand: change the source, then build again.

## The four steps

### 1 · Read (none of the owner's time)

1. `python3 <skill>/scripts/brandbook.py read --work brand-work/` reads every page of the brand's hosts from the local
   build (`--live`: from the live site) into `capture.json`, and lists the brand files in the code: logos, icons,
   share images, web manifests. `capture.md` is the short version to read.
2. Read the material, raw, not summaries: `capture.md`; the brand files and the code that names the brand (a brand
   or site config, the metadata); `design/usage.json` and `design/system.html`; the audit's `findings.json`; the
   baseline screenshots. Hand-written design docs are claims to check against the code, never facts.
3. Write `ledger.json` (format below). The voice samples are the voice chapter's facts: the site's own words, quoted
   exactly, from several kinds of copy (headlines, buttons, form and error text, meta descriptions). The 3 to 5
   assets that make the brand recognisable go in as one observed fact: a hypothesis the owner confirms, never a
   finding (there is no survey data).
4. Write the gaps: every question only the owner can answer. Always the brand's purpose, audience, positioning and
   values (they are never read off a website), and the story if one is wanted; then logo rules that no file states,
   whether the font files may be shared with makers (their licence), and every conflict found (a doc against the code,
   one brand's name or colour on the other brand's pages).
5. `python3 <skill>/scripts/brandbook.py check --work brand-work/`: every source resolves. It also prints the ledger
   by chapter and the open gaps in order.

### 2 · Ask (the owner)

Ask the gaps in chat, one question per message, the most important first. Record each answer in the ledger word for
word (id, date, question, answer), set the gap's `answer`, and write the facts it gives as confirmed, with the answer
as a source. An observation the owner confirms becomes confirmed the same way.

**Checkpoint 1:** the brand platform (chapters 1 and 2, the voice traits) as a short draft written through the copy
route from the confirmed facts, and the chapter list: the nine core chapters and which optional ones apply. The
owner's yes before the book is written.

### 3 · Write

The book's words are copy (rule 10). Fill `templates/brand-book-brief.md` with the facts per chapter and send it
through the copy route; the result is `book.md` and `readme.md`. Then check every sentence against the ledger: a fact
without a mark, a quote that is not word for word, a value not in the token file, or a gap filled with a guess goes
back to the writer with the reason. You do not rewrite it yourself.

### 4 · Build and check

`python3 <skill>/scripts/brandbook.py build --work brand-work/` runs every check, and only then writes the kit and
runs the furniture check on every file in it. Open `brand/brand-book.html` for the owner (`open <path>`).

**Checkpoint 2:** the full book. The owner's yes. A later change goes into the ledger or `book.md`, then the build
runs again.

## The chapters

Core, always present, each holding facts or its open question:

| Id | Chapter | Holds |
|---|---|---|
| `on-a-page` | Brand on a page | the scope (which brand, which surfaces), a one-screen summary, the 3 to 5 recognisable assets, the top nevers |
| `who` | Who the brand is | what it does, for whom, why, its position in one sentence, its values: the owner's words only |
| `voice` | Voice | 3 to 5 traits, each with what it must not become; tone by context; a word list, with how the brand names itself and its products; do and don't pairs quoted from the site |
| `logo` | Logo | the existing files and versions, clear space, minimum size, misuse |
| `colour` | Colour | roles, exact values and readable pairs: generated from the token file |
| `type` | Typography | faces, fallbacks and sizes: generated from the token file |
| `imagery` | Imagery | what the site shows (photographs, illustration, icons, video); what to show and what to avoid |
| `in-use` | The brand in use | how the pages are composed today (from the baseline screenshots), the key patterns, real examples |
| `care` | Files and care | where every file lives, the token file as the only source of design values, how a change is made (the change loop), who approves, the version |

Optional, only when the brand has the material (at least one fact):

| Id | Chapter | When |
|---|---|---|
| `story` | Story | the owner has a story of their own: only their text |
| `signature` | Signature element | a recurring graphic device or object |
| `motion` | Motion and video | the site animates or uses video |
| `interface` | Interface | components and states matter to makers; it points to `design/system.html` instead of repeating it |
| `family` | Brand family | a site with several brands: what they share and what never crosses over |

The colour and type chapters always hold their generated specimens; the logo chapter shows every file in `files` whose
name says logo, mark, lockup, symbol or monogram. Never type a design value that is not in the token file: the check
stops the build.

## book.md

- One title line (`# `). Each chapter is `## <title> {#<id>}`, the core chapters in the order above. The title is
  copy; the id is fixed.
- A fact mark `[[<fact id>]]` or `[[<id>, <id>]]` follows the sentence it supports. Every paragraph, list item and
  table row carries at least one, or an open mark: a claim about the brand always names its source. A mark never
  stands alone.
- Quotation marks, double or single, are only for words the site or the owner really used, word for word: the quoted
  words stand in a source of a fact the same paragraph cites. A made-up counter-example (the "don't" of a do and don't pair) goes in
  italics, never in quotation marks.
- `[[open: G3]]` marks the paragraph that holds a gap's question. The book can ship with it; it never ships with a
  guess.
- `[[specimen: colour]]`, `[[specimen: type]]` or `[[specimen: logo]]`, on a line of its own, places a specimen in its
  chapter. Without the mark the specimen closes the chapter.
- `<!-- gate-allow -->` on a line lets it break the gate (the voice chapter has to spell its never-words out; a quote
  keeps the site's own punctuation). `<!-- furniture-allow -->` lets a line hold a word the brand's own text really
  uses (a founding date in the story). `<!-- value-allow -->` lets a paragraph name a colour or font the brand must
  never use, when a fact it cites quotes it ("never Comic Sans", from the project's design doc). Each covers its line's
  paragraph: in the built files, its words pass where that paragraph stands, nowhere else. A built file never grants
  itself an exemption.
- A picture comes from the kit: `![<what it shows>](files/<name>)`, its file named in brand.json `files` or
  `examples`. A link goes to a kit file, a place in the page, or an `http`, `https` or `mailto` address, written where
  it stands as `[text](target)`. No raw HTML: the kit's Markdown files are shown as HTML where makers open them.

The build removes the marks; the kit's `.md` gets the specimens as tables of exact values.

## brand.json

Paths are relative to the work folder. Template: `templates/brand.json`.

| Field | What it is |
|---|---|
| `brand` | the brand's name, as `site.json` hosts carry it |
| `site` | the project's `site.json` |
| `design` | the folder with `usage.json` (made by `tokens.py extract`) |
| `contexts` | the brand's token contexts in `usage.json`, the main one first (`["base", "dark"]`; on a theme-class brand its own context) |
| `kit` | the kit folder (`../brand`) |
| `hosts` | optional: the brand's hosts; else every host of `site.json` that carries the brand |
| `pages` | optional: the paths to read; else `site.json` pages, else its sitemap |
| `lang` | `en` or `fi`: the language of the page labels |
| `version` | the book's version number, shown at its end |
| `files` | `{"<kit name>": "<path in the site's code>"}`: logos and other brand files the kit ships. A font file only when its licence allows sharing (ask); otherwise the book names the font and the PDF embeds it |
| `examples` | `{"<kit name>": "<path in the baseline's shots>"}`: screenshots for the brand in use |
| `sample` | a fact id whose quote is the type specimen's sample line |
| `banned` | the brand's own never-words, added to the gate's list |
| `people` | names that never appear in the kit: the people who decide and do the work |
| `audit` | the audit's `findings.json` |
| `shots` | the baseline's screenshot folder |
| `context_names`, `roles`, `labels` | optional: brand names for contexts (default: `site.json`), role names for tokens (default: `design/roles.json`), the page labels file (default: `templates/brand-book-labels.json`) |

## ledger.json

```json
{"answers": [{"id": "A1", "date": "<yyyy-mm-dd>", "question": "…", "answer": "<the owner's words, exactly>"}],
 "facts": [{"id": "voice-cta", "chapter": "voice", "status": "observed", "fact": "<one sentence>",
            "sources": [{"kind": "page", "host": "<host>", "path": "/", "quote": "<the site's words>"}]}],
 "gaps": [{"id": "G1", "chapter": "who", "question": "…", "why": "…", "answer": "A1"}]}
```

A fact id is lower-case letters, digits and hyphens; answers are A1, A2, … and gaps G1, G2, …, in the order to ask
them. Every fact has at least one source, and each source resolves:

| Kind | Fields | Checked against |
|---|---|---|
| `page` | `host`, `path`, `quote` | the quote is on that page in `capture.json` (spaces and curly quotes aside) |
| `file` | `ref` (`<path>` or `<path>:<line>`), optional `quote` | the file is in the site's code, the line exists, the quote is in it |
| `token` | `ref` (a token name) | the token is in `usage.json` with a value for the brand |
| `finding` | `ref` (a finding id) | the finding is in the audit |
| `answer` | `ref` (an answer id), optional `quote` | the answer is in the ledger, the quote is in it |
| `shot` | `ref` (a path in the baseline's shots) | the screenshot exists |

Status: **confirmed** means the owner said it or said yes to it, so at least one source is their answer.
**observed** means it was read from the site, the code, the tokens or the audit, so at least one source is not an
answer. Facts of `who` and `story` are always confirmed: an observation about them is a gap, never a fact.

## The checks

`brandbook.py check` (exit 1 on any problem):

- **ledger, source, status:** the rules above; a gap's answer exists.
- **chapter:** one title; every chapter has a known id, once; the nine core chapters are there, in order; each holds
  a fact or an open question of its own chapter (colour and type always hold their specimens, logo its logo files);
  an optional chapter holds a fact of its own. A fact of another chapter may be cited anywhere, but it never fills a
  chapter.
- **mark:** every fact mark is a fact of the ledger; every open mark is a gap without an answer; a specimen mark sits
  in its own chapter, on its own line; every paragraph, list item and table row carries a mark. A fact cited in `who`
  or `story` is confirmed.
- **quote:** every quotation, in double or single marks, stands word for word in a source of a fact its paragraph
  cites.
- **colour, font:** read from the words a reader sees (a paragraph's lines joined, emphasis marks gone), every colour
  value (hex, `rgb()`, `oklch()`, … also written as an HTML entity, and named colours in code) and every font the book
  names (in any letter case) is the brand's own in the token file; the brand family
  chapter may also name the other brands' values. The font check knows the families of the site's design data and a
  list of common ones; a family it does not know passes, so the writer's brief and the fact check against the ledger
  have to stop it.
- **gate:** on the words a reader sees (emphasis marks gone, entities decoded): no em dash, no en dash except between
  two letters or digits (3–5), none of the banned words (common filler words and the brand's own `banned`).
- **link:** every picture is a file of the kit; every link a file of the kit, a place in the page, or an `http`,
  `https` or `mailto` address, also as Markdown renders it (nested brackets); no reference-style links, no raw HTML.
- **furniture:** no internal note that a maker would read: a date (also 10/28/2026 or "last updated"), a record of
  someone deciding ("was approved by", "Approved by …", and every name in `people`; a standing rule such as "changes
  must be approved by the brand owner" is fine), an approval, draft, review or decision note, a pointer to the decision
  log, the agent's notes or the work tools, a filler marker (TODO, TBD, lorem ipsum), an internal file of
  `brand-work/`, a local path, a path in code type that neither the kit nor the site's code has. A licence text in
  `files` (named `OFL`, `LICENSE`, `LICENCE` or `COPYING`, alone or with `.txt` or `.md`, in the site's code) ships as its authors wrote it: it is
  held to the bytes of that file instead.
- **files:** a kit file name is one plain name, and no file of the work folder or the kit is named for shipping.

`brandbook.py build` runs the check first and writes nothing when it fails, or when the kit folder holds anything but
the kit (a wrong `kit` path would overwrite someone's files). It makes the whole kit in a folder of its own next to
the kit, prints the PDF with Chrome cut off from the network, and runs the furniture check and the gate over every file
of it: the text files, the PDF's text, the text inside PNG files and the metadata of other pictures, the Exif folder
included (strip a camera's or an image tool's metadata before shipping). Every file must be what its name says, and a
picture must decode. Only then does the new kit take
the old one's place; a failed build leaves the kit as it was. Exit 2 when a file of the kit cannot be read.

## Not part of a takeover book

No new visual direction, mark or wordmark: the book records what exists. No history of how the look came about. No
platform specs or separate design files beside the kit's `.md` and the generated `tokens.json`. Out of scope: testing
routes on audiences, brand architecture across markets, sound, training, and a public usage page for partners and
press.
