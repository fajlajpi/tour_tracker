import json
from datetime import date
from django import forms
from django.forms import inlineformset_factory

from .models import Tour, Tip, TourType, ExchangeRate


class TourForm(forms.ModelForm):
    class Meta:
        model = Tour
        fields = [
            'tour_type', 'tour_date', 'pax_count', 'notes',
            'fixed_income',
            'expense_1_name', 'expense_1_amount',
            'expense_2_name', 'expense_2_amount',
            'expense_3_name', 'expense_3_amount',
        ]
        widgets = {
            'tour_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'fixed_income': 'Fixed Income (CZK)',
            'expense_1_name': 'Expense 1 — Location',
            'expense_1_amount': 'Expense 1 — Amount (CZK)',
            'expense_2_name': 'Expense 2 — Location',
            'expense_2_amount': 'Expense 2 — Amount (CZK)',
            'expense_3_name': 'Expense 3 — Location',
            'expense_3_amount': 'Expense 3 — Amount (CZK)',
        }

    def food_tour_type_ids_json(self):
        ids = list(TourType.objects.filter(is_food_tour=True).values_list('pk', flat=True))
        return json.dumps(ids)


# Inline formset for tips — used on the create/edit tour form.
# extra=0: no blank rows by default; JS adds them dynamically.
TipFormSet = inlineformset_factory(
    Tour,
    Tip,
    fields=['amount', 'currency'],
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
    widgets={
        'amount': forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': '0.00',
            'step': '0.01',
        }),
        'currency': forms.Select(attrs={'class': 'form-select form-select-sm'}),
    },
)


class TipForm(forms.ModelForm):
    """Used for the quick-add panel and inline edit on tour detail."""
    class Meta:
        model = Tip
        fields = ['amount', 'currency']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
            }),
            'currency': forms.Select(attrs={'class': 'form-select'}),
        }


class ExchangeRateForm(forms.ModelForm):
    class Meta:
        model = ExchangeRate
        fields = ['currency', 'date', 'rate_to_czk']
        widgets = {
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'rate_to_czk': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'placeholder': '0.0000',
            }),
        }
        labels = {'rate_to_czk': 'Rate to CZK'}


class CNBFetchForm(forms.Form):
    date = forms.DateField(
        label='Fetch rates for date',
        initial=date.today,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
