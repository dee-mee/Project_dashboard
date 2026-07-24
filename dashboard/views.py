import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .forms import ClientForm, FileAttachmentForm, HostedWebsiteForm, InvoiceForm, ProjectCommentForm, ProjectForm, RecurringBillingForm, TimeEntryForm
from .models import AuditLog, Client, FileAttachment, HostedWebsite, Invoice, Project, ProjectComment, RecurringBilling, TimeEntry, UserProfile


class PermissionRequiredMixin(UserPassesTestMixin):
    """Mixin to check user permissions based on UserProfile"""
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        
        try:
            profile = self.request.user.profile
        except UserProfile.DoesNotExist:
            # Create a default profile if it doesn't exist
            profile = UserProfile.objects.create(user=self.request.user)
        
        # Check edit/delete permissions
        if self.request.method in ['POST', 'PUT', 'DELETE']:
            if not profile.can_edit:
                return False
            if not profile.can_delete and 'delete' in self.request.path.lower():
                return False
        
        return True
    
    def handle_no_permission(self):
        from django.contrib.auth.mixins import PermissionDenied
        raise PermissionDenied("You don't have permission to perform this action.")


def get_user_profile(user):
    """Get or create user profile"""
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)


def _month_label(dt):
    return dt.strftime("%b")


@login_required
def overview(request):
    profile = get_user_profile(request.user)
    today = timezone.now().date()
    soon = today + timedelta(days=30)

    # Filter data based on user permissions
    if profile.can_view_all_clients():
        clients = Client.objects.all()
        projects = Project.objects.all()
        sites = HostedWebsite.objects.all()
        invoices = Invoice.objects.all()
    elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
        clients = Client.objects.filter(pk=profile.client.pk)
        projects = Project.objects.filter(client=profile.client)
        sites = HostedWebsite.objects.filter(project__client=profile.client)
        invoices = Invoice.objects.filter(client=profile.client)
    else:
        # Viewer with no client assignment - show nothing
        clients = Client.objects.none()
        projects = Project.objects.none()
        sites = HostedWebsite.objects.none()
        invoices = Invoice.objects.none()

    total_clients = clients.count()
    total_projects = projects.count()
    active_projects = projects.filter(status=Project.STATUS_ACTIVE).count()
    total_sites = sites.count()

    # Project status breakdown (donut)
    project_status_qs = projects.values("status").annotate(count=Count("id"))
    status_labels = dict(Project.STATUS_CHOICES)
    project_status = {
        "labels": [status_labels.get(row["status"], row["status"]) for row in project_status_qs],
        "data": [row["count"] for row in project_status_qs],
    }

    # Hosted site status breakdown (donut)
    site_status_qs = sites.values("status").annotate(count=Count("id"))
    site_status_labels = dict(HostedWebsite.STATUS_CHOICES)
    site_status = {
        "labels": [site_status_labels.get(row["status"], row["status"]) for row in site_status_qs],
        "data": [row["count"] for row in site_status_qs],
    }

    # Invoice status breakdown (donut) + revenue bar
    invoice_status_qs = invoices.values("status").annotate(count=Count("id"), total=Sum("amount"))
    invoice_status_labels = dict(Invoice.STATUS_CHOICES)
    invoice_status = {
        "labels": [invoice_status_labels.get(row["status"], row["status"]) for row in invoice_status_qs],
        "data": [row["count"] for row in invoice_status_qs],
    }
    revenue_by_status = {
        "labels": [invoice_status_labels.get(row["status"], row["status"]) for row in invoice_status_qs],
        "data": [float(row["total"] or 0) for row in invoice_status_qs],
    }

    # Revenue trend over the last 6 months (line chart)
    months = []
    cursor = today.replace(day=1)
    for i in range(5, -1, -1):
        m = (cursor.month - i - 1) % 12 + 1
        y = cursor.year + ((cursor.month - i - 1) // 12)
        months.append((y, m))
    revenue_trend = {"labels": [], "data": []}
    for y, m in months:
        total = invoices.filter(issued_date__year=y, issued_date__month=m).aggregate(total=Sum("amount"))[
            "total"
        ] or 0
        revenue_trend["labels"].append(timezone.datetime(y, m, 1).strftime("%b"))
        revenue_trend["data"].append(float(total))

    # Projects created per month (bar chart), same 6-month window
    projects_trend = {"labels": [], "data": []}
    for y, m in months:
        count = projects.filter(created_at__year=y, created_at__month=m).count()
        projects_trend["labels"].append(timezone.datetime(y, m, 1).strftime("%b"))
        projects_trend["data"].append(count)

    expiring_sites = sites.filter(
        Q(domain_expiry_date__lte=soon) | Q(ssl_expiry_date__lte=soon)
    ).distinct().order_by("domain_expiry_date")[:8]

    overdue_invoices = invoices.filter(status=Invoice.STATUS_OVERDUE).order_by("due_date")[:8]
    recent_invoices = invoices.select_related("client").order_by("-issued_date")[:8]
    recent_projects = projects.select_related("client").order_by("-created_at")[:6]

    outstanding_total = invoices.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
        "total"
    ] or 0
    paid_total = invoices.filter(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or 0

    context = {
        "total_clients": total_clients,
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_sites": total_sites,
        "outstanding_total": outstanding_total,
        "paid_total": paid_total,
        "project_status_json": json.dumps(project_status),
        "site_status_json": json.dumps(site_status),
        "invoice_status_json": json.dumps(invoice_status),
        "revenue_by_status_json": json.dumps(revenue_by_status),
        "revenue_trend_json": json.dumps(revenue_trend),
        "projects_trend_json": json.dumps(projects_trend),
        "expiring_sites": expiring_sites,
        "overdue_invoices": overdue_invoices,
        "recent_invoices": recent_invoices,
        "recent_projects": recent_projects,
        "active_nav": "overview",
    }
    return render(request, "dashboard/overview.html", context)


class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = "dashboard/client_list.html"
    context_object_name = "clients"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return Client.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return Client.objects.filter(pk=profile.client.pk)
        return Client.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        return ctx


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = "dashboard/client_detail.html"
    context_object_name = "client"

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return Client.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return Client.objects.filter(pk=profile.client.pk)
        return Client.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["projects"] = self.object.projects.all()
        ctx["invoices"] = self.object.invoices.all()
        ctx["active_nav"] = "clients"
        return ctx


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "dashboard/project_list.html"
    context_object_name = "projects"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = Project.objects.select_related("client")
        
        if profile.can_view_all_clients():
            pass  # Show all projects
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(client=profile.client)
        else:
            qs = qs.none()
        
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = Project.STATUS_CHOICES
        return ctx


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "dashboard/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return Project.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return Project.objects.filter(client=profile.client)
        return Project.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["hosted_sites"] = self.object.hosted_sites.all()
        ctx["invoices"] = self.object.invoices.all()
        ctx["time_entries"] = self.object.time_entries.select_related('user').order_by('-date', '-created_at')
        ctx["attachments"] = self.object.attachments.select_related('uploaded_by').order_by('-uploaded_at')
        ctx["comments"] = self.object.comments.select_related('user').order_by('-created_at')
        ctx["active_nav"] = "projects"
        return ctx


class HostedWebsiteListView(LoginRequiredMixin, ListView):
    model = HostedWebsite
    template_name = "dashboard/site_list.html"
    context_object_name = "sites"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = HostedWebsite.objects.select_related("project", "project__client")
        
        if profile.can_view_all_clients():
            pass  # Show all sites
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(project__client=profile.client)
        else:
            qs = qs.none()
        
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = HostedWebsite.STATUS_CHOICES
        return ctx


class HostedWebsiteDetailView(LoginRequiredMixin, DetailView):
    model = HostedWebsite
    template_name = "dashboard/site_detail.html"
    context_object_name = "site"

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return HostedWebsite.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return HostedWebsite.objects.filter(project__client=profile.client)
        return HostedWebsite.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        return ctx


class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = "dashboard/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = Invoice.objects.select_related("client", "project")
        
        if profile.can_view_all_clients():
            pass  # Show all invoices
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(client=profile.client)
        else:
            qs = qs.none()
        
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = Invoice.STATUS_CHOICES
        return ctx


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = "dashboard/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return Invoice.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return Invoice.objects.filter(client=profile.client)
        return Invoice.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        return ctx


class ClientCreateView(PermissionRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "dashboard/client_form.html"
    success_url = reverse_lazy("dashboard:client_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        ctx["form_title"] = "Add New Client"
        return ctx


class ClientUpdateView(PermissionRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "dashboard/client_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        ctx["form_title"] = "Edit Client"
        return ctx


class ClientDeleteView(PermissionRequiredMixin, DeleteView):
    model = Client
    template_name = "dashboard/client_confirm_delete.html"
    success_url = reverse_lazy("dashboard:client_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        return ctx


class ProjectCreateView(PermissionRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "dashboard/project_form.html"
    success_url = reverse_lazy("dashboard:project_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["form_title"] = "Add New Project"
        return ctx


class ProjectUpdateView(PermissionRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "dashboard/project_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["form_title"] = "Edit Project"
        return ctx


class ProjectDeleteView(PermissionRequiredMixin, DeleteView):
    model = Project
    template_name = "dashboard/project_confirm_delete.html"
    success_url = reverse_lazy("dashboard:project_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        return ctx


class HostedWebsiteCreateView(PermissionRequiredMixin, CreateView):
    model = HostedWebsite
    form_class = HostedWebsiteForm
    template_name = "dashboard/site_form.html"
    success_url = reverse_lazy("dashboard:site_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        ctx["form_title"] = "Add New Hosted Website"
        return ctx


class HostedWebsiteUpdateView(PermissionRequiredMixin, UpdateView):
    model = HostedWebsite
    form_class = HostedWebsiteForm
    template_name = "dashboard/site_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        ctx["form_title"] = "Edit Hosted Website"
        return ctx


class HostedWebsiteDeleteView(PermissionRequiredMixin, DeleteView):
    model = HostedWebsite
    template_name = "dashboard/site_confirm_delete.html"
    success_url = reverse_lazy("dashboard:site_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        return ctx


class InvoiceCreateView(PermissionRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "dashboard/invoice_form.html"
    success_url = reverse_lazy("dashboard:invoice_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        ctx["form_title"] = "Add New Invoice"
        return ctx


class InvoiceUpdateView(PermissionRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "dashboard/invoice_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        ctx["form_title"] = "Edit Invoice"
        return ctx


class InvoiceDeleteView(PermissionRequiredMixin, DeleteView):
    model = Invoice
    template_name = "dashboard/invoice_confirm_delete.html"
    success_url = reverse_lazy("dashboard:invoice_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        return ctx


@login_required
def generate_invoice_pdf(request, pk):
    """Generate PDF for an invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Check permissions
    profile = get_user_profile(request.user)
    if not profile.can_view_all_clients() and (profile.role != UserProfile.ROLE_CLIENT or profile.client != invoice.client):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to view this invoice.")
    
    try:
        pdf_file = invoice.generate_pdf()
        if pdf_file:
            return redirect('dashboard:invoice_detail', pk=pk)
        else:
            return redirect('dashboard:invoice_detail', pk=pk)
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f"Error generating PDF: {e}")
        return redirect('dashboard:invoice_detail', pk=pk)


@login_required
def search(request):
    """Global search across clients, projects, and hosted websites"""
    query = request.GET.get('q', '').strip()
    profile = get_user_profile(request.user)
    
    results = {
        'clients': [],
        'projects': [],
        'sites': [],
    }
    
    if query:
        # Search clients
        clients_qs = Client.objects.filter(
            Q(name__icontains=query) | Q(company__icontains=query) | Q(email__icontains=query)
        )
        if not profile.can_view_all_clients():
            if profile.role == UserProfile.ROLE_CLIENT and profile.client:
                clients_qs = clients_qs.filter(pk=profile.client.pk)
            else:
                clients_qs = clients_qs.none()
        results['clients'] = clients_qs[:10]
        
        # Search projects
        projects_qs = Project.objects.filter(
            Q(name__icontains=query) | Q(client__name__icontains=query) | Q(client__company__icontains=query)
        ).select_related('client')
        if not profile.can_view_all_clients():
            if profile.role == UserProfile.ROLE_CLIENT and profile.client:
                projects_qs = projects_qs.filter(client=profile.client)
            else:
                projects_qs = projects_qs.none()
        results['projects'] = projects_qs[:10]
        
        # Search hosted websites
        sites_qs = HostedWebsite.objects.filter(
            Q(domain__icontains=query) | Q(server_ip__icontains=query) | Q(project__name__icontains=query)
        ).select_related('project', 'project__client')
        if not profile.can_view_all_clients():
            if profile.role == UserProfile.ROLE_CLIENT and profile.client:
                sites_qs = sites_qs.filter(project__client=profile.client)
            else:
                sites_qs = sites_qs.none()
        results['sites'] = sites_qs[:10]
    
    return render(request, 'dashboard/search.html', {
        'query': query,
        'results': results,
        'active_nav': 'search',
    })


class TimeEntryListView(LoginRequiredMixin, ListView):
    model = TimeEntry
    template_name = "dashboard/timeentry_list.html"
    context_object_name = "time_entries"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = TimeEntry.objects.select_related("project", "project__client", "user")
        
        if profile.can_view_all_clients():
            pass  # Show all time entries
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(project__client=profile.client)
        else:
            qs = qs.filter(user=self.request.user)
        
        project_id = self.request.GET.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "time_entries"
        ctx["current_project"] = self.request.GET.get("project", "")
        return ctx


class TimeEntryCreateView(PermissionRequiredMixin, CreateView):
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = "dashboard/timeentry_form.html"
    success_url = reverse_lazy("dashboard:timeentry_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "time_entries"
        ctx["form_title"] = "Add Time Entry"
        return ctx


class TimeEntryUpdateView(PermissionRequiredMixin, UpdateView):
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = "dashboard/timeentry_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "time_entries"
        ctx["form_title"] = "Edit Time Entry"
        return ctx


class TimeEntryDeleteView(PermissionRequiredMixin, DeleteView):
    model = TimeEntry
    template_name = "dashboard/timeentry_confirm_delete.html"
    success_url = reverse_lazy("dashboard:timeentry_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "time_entries"
        return ctx


class FileAttachmentListView(LoginRequiredMixin, ListView):
    model = FileAttachment
    template_name = "dashboard/attachment_list.html"
    context_object_name = "attachments"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = FileAttachment.objects.select_related("project", "project__client", "uploaded_by")
        
        if profile.can_view_all_clients():
            pass  # Show all attachments
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(project__client=profile.client)
        else:
            qs = qs.none()
        
        file_type = self.request.GET.get("file_type")
        if file_type:
            qs = qs.filter(file_type=file_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "attachments"
        ctx["current_file_type"] = self.request.GET.get("file_type", "")
        ctx["file_type_choices"] = FileAttachment.FILE_TYPE_CHOICES
        return ctx


class FileAttachmentDetailView(LoginRequiredMixin, DetailView):
    model = FileAttachment
    template_name = "dashboard/attachment_detail.html"
    context_object_name = "attachment"

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return FileAttachment.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return FileAttachment.objects.filter(project__client=profile.client)
        return FileAttachment.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "attachments"
        return ctx


class FileAttachmentCreateView(PermissionRequiredMixin, CreateView):
    model = FileAttachment
    form_class = FileAttachmentForm
    template_name = "dashboard/attachment_form.html"
    success_url = reverse_lazy("dashboard:attachment_list")

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "attachments"
        ctx["form_title"] = "Upload File"
        return ctx


class FileAttachmentDeleteView(PermissionRequiredMixin, DeleteView):
    model = FileAttachment
    template_name = "dashboard/attachment_confirm_delete.html"
    success_url = reverse_lazy("dashboard:attachment_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "attachments"
        return ctx


class ProjectCommentListView(LoginRequiredMixin, ListView):
    model = ProjectComment
    template_name = "dashboard/comment_list.html"
    context_object_name = "comments"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = ProjectComment.objects.select_related("project", "project__client", "user")
        
        if profile.can_view_all_clients():
            pass  # Show all comments
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(project__client=profile.client)
        else:
            qs = qs.none()
        
        project_id = self.request.GET.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "comments"
        ctx["current_project"] = self.request.GET.get("project", "")
        return ctx


class ProjectCommentCreateView(PermissionRequiredMixin, CreateView):
    model = ProjectComment
    form_class = ProjectCommentForm
    template_name = "dashboard/comment_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        project_id = self.kwargs.get('project_id')
        form.instance.project = get_object_or_404(Project, pk=project_id)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("dashboard:project_detail", kwargs={'pk': self.object.project.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["form_title"] = "Add Comment"
        return ctx


class ProjectCommentUpdateView(PermissionRequiredMixin, UpdateView):
    model = ProjectComment
    form_class = ProjectCommentForm
    template_name = "dashboard/comment_form.html"

    def get_success_url(self):
        return reverse_lazy("dashboard:project_detail", kwargs={'pk': self.object.project.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["form_title"] = "Edit Comment"
        return ctx


class ProjectCommentDeleteView(PermissionRequiredMixin, DeleteView):
    model = ProjectComment
    template_name = "dashboard/comment_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("dashboard:project_detail", kwargs={'pk': self.object.project.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        return ctx


@login_required
@csrf_exempt
def create_stripe_payment_intent(request, pk):
    """Create a Stripe Payment Intent for an invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Check permissions
    profile = get_user_profile(request.user)
    if not profile.can_view_all_clients() and (profile.role != UserProfile.ROLE_CLIENT or profile.client != invoice.client):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to view this invoice.")
    
    if invoice.status == Invoice.STATUS_PAID:
        return JsonResponse({'error': 'Invoice is already paid'}, status=400)
    
    try:
        # Configure Stripe with secret key from settings
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if not stripe.api_key:
            return JsonResponse({'error': 'Stripe not configured'}, status=500)
        
        # Create payment intent
        amount_in_cents = int(invoice.amount * 100)  # Convert to cents
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_in_cents,
            currency='usd',
            metadata={'invoice_id': invoice.pk, 'reference': invoice.reference or str(invoice.pk)}
        )
        
        return JsonResponse({
            'clientSecret': payment_intent.client_secret,
            'paymentIntentId': payment_intent.id,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not stripe.api_key:
        return JsonResponse({'error': 'Stripe not configured'}, status=500)
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    
    if not webhook_secret:
        return JsonResponse({'error': 'Webhook secret not configured'}, status=500)
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError as e:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    # Handle payment_intent.succeeded event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        invoice_id = payment_intent.metadata.get('invoice_id')
        
        if invoice_id:
            try:
                invoice = Invoice.objects.get(pk=invoice_id)
                invoice.mark_as_paid(payment_intent_id=payment_intent.id)
                invoice.stripe_payment_status = payment_intent.status
                invoice.save()
            except Invoice.DoesNotExist:
                pass
    
    return JsonResponse({'status': 'success'})


class RecurringBillingListView(LoginRequiredMixin, ListView):
    model = RecurringBilling
    template_name = "dashboard/recurring_list.html"
    context_object_name = "recurring_billings"
    paginate_by = 25

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        qs = RecurringBilling.objects.select_related("client", "project")
        
        if profile.can_view_all_clients():
            pass  # Show all recurring billings
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            qs = qs.filter(client=profile.client)
        else:
            qs = qs.none()
        
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "recurring"
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = RecurringBilling.STATUS_CHOICES
        return ctx


class RecurringBillingDetailView(LoginRequiredMixin, DetailView):
    model = RecurringBilling
    template_name = "dashboard/recurring_detail.html"
    context_object_name = "recurring"

    def get_queryset(self):
        profile = get_user_profile(self.request.user)
        if profile.can_view_all_clients():
            return RecurringBilling.objects.all()
        elif profile.role == UserProfile.ROLE_CLIENT and profile.client:
            return RecurringBilling.objects.filter(client=profile.client)
        return RecurringBilling.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "recurring"
        return ctx


class RecurringBillingCreateView(PermissionRequiredMixin, CreateView):
    model = RecurringBilling
    form_class = RecurringBillingForm
    template_name = "dashboard/recurring_form.html"
    success_url = reverse_lazy("dashboard:recurring_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "recurring"
        ctx["form_title"] = "Add Recurring Billing"
        return ctx


class RecurringBillingUpdateView(PermissionRequiredMixin, UpdateView):
    model = RecurringBilling
    form_class = RecurringBillingForm
    template_name = "dashboard/recurring_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "recurring"
        ctx["form_title"] = "Edit Recurring Billing"
        return ctx


class RecurringBillingDeleteView(PermissionRequiredMixin, DeleteView):
    model = RecurringBilling
    template_name = "dashboard/recurring_confirm_delete.html"
    success_url = reverse_lazy("dashboard:recurring_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "recurring"
        return ctx


@login_required
def generate_recurring_invoice(request, pk):
    """Generate an invoice for a recurring billing cycle"""
    recurring = get_object_or_404(RecurringBilling, pk=pk)
    
    # Check permissions
    profile = get_user_profile(request.user)
    if not profile.can_view_all_clients() and (profile.role != UserProfile.ROLE_CLIENT or profile.client != recurring.client):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to view this recurring billing.")
    
    invoice = recurring.generate_invoice()
    if invoice:
        from django.contrib import messages
        messages.success(request, f"Invoice {invoice.reference} generated successfully.")
        return redirect('dashboard:invoice_detail', pk=invoice.pk)
    else:
        from django.contrib import messages
        messages.error(request, "Could not generate invoice. Recurring billing may not be active.")
        return redirect('dashboard:recurring_detail', pk=pk)
