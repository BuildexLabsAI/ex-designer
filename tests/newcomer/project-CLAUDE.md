# Alpha Studio and Beta Labs website (invented test site)

One build serves two brands and picks the brand by host: `alpha.invalid` shows Alpha Studio, `beta.invalid` shows
Beta Labs. Static pages in `public/`; the design values in `app/globals.css`. This site is invented for The Ex-Designer
newcomer test and is never deployed.

## Commands

- Serve the local build (needed by every check): `python3 tools/serve.py` (127.0.0.1:8787; stop it when done).
- Check a change: `python3 tools/verify.py --site tools/site.json --baseline baseline/ --design design/ --out review/
  --expect-hosts <host of the brand that should change>` (leave out `--expect-hosts` when every brand should change).

## Design and publishing rules (takeover, 2026-10-28)

- **Design values live in one file:** `app/globals.css`. A brand's own values sit in its block
  (`[data-brand="beta"]` for Beta Labs; `:root` is Alpha Studio and the default). A new colour, font, size or radius
  becomes a token there first, never a value in a component. `design/tokens.json` and `design/system.html` are
  generated: `python3 tools/tokens.py extract --site tools/site.json --out design/` and `python3 tools/tokens.py page
  --site tools/site.json --design design/`.
- **Every change is checked before anyone sees it:** the verify command above must pass. Show `review/diff/index.html`
  to the owner.
- **Publishing:** this test site has no hosting. On a real site: only from `main`, only with the documented command,
  only after the checks pass and the owner said yes.
- **Rollback:** `git revert <commit>` (never rewrite history), then the verify command again.
- **Every host, every check:** `alpha.invalid` (Alpha Studio) and `beta.invalid` (Beta Labs). A change for one brand
  must not move the other.
- **Baseline:** `baseline/shots/` is not in Git and is never re-shot to make a change pass; `baseline/shots/manifest.json`
  holds the hash of every shot.
- **Secrets:** no password, token or key in chat, files or logs; platform secrets stay on the platform.
- **Dependencies, owners, renewals:** `systems.md`.
