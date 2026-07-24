from django import forms
from .models import Client, FileAttachment, HostedWebsite, Invoice, Project, ProjectComment, RecurringBilling, TimeEntry


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "company", "email", "phone", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "company": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "client", "description", "status", "start_date", "end_date", "budget"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "client": forms.Select(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "budget": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        }


class HostedWebsiteForm(forms.ModelForm):
    class Meta:
        model = HostedWebsite
        fields = [
            "project",
            "domain",
            "server_provider",
            "server_ip",
            "hosting_plan",
            "status",
            "domain_expiry_date",
            "ssl_expiry_date",
            "notes",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-input"}),
            "domain": forms.TextInput(attrs={"class": "form-input"}),
            "server_provider": forms.TextInput(attrs={"class": "form-input"}),
            "server_ip": forms.TextInput(attrs={"class": "form-input"}),
            "hosting_plan": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "domain_expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "ssl_expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["client", "project", "reference", "amount", "status", "issued_date", "due_date", "pdf_file"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-input"}),
            "project": forms.Select(attrs={"class": "form-input"}),
            "reference": forms.TextInput(attrs={"class": "form-input"}),
            "amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "issued_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "pdf_file": forms.FileInput(attrs={"class": "form-input"}),
        }


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ["project", "description", "hours", "date"]
        widgets = {
            "project": forms.Select(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.25", "min": "0"}),
            "date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }


class FileAttachmentForm(forms.ModelForm):
    class Meta:
        model = FileAttachment
        fields = ["project", "file", "file_type", "description"]
        widgets = {
            "project": forms.Select(attrs={"class": "form-input"}),
            "file": forms.FileInput(attrs={"class": "form-input"}),
            "file_type": forms.Select(attrs={"class": "form-input"}),
            "description": forms.TextInput(attrs={"class": "form-input"}),
        }


class ProjectCommentForm(forms.ModelForm):
    class Meta:
        model = ProjectComment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-input", "rows": 4, "placeholder": "Add a comment..."}),
        }


class RecurringBillingForm(forms.ModelForm):
    class Meta:
        model = RecurringBilling
        fields = ["client", "project", "name", "description", "amount", "interval", "status", "start_date", "next_billing_date"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-input"}),
            "project": forms.Select(attrs={"class": "form-input"}),
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
            "amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "interval": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_billing_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }
