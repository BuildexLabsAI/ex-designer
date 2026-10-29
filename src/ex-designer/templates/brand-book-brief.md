# Brief: the brand book of {brand}

Fill the parts in braces, then send this brief through the copy route. The writer returns two files: `book.md` and
`readme.md`.

## The book and its readers

{brand} is {one line from the confirmed facts: what it is}. This brand book is for the people who make things for
the brand and never met its owner: designers, marketers, developers and the AI tools they use. A reader opens the
chapter for their job, reads it in a few minutes, and can act on every sentence.

The book records the brand that exists. It invents nothing.

## Output

1. `book.md`: one title line (`# `), then the chapters below in this order. Write each chapter heading as
   `## <your title> {#<id>}` and keep the `{#<id>}` exactly.
2. `readme.md`: the kit's front page. A short title, one line on what the kit is, then one line per job (writing,
   design, development, AI tools, the logo) with a link to the file that job needs: `brand-book.html`,
   `brand-book.pdf`, `brand-book.md`, `files/<name>`. Only these files: {kit files}.

## Rules

- Use only the facts listed under each chapter. Add no claim, number, name, colour or font of your own.
- After each sentence that uses a fact, put its mark: `[[<fact id>]]`, or `[[<id>, <id>]]` for several. Every
  paragraph, list item and table row carries at least one mark.
- Quotation marks only around the words of a source listed with the facts, word for word. A made-up example of what
  not to write goes in italics, without quotation marks.
- Links go only to the kit's files (above), or to an http, https or mailto address; pictures only to the kit's
  files.
- A chapter with an open question says plainly what is not known yet and ends that paragraph with its mark
  `[[open: <gap id>]]`. Never fill a gap with a guess.
- The colour and type chapters get their values from a table the build adds: write what each colour and font is
  for, not the values. Name a colour value or a font only when it is in the facts. A paragraph that names a colour
  or font the brand must never use (quoted in its facts) starts with `<!-- value-allow -->`.
- Write in the brand's own voice as the voice chapter describes it, kept plain: short sentences, active voice,
  everyday words.
- No em dashes, and no en dash used as one. None of these words: {banned words}.
- No dates, no names of people who decided or worked on the book, no notes about how the book was made.
- As short as complete: no introductions, no summaries of what a chapter will say.

## Chapters and their facts

{For each chapter in the approved chapter list: its id, what it holds (references/brand-book.md), and its facts as
"<fact id>: <fact>" lines with their quotes; or its open question as "<gap id>: <question>".}
