# The Ex-Designer

A Claude Code skill (skill name `ex-designer`, formerly `snatcher`) that takes over an existing website and keeps
developing it in its current design: audit, ownership check, access, one source of design truth, a guarded change loop
and a handover.

## Status

Stages A, B and C of `docs/plan.md` are done (28.10.2026). The skill is installed on Esko's Mac as a link from
`~/.claude/skills/ex-designer` to `src/ex-designer/` of the main checkout, so a `git pull` on `main` updates it. The
local project folder keeps the old name, `~/Claude general/Projects/snatcher`. Plan checks 8, 9 and Esko's own change
(check 11) wait for a site that needs a real change. The pilot site is only a test site: no skill step waits on its
owners, its live deploy or its people.

The repository `BuildexLabsAI/ex-designer` is public and starts from one clean commit (29.10.2026). The build
history, pull requests #1–#13, the eval runs and their results stay in the private archive
`BuildexLabsAI/ex-designer-dev`.

## Read first

1. `docs/plan.md` — the flow, the files, the three build stages and the checks that mean done.
2. `handoff.md` at the repository root — the current state and the next action. It is gitignored, so it exists only
   on Esko's Mac and in no worktree.

## Commands

- Sanity check: `bash .github/scripts/check-standard.sh`
- Skill tests: `python3 tests/run_all.py` (about 8 minutes; opens the Mac's Google Chrome a few hundred times, no
  network). All 16 checks must pass.
- Newcomer test, a fresh agent and the handover kit of the invented site: `python3 tests/newcomer/newcomer.py run
  tests/newcomer/runs/<date>` (about 15 minutes; spends Claude usage). 4/4 jobs must pass.
- Eval, with and without the skill: `python3 tests/eval/run.py tests/eval/runs/<iteration>`, then
  `python3 tests/eval/judge.py tests/eval/runs/<iteration>` (Codex judges blind). It spends Claude and Codex usage. `tests/eval/runs/` is gitignored: its answers name the user.
- Denylist hashes, after a change to the local plain list `tests/denylist.txt` (gitignored, on Esko's Mac only):
  `python3 tests/denylist.py`.

- Install the skill (once per Mac): `mkdir -p ~/.claude/skills && ln -s "$PWD/src/ex-designer" ~/.claude/skills/ex-designer`
  from the main checkout; then start a new Claude Code session. A Mac that has the old link from before the rename
  removes it first: `rm ~/.claude/skills/snatcher` (a link only; no files are lost).

Add each command here when it exists and has run once.

## Project conventions

- **Layout.** The skill lives in `src/ex-designer/` (`SKILL.md` at its root). Only that folder is linked into
  `~/.claude/skills/ex-designer`; nothing else in the repository loads as part of the skill.
- **The site's confirmed tokens win.** Audit opinions, from the taste skills or from Material 3, are suggestions and
  never a change. Material 3 runs as its own check; only its "Broken" list becomes findings.
- **One token source.** On a site with code, its own token file stays the only place design values live. The skill
  generates `tokens.json` from it and never adds a second source.
- **No client data here.** The repository is public. Test fixtures and eval sites are invented; audits and pilots
  live in their own project folders. A real site, client or person is never named in a file, a commit message or a
  pull request; the pilot is "the pilot site". The denylist ships only as hashes (`tests/denylist.sha256`).
- **Who writes text.** Text a person reads (UI labels, brand books, notes to clients) is written by GPT through the
  copywriting skill. Code, specs, plans and these files are not.
- **Esko's yes first.** Nothing is deployed, pushed to a live site or sent to anyone without his explicit yes.
- **Secrets.** No password or key enters chat, a file or a log. Esko types them himself.
- **Merging follows CI.** If a check is red or cannot run, the agent opens the pull request and gives Esko the link.
  Esko then decides and merges it himself. If every check is green and the merge is agreed, the agent squash-merges it
  without a second confirmation from Esko.

<!-- buildexlabs-standard:start (copy of src/agents-block.md in BuildexLabsAI/.github; edit it there, not here) -->
## BuildexLabsAI repository standard

Every repository in the BuildexLabsAI organization follows these rules. The full version, with
the reasons, is CONTRIBUTING.md in the BuildexLabsAI/.github repository.

- **Layout.** The top level holds README.md, AGENTS.md, CLAUDE.md, DECISIONS.md, .gitignore,
  src/, tests/, docs/, scripts/, tool config files, and folders a tool requires at the root
  (such as public/ or supabase/). All code lives in src/. Inside src/ the framework's own
  convention wins: src/app/ for Next.js, src/<package>/ for Python.
- **Names.** Lowercase kebab-case (`athlete-model.md`) for the repository, the top level and
  everything in docs/. Everywhere: no spaces, no non-ASCII characters, and no two names that
  differ only by letter case. Inside src/, tests/ and scripts/, follow the language's own
  convention (`snake_case.py`, `Button.tsx`).
- **Never commit** secrets (.env files, keys, tokens). Media, documents and large files may go
  into git; GitHub itself refuses any file over 100 MiB. Small assets the app ships (icons,
  fonts, wasm) belong in src/ or public/.
- **Exceptions** go in `.github/standard-exceptions`, one path per line with its reason:
  `prisma  # Prisma reads its schema from a folder at the root`.
- **Branches.** Never commit to main directly. Name branches `feat/…`, `fix/…`, `docs/…`,
  `chore/…`, `refactor/…` or `test/…`. Agent tools' own prefixes (`claude/…`, `codex/…`) are
  accepted.
- **Commits and pull request titles** follow Conventional Commits:
  `feat(api): add athlete height endpoint`. Pull requests are squash-merged, so the title
  becomes the commit on main.
- **Decisions** that the code and git log cannot show go in DECISIONS.md, one dated line each.
- **README.md** is written with the readme-generator skill: its sections for the project type,
  plus the template's Run it locally, Deploy, Media and large files, First-time setup and Owner.
  Then the simple-english skill makes one Simplified Technical English (STE) pass over all prose,
  in its default mode. Run every command before it goes in and keep only the ones that work.
  Codex reviews it at high reasoning effort before it reaches main.
- **Check before you push:** `bash .github/scripts/check-standard.sh`. CI runs the same check
  on every pull request.
<!-- buildexlabs-standard:end -->
