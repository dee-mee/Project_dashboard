# Scheduling Automated Checks

This document explains how to set up automated uptime/SSL checks and expiry alerts for the Agency Dashboard.

## Available Management Commands

### `check_sites` - Uptime and SSL Monitoring
Checks all hosted websites for uptime and SSL certificate status.

```bash
python manage.py check_sites
```

**Options:**
- `--timeout SECONDS` - Connection timeout in seconds (default: 10)
- `--verbose` - Print detailed output for each site check

**Example:**
```bash
python manage.py check_sites --timeout 15 --verbose
```

### `check_expiry` - Domain and SSL Expiry Alerts
Checks for expiring domains and SSL certificates within a threshold.

```bash
python manage.py check_expiry --days 30 --email admin@example.com
```

**Options:**
- `--days DAYS` - Days threshold for expiry warnings (default: 30)
- `--email EMAIL` - Email address to send alerts to
- `--dry-run` - Run without sending actual alerts

**Example:**
```bash
python manage.py check_expiry --days 7 --email admin@example.com --dry-run
```

## Setting Up Scheduled Jobs

### Option 1: Cron Jobs (Linux/Mac)

Add these entries to your crontab (`crontab -e`):

```bash
# Check sites every 15 minutes
*/15 * * * * cd /path/to/agency_dashboard && /path/to/venv/bin/python manage.py check_sites

# Check expirations daily at 9 AM
0 9 * * * cd /path/to/agency_dashboard && /path/to/venv/bin/python manage.py check_expiry --days 30 --email admin@example.com
```

### Option 2: Windows Task Scheduler

1. Open Task Scheduler
2. Create a new task
3. Set trigger to run every 15 minutes for site checks
4. Set trigger to run daily at 9 AM for expiry checks
5. Action: Start a program
   - Program: `python.exe`
   - Arguments: `manage.py check_sites`
   - Start in: `d:\Users\Public\projjects\agency_dashboard`

### Option 3: GitHub Actions (for cloud deployment)

Create `.github/workflows/monitoring.yml`:

```yaml
name: Site Monitoring

on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes
    - cron: '0 9 * * *'    # Daily at 9 AM UTC

jobs:
  check_sites:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Check sites
        run: python manage.py check_sites
        env:
          DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
      
  check_expiry:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Check expirations
        run: python manage.py check_expiry --days 30 --email admin@example.com
        env:
          DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
          EMAIL_HOST: ${{ secrets.EMAIL_HOST }}
          EMAIL_PORT: ${{ secrets.EMAIL_PORT }}
          EMAIL_HOST_USER: ${{ secrets.EMAIL_HOST_USER }}
          EMAIL_HOST_PASSWORD: ${{ secrets.EMAIL_HOST_PASSWORD }}
```

### Option 4: Celery Beat (Production)

For production deployments, consider using Celery Beat for more robust scheduling:

1. Install Celery:
```bash
pip install celery redis
```

2. Create `dashboard/celery.py`:
```python
from celery import Celery
from django.conf import settings
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('agency_dashboard')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    from celery.schedules import crontab
    
    sender.add_periodic_task(
        crontab(minute='*/15'),
        'dashboard.management.commands.check_sites.Command().handle()',
        name='check-sites-every-15-minutes',
    )
    
    sender.add_periodic_task(
        crontab(hour=9, minute=0),
        'dashboard.management.commands.check_expiry.Command().handle(days=30)',
        name='check-expiry-daily',
    )
```

3. Update `config/__init__.py`:
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

4. Run Celery worker and beat:
```bash
celery -A config worker -l info
celery -A config beat -l info
```

## Email Configuration

For email alerts to work, configure these settings in `config/settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Your SMTP server
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'noreply@agencydashboard.com'
```

For development, you can use the console backend to see emails in the terminal:
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

## Monitoring Dashboard

The overview page already displays:
- Sites with expiring domains/SSL (within 30 days)
- Overdue invoices
- Recent activity

After setting up automated checks, this data will be kept current automatically.
