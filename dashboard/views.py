import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .forms import ClientForm, HostedWebsiteForm, InvoiceForm, ProjectForm
from .models import Client, HostedWebsite, Invoice, Project, UserProfile


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
