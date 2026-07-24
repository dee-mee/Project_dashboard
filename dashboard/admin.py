from django.contrib import admin

from .models import AuditLog, Client, FileAttachment, HostedWebsite, Invoice, Project, ProjectComment, RecurringBilling, TimeEntry, UserProfile


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


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "client", "can_edit", "can_delete")
    list_filter = ("role", "can_edit", "can_delete")
    search_fields = ("user__username", "user__email", "client__company")
    raw_id_fields = ("user", "client")


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "hours", "date", "description")
    list_filter = ("project", "user", "date")
    search_fields = ("description", "project__name", "user__username")
    date_hierarchy = "date"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "content_type", "object_id", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("user__username", "description")
    readonly_fields = ("user", "action", "content_type", "object_id", "description", "changes", "timestamp")


@admin.register(FileAttachment)
class FileAttachmentAdmin(admin.ModelAdmin):
    list_display = ("file", "file_type", "project", "description", "uploaded_by", "uploaded_at")
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("description", "file", "project__name")
    date_hierarchy = "uploaded_at"


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "content_preview", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("content", "project__name", "user__username")
    date_hierarchy = "created_at"
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Content"


@admin.register(RecurringBilling)
class RecurringBillingAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "amount", "interval", "status", "next_billing_date", "last_billed_date")
    list_filter = ("status", "interval", "next_billing_date")
    search_fields = ("name", "client__name", "client__company", "project__name")
    date_hierarchy = "next_billing_date"
    
    actions = ['generate_invoices']
    
    def generate_invoices(self, request, queryset):
        count = 0
        for recurring in queryset:
            if recurring.status == RecurringBilling.STATUS_ACTIVE:
                invoice = recurring.generate_invoice()
                if invoice:
                    count += 1
        self.message_user(request, f"{count} invoices generated successfully.")
    generate_invoices.short_description = "Generate invoices for selected items"
