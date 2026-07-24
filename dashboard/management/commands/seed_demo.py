import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Client, HostedWebsite, Invoice, Project

CLIENTS = [
    ("Amref Health Africa", "Amref Health Africa", "info@amref.example"),
    ("Nairobi Textiles Co.", "Nairobi Textiles", "hello@nairobitextiles.example"),
    ("Borderlands Programme", "PRBP Secretariat", "contact@prbp.example"),
    ("COMESA Competition Commission", "COMESA CCC", "admin@comesacompetition.example"),
    ("Elewa Art Studio", "Elewa Art", "team@elewaart.example"),
    ("Savanna Logistics", "Savanna Logistics Ltd", "ops@savannalogistics.example"),
]

PROJECT_NAMES = [
    "Website redesign", "Impact reporting portal", "Donor microsite",
    "E-commerce migration", "Brand refresh site", "Programme dashboard",
    "Newsletter integration", "Staging environment rebuild",
]


class Command(BaseCommand):
    help = "Seed the database with realistic demo data for clients, projects, hosted sites, and invoices."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing demo data first")

    def handle(self, *args, **options):
        if options["flush"]:
            Invoice.objects.all().delete()
            HostedWebsite.objects.all().delete()
            Project.objects.all().delete()
            Client.objects.all().delete()
            self.stdout.write("Cleared existing data.")

        today = timezone.now().date()
        rng = random.Random(42)

        clients = []
        for name, company, email in CLIENTS:
            client, _ = Client.objects.get_or_create(
                name=name, defaults={"company": company, "email": email}
            )
            clients.append(client)

        statuses = [Project.STATUS_PLANNING, Project.STATUS_ACTIVE, Project.STATUS_ON_HOLD, Project.STATUS_COMPLETED]
        site_statuses = [HostedWebsite.STATUS_ONLINE] * 5 + [HostedWebsite.STATUS_WARNING] * 2 + [HostedWebsite.STATUS_OFFLINE]
        invoice_statuses = [Invoice.STATUS_PAID] * 4 + [Invoice.STATUS_PENDING] * 3 + [Invoice.STATUS_OVERDUE] * 2

        projects = []
        for i, pname in enumerate(PROJECT_NAMES):
            client = rng.choice(clients)
            start = today - timedelta(days=rng.randint(20, 260))
            project = Project.objects.create(
                name=f"{client.company} — {pname}",
                client=client,
                description=f"{pname} for {client.company}.",
                status=rng.choice(statuses),
                start_date=start,
                budget=rng.choice([180000, 320000, 450000, 90000, 600000]),
            )
            projects.append(project)

            domain = pname.lower().replace(" ", "") + "-" + client.company.split()[0].lower() + ".com"
            HostedWebsite.objects.create(
                project=project,
                domain=domain,
                server_provider=rng.choice(["DigitalOcean", "cPanel — Kenya Web Experts", "AWS Lightsail", "SiteGround"]),
                server_ip=f"41.90.{rng.randint(0,255)}.{rng.randint(1,254)}",
                hosting_plan=rng.choice(["Business", "Pro", "Managed VPS"]),
                status=rng.choice(site_statuses),
                domain_expiry_date=today + timedelta(days=rng.randint(-10, 400)),
                ssl_expiry_date=today + timedelta(days=rng.randint(-5, 200)),
                last_checked=timezone.now() - timedelta(hours=rng.randint(0, 48)),
            )

        for i in range(18):
            client = rng.choice(clients)
            project = rng.choice([p for p in projects if p.client_id == client.id] or projects)
            issued = today - timedelta(days=rng.randint(0, 175))
            status = rng.choice(invoice_statuses)
            due = issued + timedelta(days=30)
            Invoice.objects.create(
                client=client,
                project=project,
                reference=f"INV-{1000 + i}",
                amount=rng.choice([45000, 60000, 120000, 250000, 35000, 90000]),
                status=status,
                issued_date=issued,
                due_date=due,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(clients)} clients, {len(projects)} projects, "
            f"{HostedWebsite.objects.count()} hosted sites, {Invoice.objects.count()} invoices."
        ))
