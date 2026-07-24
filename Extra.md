Roadmap: what's next

What we have now is the CRUD + reporting layer: models, admin for data entry, and a dashboard for viewing it. Everything below is what turns this from "a nice internal tool" into something an agency actually runs day-to-day on. Roughly ordered by how much it matters.

1. Automation (highest priority)

Right now every field is updated by hand — you set a site's status to "offline" yourself, you type in expiry dates manually. Without automation, the dashboard is only as accurate as your last manual update.

A scheduled job (Celery beat, or a management command run on a cron / via a scheduled GitHub Actions workflow) that actually pings each HostedWebsite.domain and updates status + last_checked
Email or Slack alerts when a site goes down, or when a domain/SSL cert is within N days of domain_expiry_date / ssl_expiry_date
2. Multi-user access & permissions

There's currently one superuser and no concept of teams or clients logging in themselves.

Staff accounts per team member (scoped permissions — not everyone needs delete access)
A client-facing login where a client sees only their own projects/invoices/sites, not the whole book of business
An audit log of who changed what and when (who marked an invoice paid, who updated a site's status)
3. Real billing

Invoice tracks status, but there's no way to actually get paid from it.

PDF invoice generation you can send to a client
Payment integration (Stripe / PayPal / M-Pesa) so status flips to paid automatically instead of by hand
Recurring/subscription billing for ongoing hosting retainers, not just one-off invoices
4. Production hardening

Beyond the "before deploying" checklist above:

Move off Django's dev server to gunicorn/nginx or a platform (Render, Railway, etc.)
Enforce HTTPS
Error tracking (Sentry) so you hear about a 500 before a client does
5. Operational texture

Smaller but genuinely useful additions:

Time tracking per project (billing hours, not just a flat budget)
File attachments — contracts, signed proposals, screenshots
A notes/comments thread per project so context doesn't live in someone's inbox
Search across clients, projects, and domains
6. Tests

There's no test suite yet, despite CI being wired up to run one. Worth prioritizing model logic first (e.g. Invoice.save()'s auto-overdue behavior, the *_days_left properties on HostedWebsite) then view-level tests for the filtered list pages.

Suggested build order

If tackling this incrementally: automated uptime/SSL checks + alerts first — it's the single highest-value addition, since it's the difference between a dashboard you have to remember to check and one that tells you when something's wrong. Then tests (so you don't break what you just built), then multi-user access, then billing, then the rest.