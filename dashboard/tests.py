from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client as DjangoClient
from django.utils import timezone
from django.urls import reverse

from dashboard.models import Client, HostedWebsite, Invoice, Project


class ClientModelTests(TestCase):
    def test_str_representation(self):
        client = Client.objects.create(name="John Doe", company="Acme Corp")
        self.assertEqual(str(client), "Acme Corp")
        
        client_no_company = Client.objects.create(name="Jane Smith")
        self.assertEqual(str(client_no_company), "Jane Smith")
    
    def test_active_project_count(self):
        client = Client.objects.create(name="Test Client")
        project_active = Project.objects.create(
            name="Active Project", client=client, status=Project.STATUS_ACTIVE
        )
        project_completed = Project.objects.create(
            name="Completed Project", client=client, status=Project.STATUS_COMPLETED
        )
        
        self.assertEqual(client.active_project_count, 1)


class ProjectModelTests(TestCase):
    def test_str_representation(self):
        client = Client.objects.create(name="Test Client")
        project = Project.objects.create(name="Test Project", client=client)
        self.assertEqual(str(project), "Test Project")
    
    def test_status_choices(self):
        self.assertEqual(Project.STATUS_PLANNING, "planning")
        self.assertEqual(Project.STATUS_ACTIVE, "active")
        self.assertEqual(Project.STATUS_ON_HOLD, "on_hold")
        self.assertEqual(Project.STATUS_COMPLETED, "completed")


class HostedWebsiteModelTests(TestCase):
    def setUp(self):
        self.client = Client.objects.create(name="Test Client")
        self.project = Project.objects.create(
            name="Test Project", client=self.client, status=Project.STATUS_ACTIVE
        )
    
    def test_str_representation(self):
        site = HostedWebsite.objects.create(
            project=self.project, domain="example.com"
        )
        self.assertEqual(str(site), "example.com")
    
    def test_days_until_calculation(self):
        site = HostedWebsite.objects.create(
            project=self.project, domain="example.com"
        )
        
        # Test with future date
        future_date = date.today() + timedelta(days=10)
        site.domain_expiry_date = future_date
        self.assertEqual(site.domain_days_left, 10)
        
        # Test with past date
        past_date = date.today() - timedelta(days=5)
        site.domain_expiry_date = past_date
        self.assertEqual(site.domain_days_left, -5)
        
        # Test with None
        site.domain_expiry_date = None
        self.assertIsNone(site.domain_days_left)
    
    def test_ssl_days_left(self):
        site = HostedWebsite.objects.create(
            project=self.project, domain="example.com"
        )
        
        future_date = date.today() + timedelta(days=30)
        site.ssl_expiry_date = future_date
        self.assertEqual(site.ssl_days_left, 30)
        
        site.ssl_expiry_date = None
        self.assertIsNone(site.ssl_days_left)
    
    def test_is_expiring_soon(self):
        site = HostedWebsite.objects.create(
            project=self.project, domain="example.com"
        )
        
        # Within threshold
        site.domain_expiry_date = date.today() + timedelta(days=15)
        self.assertTrue(site.is_expiring_soon(threshold=30))
        
        # Outside threshold
        site.domain_expiry_date = date.today() + timedelta(days=60)
        self.assertFalse(site.is_expiring_soon(threshold=30))
        
        # No expiry date
        site.domain_expiry_date = None
        site.ssl_expiry_date = None
        self.assertFalse(site.is_expiring_soon(threshold=30))
        
        # SSL expiring soon
        site.domain_expiry_date = None
        site.ssl_expiry_date = date.today() + timedelta(days=10)
        self.assertTrue(site.is_expiring_soon(threshold=30))


