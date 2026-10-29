# A site with code: one source of truth, the safety net and the design system

Steps 4–6 of the flow, for a site whose code lives in a repository the user controls (gate passed).

## 4a · Find what is deployed

The repository's `main`, a local clone and a dev server are guesses. The live site is the fact.

1. **Fetch, never trust the local clone:** `git fetch --all --prune` (this updates remote branches only; it never
   switches anyone's checkout).
2. **Ask the platform which build is live:**
   - Cloudflare Workers: `npx wrangler deployments list --name <worker>` and `npx wrangler versions view <id>` (the
     message or tag may name the commit).
   - Vercel: `vercel inspect <url>` shows the Git commit of a deployment. Netlify: the deploy's log names it.
   - Nothing recorded: list candidate commits (the latest `main`, recent branches, tags) and go to step 3 for each.
3. **Prove it:** build the candidate commit in a separate build folder (`git worktree add <tmp>/build-<sha>
   <sha>`, removed afterwards), serve the build on 127.0.0.1, then
   `python3 <skill>/scripts/livecheck.py compare --site tools/site.json --out compare.json`. Equal means every static
   asset the pages load is byte-identical on every host, the SEO facts match and each host shows its own brand.
   Then `shoot.py --live` and `shoot.py` (local) with the same pages and sizes, and `diff.py` between them.
4. **Pages live that no branch has** (or assets that differ) mean the deployed build came from somewhere else: an
   unpushed branch, another machine, a build step with different inputs. Check the rebuild rows of `stack.md` first
   (live files Git lacks, build-time values, the release machine): a commit alone may not rebuild the site. Nothing
   changes until this is solved; ask the owner which commit was deployed and where the missing pieces are, and record
   the answer. When the owner cannot get them, the takeover stops after the audit and the access rows: name the
   missing pieces for the owner and change nothing.
5. **Write the proof of source** into the takeover folder (`source.md`), one line: `<date>: Deployed <platform>
   version <id> = commit <sha>; a local build of it equals live on <hosts> (livecheck compare: <n>/<n> assets
   identical, SEO facts equal; diff: 0 changed shots).` Without this line, nothing else starts.

## 4b · Own workspace and the publishing rule

- `git fetch origin && git worktree add <path> -b takeover/<name> origin/main`: the takeover branch always starts
  from the latest remote `main`. When `main` differs from the deployed commit (`git log --oneline <sha>..origin/main`),
  list the difference for the owner and ask before the first change, because `main`'s undeployed work ships with it.
- Never switch the main checkout's branch and never touch another person's branch; other sessions and people work
  there.
- The project's `CLAUDE.md` gets the rule (template `templates/project-CLAUDE.md`): deploy only from `main`, only with
  the documented command, only after the checks and the owner's yes.

## 4c · Secrets

`gitleaks git --redact --report-path <tmp>/gitleaks.json` (history) and `gitleaks dir --redact` (the working tree).
Report counts and file names to the user, never values. A finding is the owner's to rotate; the takeover never
uses it. Platform secrets (Worker secrets, environment variables) stay on the platform.

## 4d · Backup and baseline

- **Backup:** `git bundle create <takeover>/backup/<date>-<commit>.bundle <deployed-commit>` and a tarball of the
  build output. Both stay out of the repository.
- **`site.json`** (below) in the takeover folder, its `root` pointing at the build folder, then the deployed build
  served on 127.0.0.1 (a preview server binds 127.0.0.1 only and is stopped when the session ends).
- **Screenshots:** `python3 <skill>/scripts/shoot.py --site <takeover>/site.json --out <takeover>/baseline/shots
  --runs 3` covers every page × size × host × mode. A shot joins the diff suite only when its 3 runs are identical;
  for an unstable one, add the moving part's selector to `mask` and shoot again.
- **SEO facts:** `python3 <skill>/scripts/livecheck.py seo --site <takeover>/site.json --out
  <takeover>/baseline/seo.json` (status, trailing slash, title, description, canonical, robots, hreflang, sitemap,
  robots.txt per host).
- **Then, and only then, the repository:** on the takeover branch, `site.json` goes to `tools/` (its `root` set to
  `..`), the gate record and the proof of source into the project's `DECISIONS.md`, `baseline/manifest.json` and
  `baseline/seo.json` into `baseline/`. The screenshots stay out of Git (they are large; the manifest's hashes and
  the deployed commit recreate them).

### tools/site.json

```json
{
  "root": "..",
  "tokens": {"file": "app/globals.css", "sources": ["app/**/*.tsx", "components/**/*.tsx", "app/**/*.css"],
             "exclude": [], "docs": ["*.md", "docs/**/*.md"], "fonts": ["app/fonts/**", "public/fonts/**"]},
  "oneoffs": {"#1b3559": "selection highlight in dark mode"},
  "serve": {"url": "http://127.0.0.1:3000", "start": "npm run build && npm start"},
  "hosts": [{"name": "example.com", "brand": "Example", "expect": ["<title>Example"], "absent": ["Other Brand"]}],
  "pages": ["/", "/about/"],
  "sitemap": "/sitemap.xml",
  "sizes": ["390x844", "768x1024", "1440x900"],
  "modes": ["light", "dark"],
  "mask": ["[data-live-clock]"],
  "checks": ["npm run lint", "npm test"]
}
```

- `hosts`: every host the site answers on. On a site that picks its brand by host, `expect` holds a string only that
  brand's pages have and `absent` the other brands' strings: a default brand passes an `expect` check by accident, an
  `absent` check catches it.
- `sizes`: the site's own breakpoints (read them from the CSS or the Tailwind config), plus a phone.
- `modes`: `dark` only when the site has a dark mode.
- `context_names`: a name per token context for the design system page, such as
  `{"theme-v2/dark": "Brand A", "dark": "Brand B"}`, when a brand is a theme class rather than a host's own
  token block.
- `pages`: empty means every URL in the sitemap.
- `checks`: the project's own lint and test commands, one command each (no `&&`).

## 5 · Design system

- **The token file stays the only source.** On a code site it is the site's own file (`globals.css`, a theme file,
  a Tailwind config). The Ex-Designer never adds a second source; `design/tokens.json` is generated and never edited.
