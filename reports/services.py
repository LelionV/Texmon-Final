"""
Report aggregation. One function, `build_report(date_from, date_to)`,
produces every figure the dashboard and the Excel export both use, so the
on-screen numbers and the exported workbook can never disagree.

Profit & loss model used here
-----------------------------
- Revenue (Net)       : sum of Invoice.subtotal (EXCLUDING VAT) for invoices
                        dated in the period. VAT is collected on behalf of
                        the tax authority and is a liability, not income, so
                        every profit figure below is built on this number.
- Revenue (Billed)    : Invoice.grand_total (including VAT) -- shown for
                        reference and for receivables, never used in profit.
- Revenue (Collected) : sum of Payment.amount received in the period --
                        what actually came in. Shown alongside invoiced
                        revenue because in freight forwarding the gap
                        between the two is the thing finance cares about.
- Cost of Sales       : for every invoice line in the period, the linked
                        master Item's cost_price x quantity. Lines with no
                        linked Item (free-text lines) contribute 0, so this
                        is explicitly labelled an *estimate* in the UI.
- Gross Profit        : Revenue (Net, excl. VAT) - Cost of Sales.
- Operating Expenses  : sum of approved Expense.amount dated in the period
                        (VAT excluded -- VAT is not a P&L cost).
- Net Profit          : Gross Profit - Operating Expenses.

Everything is filtered on each document's own date field, so a range of
1 Jan - 31 Mar gives you exactly the documents dated in that quarter.
"""

from decimal import Decimal

from django.db.models import Count, Sum

ZERO = Decimal("0.00")


def _money(value):
    return value if value is not None else ZERO


def build_report(date_from, date_to):
    from quotations.models import Quotation
    from proforma.models import ProformaInvoice
    from invoicing.models import Invoice, InvoiceItem, Payment
    from expenses.models import Expense

    quotations = (
        Quotation.objects.filter(date__gte=date_from, date__lte=date_to)
        .select_related("client", "currency", "sales_representative")
        .order_by("date", "id")
    )
    proformas = (
        ProformaInvoice.objects.filter(date__gte=date_from, date__lte=date_to)
        .select_related("client", "currency", "quotation")
        .order_by("date", "id")
    )
    invoices = (
        Invoice.objects.filter(date__gte=date_from, date__lte=date_to)
        .select_related("client", "currency", "proforma_invoice")
        .order_by("date", "id")
    )
    payments = (
        Payment.objects.filter(payment_date__gte=date_from, payment_date__lte=date_to)
        .select_related("invoice", "invoice__client", "invoice__currency")
        .order_by("payment_date", "id")
    )
    expenses = (
        Expense.objects.filter(date__gte=date_from, date__lte=date_to)
        .select_related("category", "supplier", "currency")
        .order_by("date", "id")
    )

    # -- headline totals ---------------------------------------------------
    revenue_invoiced = _money(invoices.aggregate(t=Sum("grand_total"))["t"])
    revenue_collected = _money(payments.aggregate(t=Sum("amount"))["t"])
    invoiced_subtotal = _money(invoices.aggregate(t=Sum("subtotal"))["t"])
    invoiced_vat = _money(invoices.aggregate(t=Sum("vat_total"))["t"])
    outstanding = _money(invoices.aggregate(t=Sum("balance_due"))["t"])

    # Cost of sales: only lines linked to a master Item carry a known cost.
    cost_of_sales = ZERO
    for line in InvoiceItem.objects.filter(
        invoice__date__gte=date_from, invoice__date__lte=date_to, item__isnull=False,
    ).select_related("item"):
        cost_of_sales += (line.item.cost_price or ZERO) * (line.quantity or ZERO)
    cost_of_sales = cost_of_sales.quantize(Decimal("0.01"))

    approved_expenses = expenses.filter(status="approved")
    operating_expenses = _money(approved_expenses.aggregate(t=Sum("amount"))["t"])

    # Profit is measured on revenue EXCLUDING VAT (see module docstring).
    revenue_net = invoiced_subtotal
    gross_profit = revenue_net - cost_of_sales
    net_profit = gross_profit - operating_expenses
    gross_margin_pct = (
        (gross_profit / revenue_net * 100).quantize(Decimal("0.01"))
        if revenue_net else ZERO
    )
    net_margin_pct = (
        (net_profit / revenue_net * 100).quantize(Decimal("0.01"))
        if revenue_net else ZERO
    )

    # Mixed currencies can't be added together honestly: flag it.
    currencies_used = sorted(set(
        list(invoices.values_list("currency__code", flat=True))
        + list(approved_expenses.values_list("currency__code", flat=True))
    ))

    # -- per-status breakdowns (useful on the dashboard) -------------------
    def status_counts(qs):
        return {
            row["status"]: row["n"]
            for row in qs.values("status").annotate(n=Count("id")).order_by()
        }

    return {
        "date_from": date_from,
        "date_to": date_to,

        "quotations": quotations,
        "proformas": proformas,
        "invoices": invoices,
        "payments": payments,
        "expenses": expenses,

        "counts": {
            "quotations": quotations.count(),
            "proformas": proformas.count(),
            "invoices": invoices.count(),
            "payments": payments.count(),
            "expenses": expenses.count(),
        },
        "status_counts": {
            "quotations": status_counts(quotations),
            "proformas": status_counts(proformas),
            "invoices": status_counts(invoices),
            "expenses": status_counts(expenses),
        },

        "quotations_value": _money(quotations.aggregate(t=Sum("grand_total"))["t"]),
        "proformas_value": _money(proformas.aggregate(t=Sum("grand_total"))["t"]),

        "revenue_net": revenue_net,
        "currencies_used": currencies_used,
        "mixed_currency": len(currencies_used) > 1,
        "revenue_invoiced": revenue_invoiced,
        "revenue_collected": revenue_collected,
        "invoiced_subtotal": invoiced_subtotal,
        "invoiced_vat": invoiced_vat,
        "outstanding": outstanding,
        "cost_of_sales": cost_of_sales,
        "gross_profit": gross_profit,
        "operating_expenses": operating_expenses,
        "expenses_total_all": _money(expenses.aggregate(t=Sum("amount"))["t"]),
        "net_profit": net_profit,
        "gross_margin_pct": gross_margin_pct,
        "net_margin_pct": net_margin_pct,
    }
