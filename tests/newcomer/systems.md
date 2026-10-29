# Systems

Every system the site depends on: who holds it, how to get in without sharing a password, what it costs, when it
renews and how to check it works. Internal: this file is never deployed. Every name here is invented.

| System | What it does | Who holds it | Admin access | Cost and renewal | Health check |
|---|---|---|---|---|---|
| Domains `alpha.invalid`, `beta.invalid` | the addresses | Registrar Nimiö, the site owner | the owner signs in; auto-renew on | 15 € / year each, expire 2027-03-01 | `whois <domain>` shows the expiry |
| DNS | names, mail records | Nimiö DNS | team member role | included | `dig +short <domain> NS` |
| Hosting | serves both brands from one build | Pilvi Hosting, project `alpha-beta-site` | team member role | 0 € (free plan) | `curl -sI https://<host>/` answers 200 |
| Code | the source | this repository | collaborator | free | `git log -1` |
| Mail | receives `hello@alpha.invalid` | Postilaatikko Mail | the owner | 4 € / month | MX and SPF records resolve; a test mail only with the owner's yes |
| Forms | the contact form on `/about/` posts to `/api/contact`, which sends through Mailroute to `hello@alpha.invalid` | Mailroute, the owner's account | the owner invites a team member | 0 € up to 100 mails / month | Mailroute's sending log; a test send only with the owner's yes |
| Analytics and tags | none | — | — | — | — |
| Fonts and licences | Fixture Grotesk (self-hosted, SIL OFL), Fixture Icons | the owner | — | free | — |

## When something breaks

| Symptom | First check | Who fixes it |
|---|---|---|
| The site is down | `curl -sI https://<host>/`; Pilvi Hosting's status page | the maintainer |
| The contact form stopped sending | Mailroute's sending log (refused, bounced, over the monthly limit?); the key `MAILROUTE_KEY` is a secret on Pilvi Hosting, never in the code: if Mailroute says it is invalid, the owner makes a new key in Mailroute and puts it on Pilvi Hosting; then one test send, only with the owner's yes | the owner (key), the maintainer (checks) |
| A brand shows on the wrong host | `python3 tools/livecheck.py compare --site tools/site.json` | the maintainer |
| The domain expired | Nimiö, the owner's account | the owner |
