import datetime

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


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


class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_VIEWER = 'viewer'
    ROLE_CLIENT = 'client'
    
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_VIEWER, 'Viewer'),
        (ROLE_CLIENT, 'Client'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profiles', help_text='For client-facing users, link to their client account')
    can_delete = models.BooleanField(default=False, help_text='Allow deletion of records')
    can_edit = models.BooleanField(default=True, help_text='Allow editing of records')
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
    
    def has_full_access(self):
        if self.user.is_superuser or self.user.is_staff:
            return True
        return self.role in [self.ROLE_ADMIN, self.ROLE_MANAGER]
    
    def can_view_all_clients(self):
        if self.user.is_superuser or self.user.is_staff:
            return True
        return self.role in [self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_VIEWER]
    
    def can_view_client(self, client):
        if self.has_full_access() or self.can_view_all_clients():
            return True
        if self.role == self.ROLE_CLIENT:
            return self.client == client
        return False


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
    
    # Stripe payment fields
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Payment Intent ID")
    stripe_payment_status = models.CharField(max_length=50, blank=True, null=True, help_text="Stripe payment status")
    paid_at = models.DateTimeField(null=True, blank=True, help_text="When the invoice was marked as paid")

    class Meta:
        ordering = ["-issued_date"]

    def __str__(self):
        if self.reference:
            return f"{self.reference} - {self.client}"
        return f"Invoice #{self.pk} - {self.client}"

    def get_absolute_url(self):
        return reverse("dashboard:invoice_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_PENDING and self.due_date and self.due_date < timezone.now().date():
            self.status = self.STATUS_OVERDUE
        super().save(*args, **kwargs)
    
    def mark_as_paid(self, payment_intent_id=None):
        """Mark invoice as paid and record payment details"""
        self.status = self.STATUS_PAID
        self.paid_at = timezone.now()
        if payment_intent_id:
            self.stripe_payment_intent_id = payment_intent_id
        self.save()
    
    def generate_pdf(self):
        """Generate PDF invoice using reportlab"""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        import os
        from django.conf import settings
        
        # Create file path
        filename = f"invoice_{self.reference or self.pk}.pdf"
        upload_to = f"invoices/{timezone.now().strftime('%Y/%m')}"
        full_path = os.path.join(settings.MEDIA_ROOT, upload_to, filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Create PDF
        doc = SimpleDocTemplate(full_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Header
        story.append(Paragraph(f"INVOICE #{self.reference or self.pk}", styles['Title']))
        story.append(Spacer(1, 0.2*inch))
        
        # Client info
        client_text = f"""
        <b>Bill To:</b><br/>
        {self.client.name}<br/>
        {self.client.company or ''}<br/>
        {self.client.email or ''}<br/>
        {self.client.phone or ''}
        """
        story.append(Paragraph(client_text, styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Invoice details
        details_text = f"""
        <b>Issued:</b> {self.issued_date.strftime('%B %d, %Y') if self.issued_date else 'N/A'}<br/>
        <b>Due:</b> {self.due_date.strftime('%B %d, %Y') if self.due_date else 'N/A'}<br/>
        <b>Status:</b> {self.get_status_display()}
        """
        story.append(Paragraph(details_text, styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Amount
        amount_text = f"<b>Total Amount: ${self.amount:,.2f}</b>"
        story.append(Paragraph(amount_text, styles['Heading2']))
        
        if self.project:
            story.append(Spacer(1, 0.2*inch))
            project_text = f"<b>Project:</b> {self.project.name}"
            story.append(Paragraph(project_text, styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Save to model
        self.pdf_file.name = f"{upload_to}/{filename}"
        self.save()
        
        return self.pdf_file


class AuditLog(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_STATUS_CHANGE = 'status_change'
    
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Created'),
        (ACTION_UPDATE, 'Updated'),
        (ACTION_DELETE, 'Deleted'),
        (ACTION_STATUS_CHANGE, 'Status Changed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} {self.content_object} by {self.user}"
    
    @classmethod
    def log_action(cls, user, action, obj, description='', changes=None):
        """Helper method to log an action"""
        return cls.objects.create(
            user=user,
            action=action,
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.pk,
            description=description,
            changes=changes or {}
        )


class TimeEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_entries')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='time_entries')
    description = models.TextField(blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2, help_text='Hours worked')
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entries'
        indexes = [
            models.Index(fields=['project']),
            models.Index(fields=['user']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.hours}h on {self.project.name} ({self.date})"

    def get_absolute_url(self):
        return reverse("dashboard:timeentry_list")


class FileAttachment(models.Model):
    FILE_TYPE_CONTRACT = 'contract'
    FILE_TYPE_PROPOSAL = 'proposal'
    FILE_TYPE_SCREENSHOT = 'screenshot'
    FILE_TYPE_OTHER = 'other'
    
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_CONTRACT, 'Contract'),
        (FILE_TYPE_PROPOSAL, 'Proposal'),
        (FILE_TYPE_SCREENSHOT, 'Screenshot'),
        (FILE_TYPE_OTHER, 'Other'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/%Y/%m/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default=FILE_TYPE_OTHER)
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'File Attachment'
        verbose_name_plural = 'File Attachments'
        indexes = [
            models.Index(fields=['project']),
            models.Index(fields=['file_type']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.file.name} ({self.get_file_type_display()})"
    
    def get_absolute_url(self):
        return reverse('dashboard:attachment_detail', args=[self.pk])


class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='project_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project Comment'
        verbose_name_plural = 'Project Comments'
        indexes = [
            models.Index(fields=['project']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        truncated = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{truncated} by {self.user}"


class RecurringBilling(models.Model):
    INTERVAL_MONTHLY = 'monthly'
    INTERVAL_QUARTERLY = 'quarterly'
    INTERVAL_YEARLY = 'yearly'
    
    INTERVAL_CHOICES = [
        (INTERVAL_MONTHLY, 'Monthly'),
        (INTERVAL_QUARTERLY, 'Quarterly'),
        (INTERVAL_YEARLY, 'Yearly'),
    ]
    
    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='recurring_billings')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_billings')
    name = models.CharField(max_length=200, help_text='Name for this recurring billing (e.g., "Monthly Hosting")')
    description = models.TextField(blank=True, help_text='Description of services included')
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Recurring amount')
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default=INTERVAL_MONTHLY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    
    # Stripe subscription fields
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Billing schedule
    start_date = models.DateField(default=timezone.now)
    next_billing_date = models.DateField()
    last_billed_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Recurring Billing'
        verbose_name_plural = 'Recurring Billings'
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['status']),
            models.Index(fields=['next_billing_date']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.client} ({self.get_interval_display()})"
    
    def get_absolute_url(self):
        return reverse('dashboard:recurring_detail', args=[self.pk])
    
    def calculate_next_billing_date(self):
        """Calculate the next billing date based on interval"""
        from datetime import timedelta
        if self.interval == self.INTERVAL_MONTHLY:
            return self.next_billing_date + timedelta(days=30)
        elif self.interval == self.INTERVAL_QUARTERLY:
            return self.next_billing_date + timedelta(days=90)
        elif self.interval == self.INTERVAL_YEARLY:
            return self.next_billing_date + timedelta(days=365)
        return self.next_billing_date
    
    def generate_invoice(self):
        """Generate an invoice for this billing cycle"""
        if self.status != self.STATUS_ACTIVE:
            return None
        
        invoice = Invoice.objects.create(
            client=self.client,
            project=self.project,
            reference=f"REC-{self.pk}-{self.last_billed_date.strftime('%Y%m') if self.last_billed_date else 'INIT'}",
            amount=self.amount,
            status=Invoice.STATUS_PENDING,
            issued_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30)
        )
        
        self.last_billed_date = timezone.now().date()
        self.next_billing_date = self.calculate_next_billing_date()
        self.save()
        
        return invoice
