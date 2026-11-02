"""
Reports dashboard + exports.

Both the dashboard and the exports run the exact same `build_report()`
aggregation over the same date range, so what you see on screen is what
lands in the workbook.
"""

import csv

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.views.generic import TemplateView

from .excel import build_workbook
from .forms import ReportFilterForm
from .services import build_report


class ReportsDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/dashboard.html"
    permission_required = "reports.view_reports"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from, date_to = ReportFilterForm.resolve_range(self.request)
        ctx["form"] = ReportFilterForm(self.request.GET or None)
        ctx["report"] = build_report(date_from, date_to)
        ctx["querystring"] = f"date_from={date_from}&date_to={date_to}"
        return ctx


@login_required
@permission_required("reports.export_reports", raise_exception=True)
def export_excel(request):
    date_from, date_to = ReportFilterForm.resolve_range(request)
    report = build_report(date_from, date_to)
    content = build_workbook(report)

    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = f"profit_and_loss_{date_from:%Y%m%d}_{date_to:%Y%m%d}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required("reports.export_reports", raise_exception=True)
def export_csv(request):
    """Single-sheet CSV of the P&L summary only -- CSV can't carry the
    multi-sheet breakdown, which is what the Excel export is for."""
    date_from, date_to = ReportFilterForm.resolve_range(request)
    report = build_report(date_from, date_to)

    response = HttpResponse(content_type="text/csv")
    filename = f"profit_and_loss_summary_{date_from:%Y%m%d}_{date_to:%Y%m%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Profit & Loss Report"])
    writer.writerow([f"Period: {date_from:%d/%m/%Y} to {date_to:%d/%m/%Y}"])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    for label, value in [
        ("Revenue (excl. VAT)", report["revenue_net"]),
        ("VAT Charged (excluded from profit)", report["invoiced_vat"]),
        ("Total Billed (incl. VAT)", report["revenue_invoiced"]),
        ("Cash Collected (incl. VAT)", report["revenue_collected"]),
        ("Outstanding / Unpaid Balance", report["outstanding"]),
        ("Cost of Sales (estimated)", report["cost_of_sales"]),
        ("Gross Profit", report["gross_profit"]),
        ("Gross Margin %", report["gross_margin_pct"]),
        ("Approved Expenses", report["operating_expenses"]),
        ("Net Profit", report["net_profit"]),
        ("Net Margin %", report["net_margin_pct"]),
        ("Quotations Created", report["counts"]["quotations"]),
        ("Proforma Invoices Created", report["counts"]["proformas"]),
        ("Invoices Processed", report["counts"]["invoices"]),
        ("Payments Received (count)", report["counts"]["payments"]),
        ("Expenses Recorded (count)", report["counts"]["expenses"]),
    ]:
        writer.writerow([label, value])
    return response
