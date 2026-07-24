from django.contrib import admin

from .models import Client, HostedWebsite, Invoice, Project


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0
    fields = ("name", "status", "start_date", "end_date")
    show_change_link = True


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "email", "phone", "active_project_count", "created_at")
    search_fields = ("name", "company", "email")
    inlines = [ProjectInline]


class HostedWebsiteInline(admin.TabularInline):
    model = HostedWebsite
    extra = 0
    fields = ("domain", "status", "domain_expiry_date", "ssl_expiry_date")
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "status", "start_date", "end_date", "budget")
    list_filter = ("status", "client")
    search_fields = ("name", "client__name", "client__company")
    inlines = [HostedWebsiteInline]


@admin.register(HostedWebsite)
class HostedWebsiteAdmin(admin.ModelAdmin):
    list_display = (
        "domain",
        "project",
        "status",
        "server_provider",
        "domain_expiry_date",
        "ssl_expiry_date",
        "last_checked",
    )
    list_filter = ("status", "server_provider")
    search_fields = ("domain", "project__name", "server_ip")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("reference", "client", "project", "amount", "status", "issued_date", "due_date")
    list_filter = ("status",)
    search_fields = ("reference", "client__name", "client__company")
