from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from dashboard.models import HostedWebsite


class Command(BaseCommand):
    help = 'Check for expiring domains and SSL certificates and send alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Days threshold for expiry warnings (default: 30)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send alerts to (required for email alerts)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending actual alerts',
        )

    def handle(self, *args, **options):
        days = options['days']
        email = options.get('email')
        dry_run = options['dry_run']
        
        self.stdout.write(f'Checking for expirations within {days} days...')
        
        today = timezone.now().date()
        threshold = today + timedelta(days=days)
        
        # Check domain expirations
        expiring_domains = HostedWebsite.objects.filter(
            domain_expiry_date__lte=threshold,
            domain_expiry_date__gte=today
        )
        
        # Check SSL expirations
        expiring_ssl = HostedWebsite.objects.filter(
            ssl_expiry_date__lte=threshold,
            ssl_expiry_date__gte=today
        )
        
        domain_count = expiring_domains.count()
        ssl_count = expiring_ssl.count()
        
        if domain_count == 0 and ssl_count == 0:
            self.stdout.write(self.style.SUCCESS('No expirations found within threshold'))
            return
        
        # Build alert message
        message_lines = []
        
        if expiring_domains.exists():
            message_lines.append(f'\n=== EXPIRING DOMAINS ({domain_count}) ===')
            for site in expiring_domains:
                days_left = (site.domain_expiry_date - today).days
                message_lines.append(
                    f'{site.domain} - expires in {days_left} days ({site.domain_expiry_date})'
                )
        
        if expiring_ssl.exists():
            message_lines.append(f'\n=== EXPIRING SSL CERTIFICATES ({ssl_count}) ===')
            for site in expiring_ssl:
                days_left = (site.ssl_expiry_date - today).days
                message_lines.append(
                    f'{site.domain} - SSL expires in {days_left} days ({site.ssl_expiry_date})'
                )
        
        message = '\n'.join(message_lines)
        
        self.stdout.write(message)
        
        # Send email alert if configured
        if email and not dry_run:
            subject = f'Agency Dashboard: {domain_count + ssl_count} expiring items'
            try:
                send_mail(
                    subject,
                    message,
                    'noreply@agencydashboard.com',
                    [email],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f'Alert sent to {email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send email: {e}'))
                self.stdout.write(self.style.WARNING('Configure EMAIL settings in config/settings.py or use --dry-run'))
        elif dry_run:
            self.stdout.write(self.style.WARNING('Dry run - no alerts sent'))
        else:
            self.stdout.write(self.style.WARNING('No email configured - use --email to send alerts'))
