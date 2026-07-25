# Deployment Guide

This guide covers deploying the Agency Dashboard to production.

## Prerequisites

- Python 3.11+
- PostgreSQL database (recommended for production)
- Nginx web server
- Gunicorn WSGI server
- SSL certificate (Let's Encrypt recommended)

## Environment Variables

Set the following environment variables in production:

```bash
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database (if using PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost/dbname

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Stripe Payment Integration
STRIPE_SECRET_KEY=sk_live_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Sentry Error Tracking
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
```

## Installation Steps

1. **Install Dependencies**
```bash
pip install -r requirements.txt
pip install gunicorn psycopg2-binary  # Additional production dependencies
```

2. **Run Migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

3. **Collect Static Files**
```bash
python manage.py collectstatic --noinput
```

4. **Create Superuser**
```bash
python manage.py createsuperuser
```

5. **Configure Gunicorn**

Copy `gunicorn_config.py` to your server and adjust paths as needed.

Start Gunicorn:
```bash
gunicorn -c gunicorn_config.py config.wsgi:application
```

Or use systemd service (recommended):
```ini
[Unit]
Description=Agency Dashboard Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/agency_dashboard
ExecStart=/path/to/venv/bin/gunicorn -c /path/to/gunicorn_config.py config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

6. **Configure Nginx**

Copy `nginx.conf` to `/etc/nginx/sites-available/agency_dashboard` and:
- Update domain names
- Update SSL certificate paths
- Update static/media file paths
- Create symlink: `ln -s /etc/nginx/sites-available/agency_dashboard /etc/nginx/sites-enabled/`
- Test config: `nginx -t`
- Reload: `systemctl reload nginx`

7. **Set Up SSL with Let's Encrypt**

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

8. **Configure Stripe Webhook**

Set up a webhook endpoint at `https://your-domain.com/stripe-webhook/` in your Stripe dashboard to receive payment events.

## Scheduled Tasks

Set up automated monitoring using GitHub Actions (already configured in `.github/workflows/monitoring.yml`) or use cron:

```bash
# Check sites every 15 minutes
*/15 * * * * cd /path/to/agency_dashboard && /path/to/venv/bin/python manage.py check_sites

# Check expirations daily at 9 AM
0 9 * * * cd /path/to/agency_dashboard && /path/to/venv/bin/python manage.py check_expiry --days 30 --email admin@yourdomain.com
```

## Monitoring

- **Sentry**: Error tracking is configured and will send alerts for 500 errors
- **Health Check**: Access `/health/` endpoint to verify server status
- **Logs**: Check Gunicorn logs at `/var/log/agency_dashboard/` and Nginx logs at `/var/log/nginx/`

## Security Checklist

- [ ] Set strong `DJANGO_SECRET_KEY`
- [ ] Enable HTTPS with SSL certificate
- [ ] Configure firewall (allow only 80, 443, 22)
- [ ] Set up regular database backups
- [ ] Enable `DEBUG=False` in production
- [ ] Review and update dependencies regularly
- [ ] Configure CORS if needed for API access
- [ ] Set up log rotation for Gunicorn and Nginx logs

## Backup Strategy

```bash
# Database backup
pg_dump dbname > backup_$(date +%Y%m%d).sql

# Media files backup
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/

# Upload to S3 or other storage
aws s3 cp backup_$(date +%Y%m%d).sql s3://your-backup-bucket/
```

## Troubleshooting

**Server won't start:**
- Check Gunicorn logs: `tail -f /var/log/agency_dashboard/error.log`
- Verify database connection
- Check port 8000 is not in use

**Static files not loading:**
- Verify `collectstatic` was run
- Check Nginx static file paths in config
- Verify file permissions

**Stripe payments failing:**
- Verify API keys are correct
- Check webhook endpoint is accessible
- Review Stripe dashboard for error logs

**Monitoring not working:**
- Verify GitHub Actions secrets are set
- Check management commands run manually first
- Review cron job logs

vlNIEm~_m}-aiasK
