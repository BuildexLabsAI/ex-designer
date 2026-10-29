# Systems

Every system the site depends on: who holds it, how to get in without sharing a password, what it costs, when it
renews and how to check it works. Internal: this file is never deployed.

| System | What it does | Who holds it | Admin access | Cost and renewal | Health check |
|---|---|---|---|---|---|
| Domain `<domain>` | the address | `<registrar>`, `<owner>` | `<owner>` signs in; renewal `<auto on/off>` | `<price>` / year, expires `<date>` | `whois <domain>` shows the expiry |
| DNS | names, mail records | `<provider>` | team member role | `<price>` | `dig +short <domain> NS` |
| Hosting | serves the site | `<platform and project>` | team member role | `<price>` | `curl -sI https://<host>/` answers 200 |
| Code | the source | `<repository>` | collaborator | free / `<plan>` | `gh repo view <repo>` |
| Mail | sends and receives `<domain>` mail | `<service>` | `<role>` | `<price>` | MX and SPF records resolve; a test mail only with the owner's yes |
| Forms | `<form>` sends to `<endpoint>` | `<service>` | `<role>` | `<price>` | the endpoint answers; a test send only with the owner's yes |
| Analytics and tags | `<tools>` | `<owner>` | `<role>` | `<price>` | the tag loads on the live page |
| Fonts and licences | `<fonts>` | `<owner>` | — | `<licence and renewal>` | — |

## When something breaks

| Symptom | First check | Who fixes it |
|---|---|---|
| The site is down | `curl -sI https://<host>/`; the hosting status page | `<who>` |
| The contact form stopped sending | the form endpoint's dashboard and its key on the hosting platform; the mail service's sending log | `<who>` |
| A brand shows on the wrong host | `python3 tools/livecheck.py compare --site tools/site.json` | `<who>` |
| The domain expired | the registrar account | `<owner>` |
