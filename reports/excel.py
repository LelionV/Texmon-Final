"""
Builds the multi-sheet report workbook.

One button on the reports dashboard produces a single .xlsx containing:
  1. "P&L Report"  -- the summary sheet (revenue, cost of sales, gross
                      profit, expenses, net profit, margins, document counts)
  2. "Quotations"
  3. "Proforma Invoices"
  4. "Invoices"
  5. "Payments"
  6. "Expenses"

A plain CSV can't hold multiple sheets, so the full breakdown is delivered
as .xlsx; a single-sheet CSV of the summary is offered separately for
anyone who needs to pipe it somewhere simple.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1A7A4C")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
TITLE_FONT = Font(bold=True, size=14, color="1A7A4C")
LABEL_FONT = Font(bold=True, size=10)
MONEY_FMT = "#,##0.00"
THIN = Side(style="thin", color="DDDDDD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _write_header(ws, headers, row=1):
    for col, title in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    # Use the string form ("A2"): referencing ws.cell(row=2, ...) here would
    # instantiate that cell, pushing ws.max_row to 2 so the first append()
    # would leave a blank row between the header and the data.
    ws.freeze_panes = f"A{row + 1}"


def _autosize(ws, min_width=10, max_width=48):
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[letter].width = max(min_width, min(max_width, length + 2))


def _money_col(ws, columns, first_data_row=2):
    for row in ws.iter_rows(min_row=first_data_row):
        for cell in row:
            if cell.column in columns:
                cell.number_format = MONEY_FMT


def build_workbook(report):
    wb = Workbook()

    # ---------------------------------------------------------------- P&L
    ws = wb.active
    ws.title = "P&L Report"
    ws["A1"] = "PROFIT & LOSS REPORT"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (
        f"Period: {report['date_from']:%d/%m/%Y} "
        f"to {report['date_to']:%d/%m/%Y}"
    )
    ws["A2"].font = Font(italic=True, size=10, color="666666")

    # Income and expenses are shown in separate columns.
    # Net Amount shows the resulting contribution or deduction.
    rows = [
        ("", "", "", ""),
        ("REVENUE", "", "", ""),
        ("Sales Revenue (excluding VAT)", report["revenue_net"], 0, report["revenue_net"]),
        ("", "", "", ""),
        ("COST OF SALES", "", "", ""),
        (
            "Cost of Sales (estimated from item cost prices)",
            0,
            report["cost_of_sales"],
            -report["cost_of_sales"],
        ),
        ("GROSS PROFIT", "", "", report["gross_profit"]),
        ("Gross Margin %", "", "", report["gross_margin_pct"]),
        ("", "", "", ""),
        ("OPERATING EXPENSES", "", "", ""),
        (
            "Approved Operating Expenses",
            0,
            report["operating_expenses"],
            -report["operating_expenses"],
        ),
        (
            "All Expenses Recorded (including unapproved)",
            0,
            report["expenses_total_all"],
            -report["expenses_total_all"],
        ),
        ("", "", "", ""),
        ("NET PROFIT", "", "", report["net_profit"]),
        ("Net Margin %", "", "", report["net_margin_pct"]),
        ("", "", "", ""),
        ("CASH FLOW & VAT SUMMARY", "", "", ""),
        ("Cash Collected (including VAT)", report["revenue_collected"], 0, report["revenue_collected"]),
        ("VAT Charged (not income)", 0, report["invoiced_vat"], -report["invoiced_vat"]),
        ("Total Billed (including VAT)", report["revenue_invoiced"], 0, report["revenue_invoiced"]),
        ("Outstanding / Unpaid Balance", 0, report["outstanding"], -report["outstanding"]),
        ("", "", "", ""),
        ("DOCUMENT VOLUMES", "", "", ""),
        ("Quotations Created", report["counts"]["quotations"], "", ""),
        ("Quotations Value", report["quotations_value"], "", ""),
        ("Proforma Invoices Created", report["counts"]["proformas"], "", ""),
        ("Proforma Invoices Value", report["proformas_value"], "", ""),
        ("Invoices Processed", report["counts"]["invoices"], "", ""),
        ("Payments Received (count)", report["counts"]["payments"], "", ""),
        ("Expenses Recorded (count)", report["counts"]["expenses"], "", ""),
    ]

    headers = ["Description", "Income", "Expenses", "Net Amount"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center")

    for i, row_data in enumerate(rows, start=5):
        label, income, expenses, net_amount = row_data

        values = [label, income, expenses, net_amount]
        for col, value in enumerate(values, start=1):
            if value != "":
                ws.cell(row=i, column=col, value=value)

        is_section = (
            bool(label)
            and all(value == "" for value in row_data[1:])
            and label.isupper()
        )
        is_headline = label in ("GROSS PROFIT", "NET PROFIT")

        if is_section:
            for col in range(1, 5):
                cell = ws.cell(row=i, column=col)
                cell.font = Font(bold=True, size=11, color="1A7A4C")
                cell.fill = PatternFill("solid", fgColor="E2F0D9")

        elif is_headline:
            for col in range(1, 5):
                cell = ws.cell(row=i, column=col)
                cell.font = Font(bold=True, size=11, color="1A7A4C")
                cell.fill = PatternFill("solid", fgColor="D9EAD3")
                cell.border = Border(
                    top=Side(style="thin", color="1A7A4C"),
                    bottom=Side(style="double", color="1A7A4C"),
                )

        elif label:
            ws.cell(row=i, column=1).font = Font(size=10)

        # Format amounts and percentages.
        for col in (2, 3, 4):
            cell = ws.cell(row=i, column=col)
            if cell.value is None or cell.value == "":
                continue

            if "%" in label:
                cell.number_format = '0.00"%"'
            elif "Created" in label or "Processed" in label or "count)" in label:
                cell.number_format = "#,##0"
            elif isinstance(cell.value, (int, float)) or hasattr(cell.value, "quantize"):
                cell.number_format = MONEY_FMT

            if col in (2, 3, 4):
                cell.alignment = Alignment(horizontal="right")

    # General layout
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 20
    ws.freeze_panes = "A5"
    ws.sheet_view.showGridLines = False

    # -------------------------------------------------------- Quotations
    ws = wb.create_sheet("Quotations")
    _write_header(ws, [
        "Number", "Date", "Client", "Sales Rep", "Status",
        "Currency", "Subtotal", "VAT", "Grand Total",
    ])
    for q in report["quotations"]:
        ws.append([
            q.quotation_number, q.date, q.client.company_name,
            str(q.sales_representative) if q.sales_representative_id else "",
            q.get_status_display(), q.currency.code,
            q.subtotal, q.vat_total, q.grand_total,
        ])
    _money_col(ws, {7, 8, 9})
    _autosize(ws)

    # --------------------------------------------------- Proforma Invoices
    ws = wb.create_sheet("Proforma Invoices")
    _write_header(ws, [
        "PI Number", "Date", "From Quotation", "Client", "Status",
        "BL Number", "Currency", "Subtotal", "VAT", "Grand Total",
    ])
    for p in report["proformas"]:
        ws.append([
            p.pi_number, p.date, p.quotation.quotation_number,
            p.client.company_name, p.get_status_display(), p.bl_number,
            p.currency.code, p.subtotal, p.vat_total, p.grand_total,
        ])
    _money_col(ws, {8, 9, 10})
    _autosize(ws)

    # ----------------------------------------------------------- Invoices
    ws = wb.create_sheet("Invoices")
    _write_header(ws, [
        "Invoice Number", "Date", "Due Date", "From Proforma", "Client",
        "Status", "Currency", "Subtotal", "VAT", "Grand Total",
        "Paid", "Balance Due",
    ])
    for inv in report["invoices"]:
        ws.append([
            inv.invoice_number, inv.date, inv.due_date,
            inv.proforma_invoice.pi_number, inv.client.company_name,
            inv.get_status_display(), inv.currency.code,
            inv.subtotal, inv.vat_total, inv.grand_total,
            inv.paid_amount, inv.balance_due,
        ])
    _money_col(ws, {8, 9, 10, 11, 12})
    _autosize(ws)

    # ----------------------------------------------------------- Payments
    ws = wb.create_sheet("Payments")
    _write_header(ws, [
        "Date", "Invoice", "Client", "Method", "Reference",
        "Bank/Account", "Currency", "Amount",
    ])
    for pay in report["payments"]:
        ws.append([
            pay.payment_date, pay.invoice.invoice_number,
            pay.invoice.client.company_name,
            pay.get_payment_method_display(), pay.reference_number,
            pay.bank_account, pay.invoice.currency.code, pay.amount,
        ])
    _money_col(ws, {8})
    _autosize(ws)

    # ----------------------------------------------------------- Expenses
    ws = wb.create_sheet("Expenses")
    _write_header(ws, [
        "Expense Number", "Date", "Category", "Type", "Supplier",
        "Description", "Status", "Currency", "Amount", "VAT", "Total",
    ])
    for exp in report["expenses"]:
        ws.append([
            exp.expense_number, exp.date, exp.category.name,
            exp.category.get_category_type_display(),
            exp.supplier.company_name if exp.supplier_id else "",
            exp.description, exp.get_status_display(), exp.currency.code,
            exp.amount, exp.vat_amount, exp.total_amount,
        ])
    _money_col(ws, {9, 10, 11})
    _autosize(ws)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
