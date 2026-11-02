import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from expenses.models import Expense, ExpenseCategory
from invoicing.models import Invoice, Payment
from masters.models import Client, Currency, Item, PaymentTerm, Supplier
from proforma.models import ProformaInvoice
from quotations.models import Quotation, QuotationItem
from .services import build_report

User = get_user_model()


class ReportBuildTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.usd = Currency.objects.create(name="US Dollar", code="USD", symbol="$", exchange_rate=1)
        self.terms = PaymentTerm.objects.create(name="30 Days", days=30)
        self.user = User.objects.create_user(username="fin1", password="x")
        self.client_obj = Client.objects.create(company_name="Acme Ltd", currency=self.usd, payment_terms=self.terms)
        self.supplier = Supplier.objects.create(company_name="Fuel Co", currency=self.usd, payment_terms=self.terms)
        self.category = ExpenseCategory.objects.create(
            name="Fuel", category_type=ExpenseCategory.CategoryType.OPERATIONS,
        )
        self.item = Item.objects.create(
            code="FRT-001", name="Freight", item_type=Item.ItemType.FREIGHT, currency=self.usd,
            cost_price=Decimal("600.00"), selling_price=Decimal("1000.00"),
            vat_applicable=False, vat_percentage=Decimal("0"),
        )

    def _full_chain(self, amount="1000.00", qty=1, with_item=True):
        q = Quotation.objects.create(client=self.client_obj, currency=self.usd, payment_terms=self.terms)
        QuotationItem.objects.create(
            quotation=q, item=self.item if with_item else None,
            description="Freight", quantity=qty, unit_price=Decimal(amount),
        )
        q.submit(user=self.user)
        q.approve(user=self.user)
        pi = ProformaInvoice.create_from_quotation(q, user=self.user)
        pi.submit(user=self.user)
        pi.approve(user=self.user)
        return Invoice.create_from_proforma(pi, user=self.user)

    def _range(self):
        return self.today - datetime.timedelta(days=1), self.today + datetime.timedelta(days=1)

    def test_counts_every_document_type(self):
        invoice = self._full_chain()
        Payment.objects.create(invoice=invoice, amount=Decimal("400.00"), created_by=self.user)
        Expense.objects.create(
            category=self.category, supplier=self.supplier, description="Diesel",
            amount=Decimal("250.00"), currency=self.usd,
        )
        date_from, date_to = self._range()
        report = build_report(date_from, date_to)

        self.assertEqual(report["counts"]["quotations"], 1)
        self.assertEqual(report["counts"]["proformas"], 1)
        self.assertEqual(report["counts"]["invoices"], 1)
        self.assertEqual(report["counts"]["payments"], 1)
        self.assertEqual(report["counts"]["expenses"], 1)

    def test_profit_and_loss_maths(self):
        # Revenue 1000 (no VAT), cost of sales 600 (item cost 600 x qty 1)
        self._full_chain(amount="1000.00", qty=1)
        expense = Expense.objects.create(
            category=self.category, description="Diesel",
            amount=Decimal("150.00"), currency=self.usd,
        )
        expense.submit(user=self.user)
        expense.approve(user=self.user)

        date_from, date_to = self._range()
        report = build_report(date_from, date_to)

        self.assertEqual(report["revenue_invoiced"], Decimal("1000.00"))
        self.assertEqual(report["cost_of_sales"], Decimal("600.00"))
        self.assertEqual(report["gross_profit"], Decimal("400.00"))
        self.assertEqual(report["operating_expenses"], Decimal("150.00"))
        self.assertEqual(report["net_profit"], Decimal("250.00"))
        self.assertEqual(report["gross_margin_pct"], Decimal("40.00"))
        self.assertEqual(report["net_margin_pct"], Decimal("25.00"))

    def test_vat_is_excluded_from_profit(self):
        """Regression: profit was built on grand_total (incl. VAT), overstating
        it by the VAT charged. 1000 net + 16% VAT, cost 600, expenses 100:
        gross must be 400 and net 300 -- not 560 / 460."""
        vat_item = Item.objects.create(
            code="VAT-1", name="Taxed freight", item_type=Item.ItemType.FREIGHT, currency=self.usd,
            cost_price=Decimal("600.00"), selling_price=Decimal("1000.00"),
            vat_applicable=True, vat_percentage=Decimal("16.00"),
        )
        q = Quotation.objects.create(client=self.client_obj, currency=self.usd, payment_terms=self.terms)
        QuotationItem.objects.create(
            quotation=q, item=vat_item, description="Taxed freight", quantity=1,
            unit_price=Decimal("1000.00"), vat_percentage=Decimal("16.00"),
        )
        q.submit(user=self.user)
        q.approve(user=self.user)
        pi = ProformaInvoice.create_from_quotation(q, user=self.user)
        pi.submit(user=self.user)
        pi.approve(user=self.user)
        Invoice.create_from_proforma(pi, user=self.user)
        expense = Expense.objects.create(
            category=self.category, description="Diesel", amount=Decimal("100.00"), currency=self.usd,
        )
        expense.submit(user=self.user)
        expense.approve(user=self.user)

        date_from, date_to = self._range()
        report = build_report(date_from, date_to)

        self.assertEqual(report["revenue_net"], Decimal("1000.00"))
        self.assertEqual(report["invoiced_vat"], Decimal("160.00"))
        self.assertEqual(report["revenue_invoiced"], Decimal("1160.00"))   # billed, incl. VAT
        self.assertEqual(report["gross_profit"], Decimal("400.00"))
        self.assertEqual(report["net_profit"], Decimal("300.00"))
        self.assertEqual(report["net_margin_pct"], Decimal("30.00"))

    def test_mixed_currency_is_flagged(self):
        kes = Currency.objects.create(name="Kenyan Shilling", code="KES", symbol="KSh", exchange_rate=130)
        self._full_chain()
        Expense.objects.create(
            category=self.category, description="Local cost", amount=Decimal("5000.00"), currency=kes,
        ).submit(user=self.user)
        exp = Expense.objects.get(description="Local cost")
        exp.approve(user=self.user)

        date_from, date_to = self._range()
        report = build_report(date_from, date_to)
        self.assertTrue(report["mixed_currency"])
        self.assertEqual(report["currencies_used"], ["KES", "USD"])

    def test_single_currency_not_flagged(self):
        self._full_chain()
        date_from, date_to = self._range()
        self.assertFalse(build_report(date_from, date_to)["mixed_currency"])

    def test_unapproved_expenses_excluded_from_operating_expenses(self):
        self._full_chain()
        Expense.objects.create(
            category=self.category, description="Draft expense",
            amount=Decimal("999.00"), currency=self.usd,
        )  # left in Draft
        date_from, date_to = self._range()
        report = build_report(date_from, date_to)
        self.assertEqual(report["operating_expenses"], Decimal("0.00"))
        self.assertEqual(report["expenses_total_all"], Decimal("999.00"))

    def test_documents_outside_range_excluded(self):
        self._full_chain()
        old_from = self.today - datetime.timedelta(days=400)
        old_to = self.today - datetime.timedelta(days=300)
        report = build_report(old_from, old_to)
        self.assertEqual(report["counts"]["invoices"], 0)
        self.assertEqual(report["revenue_invoiced"], Decimal("0.00"))
        self.assertEqual(report["net_profit"], Decimal("0.00"))

    def test_free_text_line_contributes_no_cost_of_sales(self):
        self._full_chain(amount="1000.00", with_item=False)
        date_from, date_to = self._range()
        report = build_report(date_from, date_to)
        self.assertEqual(report["cost_of_sales"], Decimal("0.00"))
        self.assertEqual(report["gross_profit"], Decimal("1000.00"))


class ReportViewTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(name="US Dollar", code="USD", symbol="$", exchange_rate=1)
        self.terms = PaymentTerm.objects.create(name="30 Days", days=30)
        Client.objects.create(company_name="Acme Ltd", currency=self.usd, payment_terms=self.terms)

        report_perms = Permission.objects.filter(content_type__app_label="reports")
        self.finance_group = Group.objects.create(name="Finance Officer")
        self.finance_group.permissions.add(*report_perms)
        self.finance_user = User.objects.create_user(username="fin1", password="pass1234")
        self.finance_user.groups.add(self.finance_group)

        self.viewer_group = Group.objects.create(name="Management Viewer")
        self.viewer_group.permissions.add(
            Permission.objects.get(content_type__app_label="reports", codename="view_reports")
        )
        self.viewer = User.objects.create_user(username="viewer1", password="pass1234")
        self.viewer.groups.add(self.viewer_group)

        self.nobody = User.objects.create_user(username="nobody1", password="pass1234")

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 302)

    def test_user_without_permission_denied(self):
        self.client.login(username="nobody1", password="pass1234")
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 403)

    def test_finance_officer_sees_dashboard(self):
        self.client.login(username="fin1", password="pass1234")
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("report", resp.context)

    def test_excel_export_returns_xlsx(self):
        self.client.login(username="fin1", password="pass1234")
        resp = self.client.get(reverse("reports:export_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", resp["Content-Disposition"])
        # xlsx files are zip archives -- check the magic bytes
        self.assertTrue(resp.content.startswith(b"PK"))

    def test_excel_export_contains_all_expected_sheets(self):
        from io import BytesIO
        from openpyxl import load_workbook

        self.client.login(username="fin1", password="pass1234")
        resp = self.client.get(reverse("reports:export_excel"))
        wb = load_workbook(BytesIO(resp.content))
        self.assertEqual(
            wb.sheetnames,
            ["P&L Report", "Quotations", "Proforma Invoices", "Invoices", "Payments", "Expenses"],
        )

    def test_detail_sheet_data_starts_immediately_below_header(self):
        """Regression: setting freeze_panes via ws.cell() instantiated that
        cell and pushed the first appended row down, leaving a blank row
        between the header and the data."""
        from io import BytesIO
        from openpyxl import load_workbook

        # Give the report something to list so there's a data row at all.
        usd = self.usd
        terms = self.terms
        client_obj = Client.objects.first()
        q = Quotation.objects.create(client=client_obj, currency=usd, payment_terms=terms)
        QuotationItem.objects.create(quotation=q, description="Freight", quantity=1, unit_price=Decimal("100"))

        self.client.login(username="fin1", password="pass1234")
        resp = self.client.get(reverse("reports:export_excel"))
        wb = load_workbook(BytesIO(resp.content))
        ws = wb["Quotations"]
        self.assertEqual(ws.cell(row=1, column=1).value, "Number")
        self.assertEqual(ws.cell(row=2, column=1).value, q.quotation_number)

    def test_csv_export(self):
        self.client.login(username="fin1", password="pass1234")
        resp = self.client.get(reverse("reports:export_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("Net Profit", resp.content.decode())

    def test_viewer_can_see_dashboard_but_not_export(self):
        self.client.login(username="viewer1", password="pass1234")
        self.assertEqual(self.client.get(reverse("reports:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports:export_excel")).status_code, 403)

    def test_date_range_filter_applied(self):
        self.client.login(username="fin1", password="pass1234")
        resp = self.client.get(reverse("reports:dashboard"), {
            "date_from": "2026-01-01", "date_to": "2026-03-31",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context["report"]["date_from"]), "2026-01-01")
        self.assertEqual(str(resp.context["report"]["date_to"]), "2026-03-31")
