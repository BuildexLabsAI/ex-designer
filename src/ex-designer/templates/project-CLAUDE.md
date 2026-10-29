<!-- Added to the project's CLAUDE.md by the takeover. Fill each <…>, keep the project's own rules above this block:
     the takeover adds rules, it never replaces them. -->

## Design and publishing rules (takeover, <date>)

- **Design values live in one file:** `<token file>`. A new colour, font, size or radius becomes a token there
  first. `design/tokens.json` and `design/system.html` are generated: `python3 tools/tokens.py extract --site
  tools/site.json --out design/` and `python3 tools/tokens.py page --site tools/site.json --design design/
  --labels tools/ui-labels.json`.
- **Every change is checked before anyone sees it:** `<project checks>` and `python3 tools/verify.py --site
  tools/site.json --baseline baseline/ --design design/ --out review/ --expect-hosts <host>`. Show
  `review/diff/index.html` to the owner.
- **Publishing:** only from `main`, only with `<deploy command>`, only after the checks pass and the owner said yes
  to this deploy. Rebase on the latest remote `main` and check again right before it. A preview first:
  `<preview command>`.
- **After a deploy:** `python3 tools/livecheck.py compare --site tools/site.json --seo baseline/seo.json` must
  report no differences on every host.
- **Rollback:** `<rollback command>`, then `git revert <commit>`.
- **Every host, every check:** <hosts and the brand each one shows>. A change for one brand must not move another.
- **Baseline:** `baseline/shots/` is not in Git. Recreate it from commit `<baseline commit>` with
  `python3 tools/shoot.py --site tools/site.json --out baseline/shots --runs 3`; Chrome `<version>` made it, and a
  newer Chrome needs a new baseline from that commit.
- **Secrets:** no password, token or key in chat, files or logs; platform secrets stay on the platform.
- **Dependencies, owners, renewals:** `systems.md`.
