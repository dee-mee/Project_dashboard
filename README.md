# Agency Dashboard

A Django app for tracking your clients, projects, hosted websites, and
invoices — with a dark analytics-style overview page (donut charts, revenue
trend, expiring domains/SSL, overdue invoices) plus filterable list pages.

Data entry happens through the built-in Django admin (`/admin/`); the
custom dashboard (`/`) is for viewing and reporting.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser  # your login for /admin/ and the dashboard
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` — you'll be redirected to log in, then land
on the overview.

### Optional: load demo data

To see the dashboard populated with realistic sample clients, projects,
hosted sites, and invoices:

```bash
python manage.py seed_demo
```

Run `python manage.py seed_demo --flush` to wipe and reseed.

## What's tracked

- **Clients** — name, company, email, phone, notes
- **Projects** — linked to a client, status (planning / active / on hold /
  completed), start/end dates, budget
- **Hosted websites** — linked to a project: domain, server provider, server
  IP, hosting plan, status (online / warning / offline), domain expiry date,
  SSL expiry date, last checked
- **Invoices** — linked to a client (and optionally a project): reference,
  amount, status (paid / pending / overdue — auto-flips to overdue past its
  due date), issued/due dates

## Structure

```
config/            Django project settings & root urls
dashboard/          the app: models, views, admin, urls
  management/commands/seed_demo.py   demo data generator
templates/          base.html + all page templates
static/css/          the dark theme stylesheet (dashboard.css)
```

## Before deploying

- Change `DJANGO_SECRET_KEY` (env var) and set `DJANGO_DEBUG=False`
- Set `DJANGO_ALLOWED_HOSTS` to your real domain(s), comma-separated
- Swap SQLite for Postgres/MySQL in `config/settings.py` `DATABASES` if you
  want something more production-grade
- Run `python manage.py collectstatic` and serve `staticfiles/` from your
  web server (or via WhiteNoise if you're on something like Render/Heroku)
- Change the seeded superuser password if you used `createsuperuser` with a
  weak one for testing

## Extending it

Ideas that fit naturally into this structure:
- A management command (or Celery task) that actually pings each hosted
  site's domain and updates `HostedWebsite.status` / `last_checked`
  automatically
- Email reminders when a domain or SSL cert is close to `domain_expiry_date`
  / `ssl_expiry_date`
- A CSV/PDF export for invoices
