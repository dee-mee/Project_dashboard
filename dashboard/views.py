import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .forms import ClientForm, HostedWebsiteForm, InvoiceForm, ProjectForm
from .models import Client, HostedWebsite, Invoice, Project


def _month_label(dt):
    return dt.strftime("%b")


@login_required
def overview(request):
    today = timezone.now().date()
    soon = today + timedelta(days=30)

    total_clients = Client.objects.count()
    total_projects = Project.objects.count()
    active_projects = Project.objects.filter(status=Project.STATUS_ACTIVE).count()
    total_sites = HostedWebsite.objects.count()

    # Project status breakdown (donut)
    project_status_qs = Project.objects.values("status").annotate(count=Count("id"))
    status_labels = dict(Project.STATUS_CHOICES)
    project_status = {
        "labels": [status_labels.get(row["status"], row["status"]) for row in project_status_qs],
        "data": [row["count"] for row in project_status_qs],
    }

    # Hosted site status breakdown (donut)
    site_status_qs = HostedWebsite.objects.values("status").annotate(count=Count("id"))
    site_status_labels = dict(HostedWebsite.STATUS_CHOICES)
    site_status = {
        "labels": [site_status_labels.get(row["status"], row["status"]) for row in site_status_qs],
        "data": [row["count"] for row in site_status_qs],
    }

    # Invoice status breakdown (donut) + revenue bar
    invoice_status_qs = Invoice.objects.values("status").annotate(count=Count("id"), total=Sum("amount"))
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
        total = Invoice.objects.filter(issued_date__year=y, issued_date__month=m).aggregate(total=Sum("amount"))[
            "total"
        ] or 0
        revenue_trend["labels"].append(timezone.datetime(y, m, 1).strftime("%b"))
        revenue_trend["data"].append(float(total))

    # Projects created per month (bar chart), same 6-month window
    projects_trend = {"labels": [], "data": []}
    for y, m in months:
        count = Project.objects.filter(created_at__year=y, created_at__month=m).count()
        projects_trend["labels"].append(timezone.datetime(y, m, 1).strftime("%b"))
        projects_trend["data"].append(count)

    expiring_sites = HostedWebsite.objects.filter(
        domain_expiry_date__lte=soon
    ) | HostedWebsite.objects.filter(ssl_expiry_date__lte=soon)
    expiring_sites = expiring_sites.distinct().order_by("domain_expiry_date")[:8]

    overdue_invoices = Invoice.objects.filter(status=Invoice.STATUS_OVERDUE).order_by("due_date")[:8]
    recent_invoices = Invoice.objects.select_related("client").order_by("-issued_date")[:8]
    recent_projects = Project.objects.select_related("client").order_by("-created_at")[:6]

    outstanding_total = Invoice.objects.exclude(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))[
        "total"
    ] or 0
    paid_total = Invoice.objects.filter(status=Invoice.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or 0

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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        return ctx


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = "dashboard/client_detail.html"
    context_object_name = "client"

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
        qs = Project.objects.select_related("client")
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
        qs = HostedWebsite.objects.select_related("project", "project__client")
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
        qs = Invoice.objects.select_related("client", "project")
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        return ctx


class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "dashboard/client_form.html"
    success_url = reverse_lazy("dashboard:client_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        ctx["form_title"] = "Add New Client"
        return ctx


class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "dashboard/client_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        ctx["form_title"] = "Edit Client"
        return ctx


class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = "dashboard/client_confirm_delete.html"
    success_url = reverse_lazy("dashboard:client_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "clients"
        return ctx


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "dashboard/project_form.html"
    success_url = reverse_lazy("dashboard:project_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["form_title"] = "Add New Project"
        return ctx


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "dashboard/project_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        ctx["form_title"] = "Edit Project"
        return ctx


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Project
    template_name = "dashboard/project_confirm_delete.html"
    success_url = reverse_lazy("dashboard:project_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "projects"
        return ctx


class HostedWebsiteCreateView(LoginRequiredMixin, CreateView):
    model = HostedWebsite
    form_class = HostedWebsiteForm
    template_name = "dashboard/site_form.html"
    success_url = reverse_lazy("dashboard:site_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        ctx["form_title"] = "Add New Hosted Website"
        return ctx


class HostedWebsiteUpdateView(LoginRequiredMixin, UpdateView):
    model = HostedWebsite
    form_class = HostedWebsiteForm
    template_name = "dashboard/site_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        ctx["form_title"] = "Edit Hosted Website"
        return ctx


class HostedWebsiteDeleteView(LoginRequiredMixin, DeleteView):
    model = HostedWebsite
    template_name = "dashboard/site_confirm_delete.html"
    success_url = reverse_lazy("dashboard:site_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "sites"
        return ctx


class InvoiceCreateView(LoginRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "dashboard/invoice_form.html"
    success_url = reverse_lazy("dashboard:invoice_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        ctx["form_title"] = "Add New Invoice"
        return ctx


class InvoiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "dashboard/invoice_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        ctx["form_title"] = "Edit Invoice"
        return ctx


class InvoiceDeleteView(LoginRequiredMixin, DeleteView):
    model = Invoice
    template_name = "dashboard/invoice_confirm_delete.html"
    success_url = reverse_lazy("dashboard:invoice_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "invoices"
        return ctx
