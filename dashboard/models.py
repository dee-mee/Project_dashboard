import datetime

from django.db import models
from django.urls import reverse
from django.utils import timezone


class Client(models.Model):
    name = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.company or self.name

    def get_absolute_url(self):
        return reverse("dashboard:client_detail", args=[self.pk])

    @property
    def active_project_count(self):
        return self.projects.filter(status="active").count()


class Project(models.Model):
    STATUS_PLANNING = "planning"
    STATUS_ACTIVE = "active"
    STATUS_ON_HOLD = "on_hold"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_PLANNING, "Planning"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ON_HOLD, "On hold"),
        (STATUS_COMPLETED, "Completed"),
    ]

    name = models.CharField(max_length=200)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="projects")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNING)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("dashboard:project_detail", args=[self.pk])


class HostedWebsite(models.Model):
    STATUS_ONLINE = "online"
    STATUS_WARNING = "warning"
    STATUS_OFFLINE = "offline"
    STATUS_UNCHECKED = "unchecked"
    STATUS_CHOICES = [
        (STATUS_ONLINE, "Online"),
        (STATUS_WARNING, "Warning"),
        (STATUS_OFFLINE, "Offline"),
        (STATUS_UNCHECKED, "Not checked yet"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="hosted_sites")
    domain = models.CharField(max_length=255, help_text="e.g. clientsite.com")
    server_provider = models.CharField(max_length=150, blank=True, help_text="e.g. DigitalOcean, cPanel host, AWS")
    server_ip = models.GenericIPAddressField(null=True, blank=True)
    hosting_plan = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNCHECKED)
    domain_expiry_date = models.DateField(null=True, blank=True)
    ssl_expiry_date = models.DateField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["domain"]
        verbose_name = "Hosted website"

    def __str__(self):
        return self.domain

    def get_absolute_url(self):
        return reverse("dashboard:site_detail", args=[self.pk])

    def _days_until(self, target_date):
        if not target_date:
            return None
        return (target_date - timezone.now().date()).days

    @property
    def domain_days_left(self):
        return self._days_until(self.domain_expiry_date)

    @property
    def ssl_days_left(self):
        return self._days_until(self.ssl_expiry_date)

    @property
    def is_expiring_soon(self, threshold=30):
        for days in (self.domain_days_left, self.ssl_days_left):
            if days is not None and days <= threshold:
                return True
        return False


class Invoice(models.Model):
    STATUS_PAID = "paid"
    STATUS_PENDING = "pending"
    STATUS_OVERDUE = "overdue"
    STATUS_CHOICES = [
        (STATUS_PAID, "Paid"),
        (STATUS_PENDING, "Pending"),
        (STATUS_OVERDUE, "Overdue"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="invoices")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    reference = models.CharField(max_length=50, blank=True, help_text="Invoice number / reference")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    issued_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    pdf_file = models.FileField(upload_to="invoices/%Y/%m/", null=True, blank=True)

    class Meta:
        ordering = ["-issued_date"]

    def __str__(self):
        return self.reference or f"Invoice #{self.pk} - {self.client}"

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_PENDING and self.due_date and self.due_date < timezone.now().date():
            self.status = self.STATUS_OVERDUE
        super().save(*args, **kwargs)
