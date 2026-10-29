# Plan: The Ex-Designer (formerly Snatcher) — a website-takeover skill + a pilot site

Approved by Esko on 27.10.2026. Every build stage continues this plan without a new approval; a change of scope goes
back to Esko.

Since 29.10.2026 this plan names `objective-brand-audit`, the public copy of the private brand-audit skill that the
build used. Both have the same phases 1–4 and write `data/findings.md`.

**Goal behind this:** anyone Esko hands a site to can own its design and upkeep after one guided run, without the
original builder, and without breaking what already works (mail, search rankings, forms, leads).

## Context

Esko wants to take over existing websites and keep developing them in their current design. No skill did this:

- **objective-brand-audit** audits a site, but has no Material 3 / WCAG step, no access step and no upkeep.
- **redesign-existing-projects** and **taste-redesign** overwrite fonts and colours with their own taste values.
- **An earlier redesign project** was a takeover that replaced the identity; it never proved ownership or wrote a rollback.

**Pilot site** — Esko's own test site; he confirmed his right to it in chat on 27.10.2026. Facts found
read-only on that day:

- **Why it suits a pilot:** the deployed version differs from the local repository, the site has its own token file
  and design guards, and one deploy serves more than one brand. Its stack, hosts and accounts are recorded in the
  pilot's own files, not here.

