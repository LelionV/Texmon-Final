from datetime import timedelta

from django import forms
from django.utils import timezone


class ReportFilterForm(forms.Form):
    """Date-range filter shared by the dashboard and both export buttons.
    Defaults to the last 30 days so the page is useful on first load."""

    date_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data:
            today = timezone.localdate()
            self.fields["date_from"].initial = today - timedelta(days=30)
            self.fields["date_to"].initial = today

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("'Date From' must be on or before 'Date To'.")
        return cleaned

    @staticmethod
    def resolve_range(request):
        """Returns (date_from, date_to) from the querystring, falling back
        to the last 30 days. Used by the export views so an export always
        covers exactly the range currently shown on the dashboard."""
        today = timezone.localdate()
        form = ReportFilterForm(request.GET or None)
        if request.GET and form.is_valid():
            return form.cleaned_data["date_from"], form.cleaned_data["date_to"]
        return today - timedelta(days=30), today
