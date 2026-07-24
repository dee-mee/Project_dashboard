import socket
import ssl
from datetime import datetime, timedelta
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import HostedWebsite


class Command(BaseCommand):
    help = 'Check uptime and SSL status for all hosted websites'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Connection timeout in seconds (default: 10)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print detailed output for each site check',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        verbose = options['verbose']
        
        self.stdout.write(f'Checking {HostedWebsite.objects.count()} hosted websites...')
        
        checked_count = 0
        updated_count = 0
        errors = 0
        
        for site in HostedWebsite.objects.all():
            checked_count += 1
            old_status = site.status
            
            try:
                # Check uptime
                domain = site.domain
                if not domain.startswith(('http://', 'https://')):
                    domain = f'https://{domain}'
                
                parsed = urlparse(domain)
                hostname = parsed.hostname or parsed.path
                
                # Try to connect to check if site is up
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                
                port = 443 if parsed.scheme == 'https' else 80
                result = sock.connect_ex((hostname, port))
                
                if result == 0:
                    # Connection successful, check SSL if HTTPS
                    if parsed.scheme == 'https':
                        try:
                            context = ssl.create_default_context()
                            with socket.create_connection((hostname, 443), timeout=timeout) as sock:
                                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                                    cert = ssock.getpeercert()
                                    
                                    # Extract expiry date from certificate
                                    if cert and 'notAfter' in cert:
                                        expiry_str = cert['notAfter']
                                        # Parse certificate expiry date
                                        expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z').date()
                                        site.ssl_expiry_date = expiry_date
                                        
                                        # Check if SSL is expiring soon
                                        days_left = (expiry_date - timezone.now().date()).days
                                        if days_left <= 7:
                                            site.status = HostedWebsite.STATUS_WARNING
                                        else:
                                            site.status = HostedWebsite.STATUS_ONLINE
                            site.last_checked = timezone.now()
                        except ssl.SSLError as e:
                            if verbose:
                                self.stdout.write(self.style.WARNING(f'SSL error for {site.domain}: {e}'))
                            site.status = HostedWebsite.STATUS_WARNING
                            site.last_checked = timezone.now()
                        except Exception as e:
                            if verbose:
                                self.stdout.write(self.style.WARNING(f'SSL check error for {site.domain}: {e}'))
                            site.status = HostedWebsite.STATUS_ONLINE
                            site.last_checked = timezone.now()
                    else:
                        # HTTP site, just check if it's up
                        site.status = HostedWebsite.STATUS_ONLINE
                        site.last_checked = timezone.now()
                else:
                    # Connection failed
                    site.status = HostedWebsite.STATUS_OFFLINE
                    site.last_checked = timezone.now()
                
                sock.close()
                
            except socket.gaierror:
                # DNS resolution failed
                site.status = HostedWebsite.STATUS_OFFLINE
                site.last_checked = timezone.now()
                if verbose:
                    self.stdout.write(self.style.ERROR(f'DNS resolution failed for {site.domain}'))
                errors += 1
            except socket.timeout:
                site.status = HostedWebsite.STATUS_OFFLINE
                site.last_checked = timezone.now()
                if verbose:
                    self.stdout.write(self.style.ERROR(f'Timeout checking {site.domain}'))
                errors += 1
            except Exception as e:
                if verbose:
                    self.stdout.write(self.style.ERROR(f'Error checking {site.domain}: {e}'))
                errors += 1
                continue
            
            # Save if status changed
            if site.status != old_status:
                updated_count += 1
                if verbose:
                    self.stdout.write(
                        f'Updated {site.domain}: {old_status} -> {site.status}'
                    )
            
            site.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Checked {checked_count} sites, updated {updated_count} statuses, {errors} errors'
            )
        )