**A second site** (recon done, not Esko's): a Framer export on shared hosting. Its facts go into the platform
table and into the "not my site" test scenario. Nothing more is done with it.

## Deepen answers

1. **Pro move:** treat a takeover as due diligence + continuity first: find what is actually deployed, list every
   dependency (domain, DNS/mail, hosting, backends, forms, tracking, licences, renewals), freeze a baseline, then make
   one token file the only place design values live, guarded by a zero-noise visual diff and a live check.
2. **Raw material:** GitHub's latest `main` and the deployed Worker version, every file that defines or uses a design
   value (`globals.css`, components, guards), the live responses of every sitemap URL on both hosts, DNS/WHOIS. Not
   screenshots, not the audit's summary, not the stale local clone.
3. **Methods and tools:** Playwright against a local build of the deployed commit (both hosts via the Host header,
   light and dark, the site's own breakpoints) + numpy pixel diff; static extraction with usage counts and ΔE colour
   distance; a DTCG 2025.10 export generated from the token file; M3 + WCAG + axe as a separate check; the project's
   own lint and tests; gitleaks; wrangler preview + `wrangler rollback`; Codex review.
4. **Verify:** "Bigger work" check at the end; "Leaves the workshop" for anything live (Codex review + live check).
   Core tests: the local build of the deployed commit equals the live site; an unchanged rebuild shows 0 changed
   pixels; one token change shows only where it is used; a fresh agent with only the folder completes 4 upkeep jobs.

## Material 3: a separate check

Merging M3 into the brand audit would create a clash. The brand audit already judges design with
redesign-existing-projects' taste values; M3 brings its own scales. Two rulebooks give opposite "fixes", and the model
picks between them at random. So:

- **M3 stays a separate step** in The Ex-Designer. objective-brand-audit is not changed.
- **Only M3's "Broken" list becomes findings:** contrast, target size, focus, hover, overflow, reduced motion, axe
  WCAG faults. These are faults on any brand, so they cannot clash with the site's style.
- **"Differs from M3" is never an instruction.** It only feeds the completeness list ("a full system has an error
  colour, a focus style, a disabled state — this site lacks X").
- **One rule, in SKILL.md:** the site's confirmed tokens win. Audit opinions (taste or M3) are suggestions, never a
  change.

## Approaches considered

1. ★ **Platform-aware takeover skill (this plan).** Audit → ownership → access → one source of truth → design page →
   confirm → guarded change loop → handover. The site stays where it is. v1 runs the whole way for sites with code and
   a repo (piloted on the pilot site); builder and export sites get the audit, the access list and a platform-table row.
2. **Always rebuild into clean code** (most ambitious). For builder/export sites only a rebuild makes "as if they built
   it" literally true (the premortem reviewer's pick), but every takeover becomes weeks of migration with SEO risk. A
   per-site option, never the default.
3. **Figma as the design source.** Adds a tool Esko must run; Figma drifts from the live site.
4. **Hosted AI builder (Lovable).** Credits, lock-in, and single-page apps hurt SEO.
5. **Steward only** (audit + docs + monitoring, no changes). Safe anywhere, but nobody can change the site.

Bigger outcome, **not in this plan** (needs Esko's yes later): audit → takeover → monthly upkeep as a Buildex service.

## The skill's flow (what Esko experiences)

Chat in Finnish, one question per message, answers as one digit, each approval readable in 2 minutes. Files in English.

**0 · Intake** — the URL; whose site it is (own / client / friend / prospect); audit form (findings only ★ or the full
PDF report).

**1 · Public audit** — Gmail/Drive/Calendar/Slack off, no Claude in Chrome.
- **objective-brand-audit phases 1–4** → `data/findings.md`. Phases 5–8 (GPT copy, PDF) only if the full report was
  chosen.
- **M3 check:** `material-3/scripts/audit_web.py` on each host, after an HTTP status check → "Broken" into the findings.
- **Stack map:** a fixed checklist (`curl`, `dig`, `whois`, generator, scripts, forms, a network log of every
  third-party host) → `stack.md`, plus a row in the platform table: full support, or audit + access list only.
- No security probing before ownership is confirmed. Scripts read the HTML; Claude never loads whole pages.

**2 · Ownership gate** — "Onko tää sun saitti?" 1 mine · 2 a client's, I have written permission · 3 no.
- **3 → stop.** Deliver the audit. Nothing is copied, mirrored or published.
- **1 or 2 → proof by control:** access to the account that holds the site (for the pilot: the GitHub repo and the
  Cloudflare account). Written permission (client case) is saved as a file. Recorded in `DECISIONS.md` with the date.

**3 · Access** — from `stack.md`, one row per system: why, the safest way to grant it (invite or collaborator role,
never a password in chat), who holds it, and a read-only proof (e.g. `gh repo view`, `wrangler deployments list`).
Esko signs in himself where needed; Claude opens each page with `open <url>`. Notes to clients are written by GPT.

**4 · One source of truth + safety net**
- **Find what is deployed:** the live Worker version → its commit or branch. Build that commit locally and prove it
  equals the live site (static assets byte for byte; each page's SEO facts and screenshot).
- **Own workspace:** a git worktree from GitHub `main` on branch `takeover/pilot`. The main checkout and the other
  session's branch are never touched.
- **Who publishes:** Esko, his Codex branches and the takeover all touch this repo. Rule written into its `CLAUDE.md`:
  deploy only from `main`, only with the documented command, after the checks.
- **Secrets:** gitleaks scans the repo and its history; Worker secrets stay in Cloudflare.
- **Baseline:** every sitemap page × the site's breakpoints × both hosts × light/dark (where the site uses dark).
  Playwright serves the local build; trackers and third parties are blocked; a page joins the diff suite after 3
  identical runs.
- **SEO facts:** per URL and host — status, trailing slash, title, canonical, hreflang, robots, the sitemap →
  `seo.json`.

**5 · Design system**
- **Where the tokens live:** for a code site, its own token file (`app/globals.css`) is and stays the only source.
  The skill never adds a second one.
- `tokens.py extract` reads the token file (every mode: `:root`, `.dark`, brand) and every source file, and counts
  where each value is used. Values outside the tokens (hard-coded hex, Tailwind arbitrary values) are listed; colours
  within ΔE 2 are flagged as near-duplicates.
- → `design/tokens.json` (DTCG 2025.10), generated, never edited: input for `system.html` and for tools like Figma.
- `design/system.html`, generated: the system only (Esko 2026-10-27) — each brand's key colours, every used colour by
  role per brand, the brands' fonts, type sizes, corners and readable text pairs. Values outside the tokens, unused
  tokens and the coverage share go to the audit report. Its few labels are UI copy, written once by GPT.

**6 · Confirm** — Esko gets three short lists:
- **Found** — `system.html`: what each brand uses, with evidence.
- **Gaps** — in chat, as one list: what a complete system has but the site lacks (from the M3 completeness list).
- **Questions** — in chat, one per message (`tokens.py questions`): e.g. "the docs say font A, the site uses font B:
  which is right?", "these two greys differ by ΔE 1.2: merge?"
Each correction is one sentence ("väärä sininen, oikea on #…") → token file → regenerate → re-confirm.

**6b · Brand book** — asked right after "kaikki oikein": "Tehdäänkö brand book? 1 kyllä · 2 ei" (and, on a two-brand
site, which brand: one book per brand). The design system covers the look; the brand book adds who the brand is and
how it speaks. It documents the brand that exists and invents nothing. Built on the research in
`docs/research/brand-book-practice.md` and the proposal Esko approved on 28.10.2026; the skill's own text is
`src/ex-designer/references/brand-book.md`.
- **Goal:** a maker who never met the owner can make on-brand work from the book and its files alone.
- **9 core chapters**, always present, each holding facts or its open question: brand on a page (scope, a one-screen
  summary, the 3–5 recognisable assets as a hypothesis the owner confirms, the top nevers); who the brand is (the
  owner's words only); voice (traits, tone by context, a word list, do/don't pairs quoted from the site); logo; colour
  and typography (generated from the token file); imagery; the brand in use (from the baseline screenshots); files and
  care (where the files live, the token file as the only source, the change loop, who approves, the version).
- **5 optional chapters**, only with material: story (the owner's own text), signature element, motion and video,
  interface (points to `design/system.html`), brand family (multi-brand sites).
- **A source ledger** (`ledger.json`, internal, never handed to makers): each fact with its sources and its status,
  confirmed (the owner's answer backs it) or observed. Every source resolves by script: a page quote in the copy that
  `brandbook.py read` captured, `file:line` in the code, a token in `usage.json`, a finding in `findings.json`, the
  owner's answer word for word, a baseline screenshot.
- **Process:** 1 Read (Claude: capture, ledger, voice samples, the gap list) → 2 Ask (the owner, gaps only, one
  question per message) → **checkpoint 1** (the brand platform and the chapter list) → 3 Write (Claude briefs, GPT
  writes through the copywriting skill, Claude checks every fact against the ledger) → 4 Build and check →
  **checkpoint 2** (the full book).
- **Output:** the kit `brand/` (`README.md` front page "find your job, take the file", `brand-book.md` for AI tools,
  `brand-book.html` the main book in the brand's own colours and type, `brand-book.pdf` an export, `files/`) and the
  internal `brand-work/` (brand.json, the ledger, the capture, the book's source with its fact marks). Both in the
  site's project, outside anything deployed; in the takeover folder until the baseline exists.
- **Checks** (`brandbook.py check`, and `build` before it writes anything): the ledger, the chapters and marks, every
  colour and font against the token file for that brand, the gate (em dashes, banned words) and the furniture check
  (no internal notes) on the source and then on every file of the kit, the PDF's text included.
- **Gone from the first plan:** the `brand-skill` phases 2–4 and phase 5.5's diverge/kill/mutate rounds, the 17-chapter
  shape, the appendix "how the look was arrived at", iOS specs and a separate DESIGN.md; three checkpoints became two.
  Out of scope: route testing, brand architecture across markets, sound, training, a public usage page.

**7 · Change loop** — "muutos: …"
1. On the branch: edit the token file.
2. Checks: `npm run lint` + `npm test` (the project's own) + `verify.py` (pixel diff on every page, breakpoint, host
   and mode; contrast; sideways overflow; values outside the tokens; `seo.json` unchanged).
3. A review page with before/after and only the real changes outlined → Esko's digit.
4. Codex review → preview deploy → check → Esko's yes → production deploy.
5. **Live check:** both hosts carry the right brand; static assets byte-identical to the build; SEO facts unchanged.
6. **Rollback:** `wrangler rollback` to the previous version (seconds) + `git revert`. Drilled twice.

**8 · Handover**
- `CLAUDE.md` (for Claude: commands, rules, traps), `systems.md` (every dependency: owner, admin, cost, renewal, health
  check — internal, never deployed), `design/system.html`, `DECISIONS.md`, the project's `handoff.md`.
- Hand-written design docs that disagree with the code are listed for Esko; deleting them is his call.
- The scripts are copied into the project's `tools/`, so the project works without the skill.
- **Newcomer test**, script-scored: a fresh agent with only the folder changes one brand's accent colour, swaps a
  font, rolls a change back, and answers "the contact form stopped sending — what now?" from `systems.md`. Then Esko
  makes one change himself in a new session.
- **Offered, not built** (needs Esko's yes): a weekly scheduled check (live, SSL and domain expiry, both brands).

## Changes to existing skills

- **material-3** `scripts/audit_web.py`: check the HTTP status (today it audits a block page silently, and Cloudflare
  can block headless browsers) + a test. Its `tests/run_all.py` must pass. Public repo: pushing needs Esko's separate
  yes.
- **objective-brand-audit:** no change.

## Reuse — do not rebuild

| Need | Existing piece |
|---|---|
| Audit and findings | [`objective-brand-audit`](https://github.com/BuildexLabsAI/objective-brand-audit) phases 1–4 |
| M3 + WCAG + axe, animation freeze | `~/Claude general/Skills/material-3/scripts/audit_web.py` |
| Contrast maths | `material-3/scripts/lib/color.mjs` `contrastRatio()`; `scripts/lib/pixels.py` |
| Speed baseline | `objective-brand-audit/kit/perf.py --audit <dir>` |
| Design guards, tests, live title check | the pilot site's repository (`npm run lint`, `npm test`, `handoff.md`) |
| Blind eval judge | `~/Claude general/Skills/material-3-workspace/private/evals/judge.py` |
| Brand book chapters and process | `docs/research/brand-book-practice.md` and the approved proposal (replaces the `brand-skill` phases) |
| Brand book build, gate, furniture check | `~/Claude general/Projects/Buildex brand` (`source/book/build.py`: Chrome print to PDF; `tools/gate.sh`; `tools/furniture.py`, adapted from a repository's `git ls-files` to the kit folder) → `brandbook.py` |
| Brand book voice chapter, ledger statuses | the brand-voice plugin's `guideline-template.md` (we are / we are not, tone by context, terms) and `confidence-scoring.md` (sources behind each claim) |
| Gate's default banned words | the `plain-english` skill's hard list and the `copywriting` skill's named words |
| Brand book prose | `copywriting` skill (GPT writes, Claude checks) |
| Skill structure | `~/Claude general/Skills/material-3` (router SKILL.md, references/, scripts/, tests/run_all.py) |

## Files

**The Ex-Designer** — `~/Claude general/Projects/snatcher/` (the local folder keeps the old name), repo
`BuildexLabsAI/ex-designer`; the build history stays in the private archive `BuildexLabsAI/ex-designer-dev`. The skill is named `ex-designer`, renamed from `snatcher`
on 29.10.2026; its description triggers on its names, the old name "snatcher" and Finnish requests to continue or look
after a site.

```
README.md · AGENTS.md · CLAUDE.md (@AGENTS.md) · DECISIONS.md · .github/ (org standard) · docs/plan.md
src/ex-designer/   SKILL.md
                references/  takeover.md (stack checklist, ownership, access) · code-site.md · change-loop.md
                             brand-book.md (the brand book step: chapters, ledger, checks)
                             platforms.md (support table: Framer export, Framer-hosted, Webflow, WordPress, Wix/Squarespace)
                scripts/     tokens.py · shoot.py · diff.py · livecheck.py · verify.py · report.py · brandbook.py
                templates/   project-CLAUDE.md · systems.md · ui-labels.json · brand.json · brand-book-brief.md
                             brand-book-labels.json
tests/          run_all.py · fixtures/code-site/ (an invented site full of traps; no client data)
                fixtures/brand-work/ (an invented brand book of that site, planted with traps by run_all.py)
```

The skill sits in `src/ex-designer/` because the org standard keeps all code in `src/`. Only that folder is linked into
`~/.claude/skills/ex-designer`, so the repo's own files never load as part of the skill. Every change reaches `main`
through a pull request (org standard).

**Pilot** — a worktree of the pilot site's local clone on branch `takeover/pilot`: `design/`,
`baseline/`, `tools/`, `systems.md`, `seo.json`, additions to `CLAUDE.md` and `DECISIONS.md`. The project's root
`handoff.md` names the branch. The audit lives in `~/Claude general/Projects/Eskon Brand Audit/audits/<site>-<date>/`.

**Install (approved with the plan):** gitleaks — secret scanner, Homebrew (`brew install gitleaks`), free, about
20 MB. Why: scans the repo and its history for committed keys; grep misses most patterns. Everything else is already
on the Mac (Python Playwright 1.58 + browsers, PIL, numpy, node 22, gh, codex, wrangler via npx, skillspector).

## Build order — three build sessions

Each stage ends with `handoff.md` updated (facts only, never page text).

**Stage A**
1. **Failing test first:** two scenarios run by fresh agents *without* the skill, plan-only, no network — "take over
   the pilot site" (mine) and "take over a site that is not mine" (not mine). Assertions written before the runs; mistakes recorded.
2. In parallel: the material-3 patch · the skill (skeleton, scripts, fixture tests).
3. The same scenarios *with* the skill → every assertion passes; Codex judges blind.
4. Codex review of the scripts (max 2 rounds) → first pull request.
5. Pilot steps 0–6 on the pilot site: intake → audit + M3 → ownership → access proofs → source + baseline → design system
   → Esko's confirmation → the brand book question.

**Stage B** (new session): step 6b, the brand book. Esko answered "1 kyllä" on 27.10.2026 and asked for research
first and the professional standard, not length. The research (`docs/research/brand-book-practice.md`) and a proposal
followed; Esko approved the proposal on 28.10.2026 and gave the go-ahead to plan and build without waiting.

- **Goal behind this:** a maker who never met the owner can make on-brand work from the book and its files alone, and
  nothing in the book is invented.
- **Deepen answers:**
  1. Pro move: treat the existing brand as evidence. Record what the site really says and uses with its provenance,
     keep the owner's words apart from observations, and make every fact traceable by a script: a quote is checked
     against the page text that was read, never only cited.
  2. Raw material: the live copy of every brand page read by a script (title, meta, headings, text, buttons, image
     text), the brand files in the code, `design/usage.json` from the token file, `data/findings.json`, the baseline
     screenshots. Not the audit summary, not hand-written design docs (claims to check), not memory.
  3. Methods and tools: a JSON source ledger whose every source kind resolves mechanically (a page quote in the
     captured text, `file:line` in the file, a token in `usage.json`, a finding in `findings.json`, an answer in the
     ledger's word-for-word answers, a shot in the baseline); python-markdown; colour, type and logo specimens made per
     brand from `usage.json`, contrast from `lib/color.py`; Google Chrome headless print to PDF, checked with pypdf; the
     gate and furniture rules of the model book adapted to a brand folder; fixture tests with planted traps.
  4. Verify: "Bigger work" for the step, "Leaves the workshop" for the code that reaches `main`. `run_all.py` with a
     new check (the clean invented book builds `.md`, `.html` and `.pdf` and passes; each planted trap fails on its own
     rule), `check-standard.sh` and the CI-equivalent check, a look at the rendered fixture book, Codex's review at
     high effort (max 2 rounds). In the pilot, `brandbook.py check` passes on both brands' ledgers.
- **Steps:**
  1. The skill step: `references/brand-book.md`, the 6b row and the scripts table of `SKILL.md`,
     `scripts/brandbook.py` (`read`, `check`, `build`), the templates (`brand.json`, the GPT brief, the page labels
     written by GPT), fixture tests (check 15 of `run_all.py`).
  2. This plan (6b, the reuse table, check 12), `DECISIONS.md`, the research in `docs/research/`.
  3. Verify, Codex review, pull request. No CI job can start, so Esko merges it.
  4. Pilot step 1 "Read" for both brands: `brandbook.py read`, the source ledger (its voice facts are the voice
     samples), the gap list; `brandbook.py check` passes on both.
  5. With Esko, one question per message: which brand, the gap questions, checkpoint 1, then GPT writes, the build,
     checkpoint 2.
- **Done:** check 12 passes and the pull request is merged. Without Esko, everything up to his first answer.

**Stage C** (new session, scope cut by Esko on 28.10.2026): finish and ship the skill. No real deploy and no rollback
drill: the pilot tested steps 0–6b, `run_all.py` already tests step 7's scripts (`verify.py`, `livecheck.py`,
`diff.py`) on the invented site, and deploy and rollback are the platform's own commands. Nothing in Stage C touches
the pilot site or waits on its people.

- **Goal behind this:** a stranger installs The Ex-Designer and it works as installed, not only from this repository.
- **Deepen answers:**
  1. Pro move: test the skill the way users get it, through the symlink in a fresh session, and let the newcomer test
     be blind (a fresh agent, no hints) and scored by a script, never by the author.
  2. Raw material: the pilot's real stack run (`takeover/stack.md`, 28.10.2026) as evidence for the checklist fix;
     the invented site `tests/fixtures/code-site/`; the skill folder as `~/.claude/skills/snatcher` loads it (the name until 29.10.2026).
  3. Methods and tools: skillspector (`--no-llm`, flagged lines read), `claude -p` in a temp copy of the invented
     site for the newcomer test, a scoring script (git diff, `tokens.py extract`, `verify.py`, the answer against
     `systems.md`), `run_all.py`, `check-standard.sh`, Codex at high effort (max 2 rounds), readme-generator then
     simple-english.
  4. Verify: "Leaves the workshop" (code to `main`): every check below, Codex on the shipped code and the README.
- **Steps:**
  1. Skill fix from the pilot's stack run: the stack checklist (`references/takeover.md`) and step 4
     (`references/code-site.md`) also ask for files the live site serves that Git lacks, build-time values the
     release needs, the machine and command releases run from, and platform-managed files (such as a CDN's robots.txt).
  2. The newcomer kit on the invented site: `systems.md` from the template, the project `CLAUDE.md`, and the scripts in
     `tools/`; a scoring script and its check in `run_all.py` (a planted wrong answer fails); then one real blind run.
  3. skillspector on `src/snatcher/` (now `src/ex-designer/`) → clean (or each flagged line read and explained).
  4. README through readme-generator, one simple-english pass, every command run first, Codex review.
  5. Codex review of the code, pull request; Esko merges (no CI job can start). Then the symlink install
     `~/.claude/skills/snatcher` → `src/snatcher/` of the main checkout, and a smoke test in a fresh session ("snatcher"
     loads the skill and its first question is the intake). After the rename on 29.10.2026 the link is
     `~/.claude/skills/ex-designer` → `src/ex-designer/`.
  6. Cleanup: merged branches and worktrees, `git fetch --prune`, temp files; `handoff.md` rewritten.
- **Done:** `run_all.py` all pass (16 checks); newcomer 4/4 with 0 hints; skillspector clean; `check-standard.sh`
  passes; Codex rounds closed; the PR merged by Esko; the installed skill loads in a fresh session.
- **Out of this stage:** checks 8 and 9 (real deploy, rollback drills) and Esko's own change in a fresh session
  (check 11's second half) wait for a site that needs a real change.

## Where Esko acts (target: under 5 h of his time in total, the brand book included)

- **Stage A:** intake answers · the audit plan's yes · the ownership digit · sign-ins if a proof needs one (he types
  every password) · corrections on `system.html`, then "kaikki oikein" · the brand book digit · a yes before the
  material-3 patch goes to its public repo.
- **Stage B:** which brand · the gap questions (one per message) · checkpoint 1 (the brand platform and the chapter
  list) · checkpoint 2 (the full book) · merging the pull request.
- **Stage C:** merging the pull request. A real change, its production yes and his own change in a fresh session
  wait for a site that needs one (see Stage C).

## Landmines → built in as checks

- **Stale clone, busy repo.** Codex branches move `main` → always start from GitHub `main`; rebase and re-check right
  before any deploy.
- **Live ≠ repo.** Pages exist live that no local branch has → nothing changes until the deployed version is found
  and proven.
- **Two brands, one Worker.** Every check runs on both hosts; a token change for one brand must not move the other.
- **Approval fatigue.** Noisy diffs teach Esko to click yes → zero-noise harness; the review page shows real changes
  only; production moves only after his digit.
- **The project's own rules win.** Its `CLAUDE.md` ("do not reopen the framework, component system or typeface") and
  guards stay; the takeover adds, never replaces.
- **Mail and forms.** The contact form is never test-sent without Esko's yes; the open mail migration is out of scope.
- **Renewals.** A domain near its expiry date, or one with auto-renew off → `systems.md` flags it.
- **Secrets and sessions.** No password in chat or files; crawling and signed-in work never share a session; preview
  servers bind 127.0.0.1 and stop at the end.
- **Brand book invents things.** A model fills gaps with plausible claims → every fact needs a source that a script
  resolves (a quote must be on the page as read); who the brand is comes only from the owner; a gap stays an open
  question; the build refuses a book that fails a check.
- **Public repo.** No client data in the skill folder; a denylist test enforces it, and the denylist ships only as SHA-256 hashes.

## Done = these checks pass

1. **Skill tests:** `python3 tests/run_all.py` → all pass. Fixture traps: a colour in hex and rgb(), a Tailwind
   arbitrary value, a `.dark` block, a second brand, an asset name containing a hex code, a page that overflows
   sideways, a file with a dummy key. Checked: extraction finds every trap; no request leaves the machine; the overflow
   is caught; the dummy key never appears in output.
2. **Harness:** 0 differing pixels across 3 unchanged runs; a planted ΔE 2 colour shift caught 10/10.
3. **material-3:** `tests/run_all.py` → all pass after the patch.
4. **Eval:** with the skill every assertion passes (stops on "not mine", ownership before access, no password requests,
   finds the deployed version before any edit, baseline before any edit, no push without a yes); without it at least
   one fails. No client data in the skill folder; skillspector clean before install.
5. **Proof of source:** the deployed version is identified; its local build equals live on both hosts; gitleaks finds
   0 secrets.
6. **Tokens:** every colour and font use accounted for (≥ 98 % in tokens, the rest named one-offs; 0 unexplained
   fonts), both brands and both modes.
7. **One-token change:** the diff shows only where that token is used, on that brand only; contrast ≥ 4.5:1; lint and
   tests pass; no new WCAG AA failure.
8. **Deploy:** preview first; production live check passes on both hosts; deploy ≤ 10 min.
9. **Rollback:** drilled twice; the previous version is back within 5 min.
10. **Newcomer test:** 4/4 jobs, checks pass, 0 hints (`tests/newcomer/newcomer.py`, on the invented site); the scorer
    itself is `run_all.py` check 16.
11. **Esko:** "kaikki oikein" on `system.html`, and one change made by him in a fresh session.
12. **Brand book:** the 9 core chapters present, each holding facts or its open question; an optional chapter only
    where the brand has the material; every fact in the ledger with a source that resolves (the site, the code, the
    audit, the token file or the owner's answer); every colour and font in the book matches the token file for that
    brand; the gate and the furniture check pass; `.md`, `.html` and `.pdf` build; Esko's yes on the full book. In the
    skill: `run_all.py` check 15 (the invented book builds; each planted trap fails on its own rule).
13. **Codex:** the skill's scripts before the first pull request; the shipped change before production; the README
    (max 2 rounds each).
14. **Org standard:** `bash .github/scripts/check-standard.sh` passes and the standard-check CI is green on every pull
    request.

**What the pro targets cost:** the zero-noise harness (check 2) needs about 1–3 days of tuning, reused on every later
site; the rollback drills add hours, not days, because Workers roll back in seconds.

## Sources

[DTCG 2025.10 stable](https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/) ·
[Handover checklist](https://teklanhosting.co.uk/guides/migration-handover-checklist) ·
[Framer: no official export](https://www.framer.com/help/articles/can-i-export-my-website-to-html-and-self-host-it/) ·
[Hostinger Git deploy](https://docs.hostinger.com/websites/git) ·
[Hostinger account sharing](https://www.hostinger.com/support/1583777-how-to-share-access-to-your-account-at-hostinger/)