class InvoiceModelTests(TestCase):
    def setUp(self):
        self.client = Client.objects.create(name="Test Client")
    
    def test_str_representation(self):
        invoice = Invoice.objects.create(
            client=self.client,
            reference="INV-001",
            amount=1000.00,
            due_date=date.today() + timedelta(days=30)
        )
        self.assertEqual(str(invoice), "INV-001 - Test Client")
        
        invoice_no_ref = Invoice.objects.create(
            client=self.client,
            amount=500.00,
            due_date=date.today() + timedelta(days=30)
        )
        self.assertIn("Invoice #", str(invoice_no_ref))
    
    def test_auto_overdue_on_save(self):
        # Create pending invoice with past due date
        invoice = Invoice.objects.create(
            client=self.client,
            reference="INV-002",
            amount=1000.00,
            status=Invoice.STATUS_PENDING,
            due_date=date.today() - timedelta(days=5)
        )
        
        # Should auto-flip to overdue
        self.assertEqual(invoice.status, Invoice.STATUS_OVERDUE)
    
    def test_no_auto_overdue_for_paid(self):
        # Create paid invoice with past due date
        invoice = Invoice.objects.create(
            client=self.client,
            reference="INV-003",
            amount=1000.00,
            status=Invoice.STATUS_PAID,
            due_date=date.today() - timedelta(days=5)
        )
        
        # Should remain paid
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)
    
    def test_no_auto_overdue_for_future_due_date(self):
        # Create pending invoice with future due date
        invoice = Invoice.objects.create(
            client=self.client,
            reference="INV-004",
            amount=1000.00,
            status=Invoice.STATUS_PENDING,
            due_date=date.today() + timedelta(days=30)
        )
        
        # Should remain pending
        self.assertEqual(invoice.status, Invoice.STATUS_PENDING)
    
    def test_status_choices(self):
        self.assertEqual(Invoice.STATUS_PAID, "paid")
        self.assertEqual(Invoice.STATUS_PENDING, "pending")
        self.assertEqual(Invoice.STATUS_OVERDUE, "overdue")


class ViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = DjangoClient()
        self.client.login(username='testuser', password='testpass')
        
        # Create test data
        self.client_obj = Client.objects.create(name="Test Client", company="Test Corp")
        self.project = Project.objects.create(
            name="Test Project", client=self.client_obj, status=Project.STATUS_ACTIVE
        )
        self.site = HostedWebsite.objects.create(
            project=self.project, domain="example.com", status=HostedWebsite.STATUS_ONLINE
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj, reference="INV-001", amount=1000.00,
            due_date=date.today() + timedelta(days=30)
        )
    
    def test_overview_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard:overview'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_overview_accessible_when_logged_in(self):
        response = self.client.get(reverse('dashboard:overview'))
        self.assertEqual(response.status_code, 200)
    
    def test_client_list_view(self):
        response = self.client.get(reverse('dashboard:client_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Corp")
    
    def test_client_detail_view(self):
        response = self.client.get(reverse('dashboard:client_detail', args=[self.client_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Corp")
    
    def test_project_list_view(self):
        response = self.client.get(reverse('dashboard:project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")
    
    def test_project_list_filter_by_status(self):
        response = self.client.get(reverse('dashboard:project_list'), {'status': 'active'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")
        
        response = self.client.get(reverse('dashboard:project_list'), {'status': 'completed'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Project")
    
    def test_project_detail_view(self):
        response = self.client.get(reverse('dashboard:project_detail', args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")
    
    def test_site_list_view(self):
        response = self.client.get(reverse('dashboard:site_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "example.com")
    
    def test_site_list_filter_by_status(self):
        response = self.client.get(reverse('dashboard:site_list'), {'status': 'online'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "example.com")
        
        response = self.client.get(reverse('dashboard:site_list'), {'status': 'offline'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "example.com")
    
    def test_site_detail_view(self):
        response = self.client.get(reverse('dashboard:site_detail', args=[self.site.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "example.com")
    
    def test_invoice_list_view(self):
        response = self.client.get(reverse('dashboard:invoice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-001")
    
    def test_invoice_list_filter_by_status(self):
        response = self.client.get(reverse('dashboard:invoice_list'), {'status': 'pending'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-001")
    
    def test_invoice_detail_view(self):
        response = self.client.get(reverse('dashboard:invoice_detail', args=[self.invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-001")
    
    def test_client_create_view(self):
        response = self.client.get(reverse('dashboard:client_create'))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(reverse('dashboard:client_create'), {
            'name': 'New Client',
            'company': 'New Company',
            'email': 'test@example.com',
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(Client.objects.filter(company='New Company').exists())
    
    def test_project_create_view(self):
        response = self.client.get(reverse('dashboard:project_create'))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(reverse('dashboard:project_create'), {
            'name': 'New Project',
            'client': self.client_obj.pk,
            'status': Project.STATUS_ACTIVE,
            'start_date': date.today(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name='New Project').exists())
