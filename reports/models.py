"""
reports app: profit & loss reporting across the whole document pipeline.

This app owns no business data of its own -- every figure it shows is
aggregated live from quotations, proforma, invoicing, expenses and
accounting. It therefore has no real tables; `ReportPermission` exists
purely as a permission anchor, because Django attaches permissions to
models and this app needs its own `view_reports` / `export_reports`
permissions so the Reports section can be granted per-role through the
same Groups mechanism as everything else.

`managed = False` means no table is ever created for it, and
`default_permissions = ()` suppresses the usual add/change/delete/view
permissions in favour of the two explicit ones below.
"""

from django.db import models


class ReportPermission(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_reports", "Can view reports and the reports dashboard"),
            ("export_reports", "Can export reports to Excel/CSV"),
        ]
        verbose_name = "Report Access"
        verbose_name_plural = "Report Access"
