# Brief: the labels of the audit report

You write the short interface text of one generated web page. Return only one JSON object, nothing else.

## The page and its reader

The page is an audit report of a website. On the left: a full-page screenshot of one page of the site, with
numbered red markers on the places where something is wrong, and buttons to switch between the site's pages. On the
right: one numbered list of findings, with the same numbers as the markers. The list opens on the findings to fix
first; tabs switch it to all findings at once, to the severe, the moderate or the minor ones, or to the dropped
items: what the automatic Material 3 check flagged that a person checked and did not count as a fault, each with the
reason. Each finding shows its severity, a title,
its area (CRO, UX and accessibility, SEO, technical or data protection), where it is and how to fix it. A row of area
buttons narrows every list to one area.

Readers: the site's owner, who is not a developer, and the developer who fixes the findings. Some readers have
dyslexia: short, everyday words.

## Output

One JSON object with two keys, `"en"` (English) and `"fi"` (Finnish), each holding exactly the keys below. Write the
Finnish as a Finnish writer would, not as a translation. Plain and direct, sentence case, no exclamation marks, no em
dashes, no marketing words. Keep every placeholder of a key, spelled exactly, and add no others.

| Key | What it is | Placeholders | Max length |
|---|---|---|---|
| `title` | page title and main heading: an audit of the site | `{site}` | 50 |
| `checked` | line next to the title: the findings were checked on the live site on this date | `{date}` | 50 |
| `first` | tab: the findings to fix first | – | 25 |
| `high` | severity chip: severe | – | 15 |
| `medium` | severity chip: moderate | – | 15 |
| `low` | severity chip: minor | – | 15 |
| `high_count_one` | tab with the number of severe findings, when there is one | `{n}` | 20 |
| `high_count_other` | the same tab when there are several | `{n}` | 20 |
| `medium_count_one` | tab: one moderate finding | `{n}` | 20 |
| `medium_count_other` | tab: several moderate findings | `{n}` | 20 |
| `low_count_one` | tab: one minor finding | `{n}` | 20 |
| `low_count_other` | tab: several minor findings | `{n}` | 20 |
| `all` | tab: every finding at once, with their number | `{n}` | 20 |
| `dropped` | tab: the dropped items of the automatic Material 3 check, with their number | `{n}` | 20 |
| `dropped_intro` | one or two sentences at the top of the dropped list: an automatic Material 3 check flagged these items; each was checked on the live page and is not counted as a fault; the reason is under each | – | 170 |
| `reason` | label before why an item was dropped (end it as the language ends such a label) | – | 12 |
| `where` | label before the place of a finding (end it as the language ends such a label, e.g. a colon) | – | 12 |
| `fix` | label before how to fix it | – | 12 |
| `pages` | accessible name of the row of page buttons | – | 30 |
| `lists` | accessible name of the row of list tabs | – | 30 |
| `screenshot` | alternative text of a page's screenshot | `{page}` | 60 |
| `marker` | accessible name of a marker on the screenshot | `{n}`, `{title}` | 40 |
| `tick` | accessible name of a mark on the side rail that jumps to a marker | `{n}` | 30 |
| `no_place` | shown over the screenshot when the reader opens a finding that has no place on any page (DNS, analytics, search results); the finding's own "where" text follows it on the next line | – | 45 |
| `areas` | accessible name of the row of buttons that narrow the list to one area | – | 30 |
| `area_all` | area button: every area | – | 20 |
| `area_cro` | area tag: conversion rate optimisation, how a visitor becomes a lead and whether it is measured; the professional term, e.g. "CRO" | – | 20 |
| `area_ux` | area tag: user experience and accessibility (usability, WCAG); professional terms, e.g. "UX ja saavutettavuus" | – | 25 |
| `area_seo` | area tag: search visibility; the owner wants it to read "SEO" | – | 20 |
| `area_tech` | area tag: technical (performance, caching, security headers, e-mail authentication); the professional term | – | 20 |
| `area_privacy` | area tag: data protection and legal (GDPR, privacy notice, who runs the site); the professional term | – | 20 |

## Checks before you answer

- Valid JSON, two keys, each with exactly the keys above; every placeholder kept, none added; every value within its
  length (placeholders count as their names).
