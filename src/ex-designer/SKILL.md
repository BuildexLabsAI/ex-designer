---
name: ex-designer
description: "Use when the user wants to keep developing an existing website in its current design as its new maintainer: their own site, or a client's site handed over with permission. Covers Finnish requests about continuing or looking after a site ('jatka <domain> kehitystä', 'ylläpidä saittia'), the names 'The Ex-Designer' and 'ex-designer' (and the old name 'snatcher'), and a project that already has tools/site.json or design/system.html. Also use when it is unclear whose site the user wants to continue: the ownership check comes first."
---

# The Ex-Designer: become a website's maintainer and keep its design

A maintainer handover ("takeover") is due diligence first and design second. Prove whose site it is, find what is
really live, freeze it, make the site's own token file the only place its design values live, and change it only
through a guarded loop. The site stays where it is, on its own platform.

## Rules

Breaking the letter of a rule is breaking the rule.

1. **Ownership before access.** Start with the intake questions. Until the ownership gate is passed, look at the
   site only as a visitor sees it: do not search this machine, its projects or the user's accounts for the site's
   code. (A session that starts inside the site's own takeover project, with its `tools/site.json`, passed the gate
   before.) The user's answer is not the proof. The proof is control: the user shows, with a session of their own,
   read-only access to the account that holds the site (the code repository, the hosting or the registrar). For a
   client's site, the written permission is saved as a file too. Showing control is the user's own act, with a session
   they already have; when there is none, say what counts as proof and wait. Every request of yours for access, an
   invite, a role or a sign-in, and every sign-in page you would open, waits until the gate is passed.
2. **No secrets travel.** Never ask for a password, API token or key: not in chat, not in a file, not "safely"
   through an environment variable, a secrets manager or a one-time link. Access comes from an invite or a role on
   the user's own account, or the owner signs in on their own machine.
3. **"Not mine" stops the takeover, not the audit.** A public, read-only audit is fine on any site. Until ownership
   is proven it keeps only findings: the scripts read pages in memory and no file of the site (HTML, CSS, scripts,
   images, fonts) is saved, not even for a while (a full report's logo follows the brand-audit skill's own intake).
   On "not mine, no permission": deliver the audit findings and stop. Copy, mirror, scrape, clone or rebuild nothing,
   and build no look-alike. Name the owner's written permission as the only way on, and plan nothing past it: no
   proof, sign-in or access steps for a site whose owner has not said yes.

4. **Read like a visitor until ownership is proven.** No port scans, admin-path or login probing, vulnerability
   scanners or load tests.
5. **Live first.** Ask the platform which version is deployed and which commit it came from, build that commit in a
   separate build folder, and prove the build equals the live site. Write this proof of source down. The repository,
   its `main` and a dev server are not the live site.
6. **Nothing in the site's repository changes before the baseline exists.** Until then every note (the intake, the
   gate record, `stack.md`, the proof of source), `site.json`, the backup and the baseline itself live in a takeover
   folder outside the repository. The baseline: a backup, screenshots of every page (3 identical runs) and the SEO
   facts of every URL and host.
7. **Own workspace.** The takeover branch `takeover/<name>` is a new worktree made from the latest remote `main`
   (fetched first). Never an existing checkout, never another person's branch, never `main` itself. When `main`
   differs from the deployed commit, list the difference and ask the owner before the first change: `main`'s
   undeployed work would ship with it.
8. **The site's tokens win.** The site's own token file stays the only source of design values. Audit opinions
   (taste skills, Material 3) are suggestions and never a change. Material 3 runs as its own check; only its
   "Broken" list becomes findings.
9. **A yes per step.** Nothing is pushed, deployed, published or sent without the user's explicit yes for that step.
   A yes for the preview is not a yes for production.
10. **Copy is not yours.** Notes to clients, page labels and the brand book go through the user's copy route (a
    copywriting skill, when installed). Code, plans and these files do not.
11. **The brand book records, never invents.** Every fact in it has a source that a script can resolve: the site's
    copy as read, the code, the token file, the audit or the owner's own words. Who the brand is (purpose, audience,
    position, values, story) comes only from the owner. A gap stays an open question.

## Flow

Talk in the user's language. One question per message; answers are digits. Files are in English.

