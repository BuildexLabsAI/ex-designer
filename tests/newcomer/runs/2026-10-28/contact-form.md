# The contact form stopped sending: what to do now

How it works: the form on `/about/` posts to `/api/contact`, which sends through Mailroute to `hello@alpha.invalid`
(`systems.md`, row "Forms"). The Mailroute account belongs to the owner; the key `MAILROUTE_KEY` is a secret on Pilvi
Hosting and is never in the code, in chat or in a log.

## Now, in this order

1. **Read Mailroute's sending log** (the owner, or a team member the owner invites). Find the newest form send and
   note what Mailroute says about it:
   - **Refused, key invalid** → step 2.
   - **Over the monthly limit** (free plan: 100 mails / month) → nothing is broken; the owner decides between waiting
     for the next month and a paid plan. That costs money, so it is the owner's call.
   - **Bounced** → the mailbox side: check `hello@alpha.invalid` at Postilaatikko Mail and that the MX and SPF records
     resolve (`dig +short alpha.invalid MX`, `dig +short alpha.invalid TXT`).
   - **No send in the log at all** → the request never reached Mailroute: check that the site answers
     (`curl -sI https://alpha.invalid/` gives 200) and look at Pilvi Hosting's logs for `/api/contact`.
2. **Key invalid:** the owner makes a new key in Mailroute and puts it on Pilvi Hosting as `MAILROUTE_KEY`. The
   maintainer never sees the value. Nobody pastes it into chat, a file, a commit or a ticket.
3. **One test send, only after the owner says yes.** Then confirm it in Mailroute's sending log and in the
   `hello@alpha.invalid` inbox.
4. **Tell the owner** what failed, what was changed and when the test send arrived.

## Who does what

| Step | Who |
|---|---|
| Sending log, new key, paid plan, yes to a test send | the owner |
| DNS, hosting and log checks, the report | the maintainer |

## Do not

- Put the key, or any new key, in the code or the repository.
- Send test mails without the owner's yes.
- Change the site to "fix" it before the log says what failed: the pages have not changed since the takeover baseline,
  so the cause is most likely outside the code (key, limit or mail).