- `python3 <skill>/scripts/tokens.py extract --site tools/site.json --out design/` reads every context (base, dark
  mode, each brand, each brand in dark mode), counts every use in the sources (`file:line`), lists every value
  outside the tokens (hex, rgb(), Tailwind arbitrary values and palette classes, hard-coded fonts), flags colours
  within CIEDE2000 2 of each other, and names fonts that the docs or font files mention but no token uses.
- Coverage target: at least 98 % of colour and font uses go through tokens; every other value is a named one-off in
  `site.json` `oneoffs` (with its reason); no font is unexplained.
- `python3 <skill>/scripts/tokens.py page --site tools/site.json --design design/ --labels
  <skill>/templates/ui-labels.json --lang <en|fi>` → `design/system.html`: the system only. Each brand's key colours
  large, every used colour by role with one column per brand, the brands' fonts with their files, the type sizes,
  the corners and the readable text and background pairs. Its labels are copy, written once through the copy route
  into `templates/ui-labels.json`.
- **Not on the page:** values outside the tokens, tokens no code uses and the coverage share go to the audit report;
  the owner's questions and the gaps are asked in chat (step 6).

## 6 · Confirm

Open `system.html` for the owner (`open design/system.html`): that is the Found list. Then run `python3
<skill>/scripts/tokens.py questions --site tools/site.json --design design/ --labels <skill>/templates/ui-labels.json
--lang <en|fi>` and ask its Questions in chat, one per message, then its Gaps (roles a full system has: error, focus,
disabled, success, warning, border, muted text, link, surface, on-primary; never Material 3's style differences) as
one list. Each answer changes one thing:

- **A correction** ("the blue is wrong, the right one is #…"): edit the token file in the takeover worktree, extract
  again, make the page again, ask again.
- **A docs drift question** ("the docs say font X, the site uses font Y"): the code is the fact today; the owner
  decides which one is right, and the answer goes into the project's `DECISIONS.md`. A hand-written doc that
  disagrees is listed for the owner, never deleted by you.
- **A near-duplicate** ("these two greys differ by ΔE 1.2: merge?"): merging is a design change, so it waits for the
  change loop; the answer is recorded now.

The step ends with the owner's "kaikki oikein" (all correct). Then ask the brand book question (6b).