| Step | What happens | Gate and output |
|---|---|---|
| 0 Intake | The URL; whose site (own, client, friend, prospect); audit form (findings only ★, or the full report) | answers |
| 1 Public audit | The brand audit (phases 1–4 of the user's brand-audit skill), the Material 3 check per host, the stack map, the audit report — `references/takeover.md` | `findings.md`, `findings.json`, `report.html`, `stack.md` |
| 2 Ownership | "Onko tää sun saitti? 1 oma · 2 asiakkaan, kirjallinen lupa · 3 ei" (in English: 1 mine · 2 a client's, written permission · 3 no). 3 → stop with the audit. 1 or 2 → proof by control | the dated gate record in the takeover folder |
| 3 Access | One row per system from `stack.md`: why, the safest way (invite or role), who holds it, a read-only proof | access rows in `stack.md` |
| 4 Source and safety net | The platform's deployed version → its commit → a build of that commit equals live; own worktree from the latest remote `main`; secrets scan; backup; baseline — `references/code-site.md` | in the takeover folder: the proof of source, `site.json`, `baseline/`, `seo.json` |
| 5 Design system | On the takeover branch: the notes go into the project's `DECISIONS.md`, `site.json` into `tools/`. The token file named in `site.json` stays the only source of design values; `tokens.py extract` and `tokens.py page` generate the rest | `design/tokens.json`, `design/system.html` (generated, never edited) |
| 6 Confirm | The owner reads `system.html` (what was found); you ask the `tokens.py questions` list in chat, one question per message, then the gaps as one list. Each correction is one sentence → the token file → extract again → confirm again | "kaikki oikein" (all correct) |
| 6b Brand book | "Tehdäänkö brand book? 1 kyllä · 2 ei" (and which brand, on a multi-brand site). On yes: read the site and its files into a source ledger, ask the owner only the gaps (one per message), checkpoint 1 (the brand platform and the chapter list), the book written through the copy route, build and check, checkpoint 2 (the full book) — `references/brand-book.md` | `brand/` (the kit: `README.md`, `brand-book.md`, `.html`, `.pdf`, `files/`), `brand-work/` (the ledger, never handed to makers); the owner's yes on the book |
| 7 Change loop | Token edit → the project's checks → `verify.py` → review page → yes → preview → yes → production → live check → rollback ready — `references/change-loop.md` | the owner's yes per step |
| 8 Handover | `CLAUDE.md`, `systems.md`, `system.html`, decisions, handoff; the scripts copied into `tools/`; the newcomer test — `references/change-loop.md` | a newcomer passes |

Sites built with a builder or exported from one (Framer, Webflow, WordPress, Wix, Squarespace) get steps 0–3 and a
row in `references/platforms.md`. Version 1 changes nothing on them, so steps 4–8 do not apply.

## Scripts

All read the project's `tools/site.json` (format in `references/code-site.md`); `--help` gives every option.

| Job | Command |
|---|---|
| The audit report | `python3 <skill>/scripts/report.py --findings data/findings.json --labels <report-labels.json> --lang fi --out report.html` |
| Design values, uses, coverage | `python3 <skill>/scripts/tokens.py extract --site tools/site.json --out design/` |
| The design system page | `python3 <skill>/scripts/tokens.py page --site tools/site.json --design design/ --labels <ui-labels.json>` |
| The owner's questions, for chat | `python3 <skill>/scripts/tokens.py questions --site tools/site.json --design design/ --labels <ui-labels.json>` |
| Screenshots, zero noise | `python3 <skill>/scripts/shoot.py --site tools/site.json --out baseline/shots --runs 3` (`--live` for the live site) |
| Pixel diff and review page | `python3 <skill>/scripts/diff.py <before> <after> --out review/` |
| SEO facts; local build against live | `python3 <skill>/scripts/livecheck.py seo --out seo.json` · `livecheck.py compare --seo seo.json` |
| Every check of one change | `python3 <skill>/scripts/verify.py --baseline baseline/ --design design/ --out review/` |
| The brand's copy and files, for the brand book | `python3 <skill>/scripts/brandbook.py read --work brand-work/` (`--live` for the live site) |
| The brand book's ledger and text against their sources | `python3 <skill>/scripts/brandbook.py check --work brand-work/` |
| The brand book kit: `.md`, `.html`, `.pdf`, README, files | `python3 <skill>/scripts/brandbook.py build --work brand-work/` |

The scripts block every request that is not the site, bind nothing outside 127.0.0.1, never read secret files, and
print where a value is (`file:line`), never the line around it.

## Red flags: stop and go back to the rule

| The thought | The rule |
|---|---|
| "It's their own site, they said so: go on." | The answer is not the proof. Ask for control (rule 1). |
| "They can put the password in an env var or a one-time link." | That is still a password handed over. Invite or role, or they sign in (rule 2). |
| "Not their site, so I refuse everything." | The public audit is fine; stop after it (rule 3). |
| "I'll build them a site in the same style instead." | A look-alike of someone else's site is a copy (rule 3). |
| "Clone the repo, run the dev server, that's the reference." | The repo is not what is live (rule 5). |
| "Small change, no baseline needed." | Every change needs the baseline (rule 6). |
| "I'll note the gate in the project's DECISIONS.md right away." | Notes wait in the takeover folder until the baseline exists (rule 6). |
| "Let me look for the site's repo on this machine first." | Not before the gate: intake questions first (rule 1). |
| "I'll just work in the existing checkout." | Own worktree from the latest remote `main` (rule 7). |
| "The audit says the type would be better in another font." | A suggestion. The site's tokens win (rule 8). |
| "Deploying is the obvious next step." | Only after the user's yes for that step (rule 9). |
| "The about page says what they value; I'll write the values from it." | Who the brand is comes from the owner. Ask (rule 11). |
| "There are no logo rules, so I'll add sensible ones." | A gap is an open question in the book, never a guess (rule 11). |
