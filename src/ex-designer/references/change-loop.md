# The change loop and the handover

Steps 7 and 8, for a code site whose design system the owner has confirmed.

## 7 · One change ("muutos: …")

1. **Edit the token file** on the `takeover/<name>` branch. A change that needs a value outside the tokens adds a
   token first.
2. **Checks:** the project's own (`npm run lint`, `npm test`, its guards) and
   `python3 <skill>/scripts/verify.py --site tools/site.json --baseline baseline/ --design design/ --out review/
   --expect-hosts <host of the brand that should change>`. It fails on a new colour or font outside the tokens, a
   foreground/background pair that falls below 4.5:1, a pixel change on a host that should not move, new sideways
   overflow, a page that now answers an error, or a changed SEO fact.
3. **Review page:** `review/diff/index.html` shows only the shots that changed, the changed areas outlined. Show it
   to the owner and ask for a digit: 1 ship to preview · 2 change it · 3 drop it.
4. **Code review** of the change by a second model or person, then a **preview deploy** (the platform's own preview:
   `wrangler versions upload`, a Vercel preview, a Netlify deploy preview) and the same checks against the preview.
5. **Production** only after the owner's explicit yes for production. Use the project's documented deploy command,
   from `main`, after rebasing on the latest remote `main` and checking again.
6. **Live check:** `python3 <skill>/scripts/livecheck.py compare --site tools/site.json --seo baseline/seo.json`
   against the build that was deployed: every host carries its brand, every static asset is byte-identical to the
   build, the SEO facts are unchanged.
7. **Rollback ready:** the previous version comes back with the platform's rollback (`wrangler rollback`, a Vercel
   instant rollback, Netlify's publish of the previous deploy) plus `git revert`. Drill it twice on the first
   takeover of a site, and time it.

The contact form is never test-sent and no mail setting is changed without the owner's yes.

## 8 · Handover

The project must work without this skill and without you.

- `CLAUDE.md` from `templates/project-CLAUDE.md`: commands, the publishing rule, the token rule, traps.
- `systems.md` from `templates/systems.md`: every dependency from `stack.md` with owner, admin, cost, renewal date and
  a health check. Internal: never deployed. Renewals within a year and any auto-renew that is off are flagged.
- `design/system.html` and `design/tokens.json`, regenerated from the final token file.
- The project's `DECISIONS.md` and `handoff.md` brought up to date. Hand-written design docs that disagree with the
  code are listed for the owner; deleting them is the owner's call.
- The scripts copied into the project's `tools/` (`scripts/*.py` and `scripts/lib/`), with `tools/site.json`, so
  every check runs from the project.

**Newcomer test**, scored by a script: a fresh agent with only the project folder (1) changes one brand's accent
colour, (2) swaps a font, (3) rolls a change back, (4) answers "the contact form stopped sending: what now?" from
`systems.md`. Pass = 4/4 jobs, the checks green, no hints. Then the owner makes one change in a new session.

Offer, do not build: a weekly scheduled check of the live site (status, SSL and domain expiry, every brand).
