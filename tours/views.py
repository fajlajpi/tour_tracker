import urllib.request
from collections import defaultdict
from datetime import datetime, date
from calendar import month_name

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .models import Tour, Tip, TourType, Currency, ExchangeRate
from .forms import TourForm, TipFormSet, TipForm, ExchangeRateForm, CNBFetchForm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _available_periods():
    """List of date objects (first-of-month) for every month that has tours."""
    return list(Tour.objects.dates('tour_date', 'month', order='ASC'))


def _tour_summary(tours):
    """Aggregated totals for a list (or queryset) of tours."""
    tour_list = list(tours)
    total_pax = sum(t.pax_count for t in tour_list)
    total_tips = sum(t.get_total_tips() for t in tour_list)
    # Net settlement: regular payins minus food tour salaries + expense credits.
    total_settlement = sum(t.get_settlement_contribution() for t in tour_list)
    total_profit = sum(t.calculate_profit() for t in tour_list)
    return {
        'total_tours': len(tour_list),
        'total_pax': total_pax,
        'total_tips': total_tips,
        'total_payin': total_settlement,
        'total_profit': total_profit,
        'avg_tips_per_pax': total_tips / total_pax if total_pax else 0,
    }


def _fetch_cnb_rates(target_date):
    """
    Fetch exchange rates from the Czech National Bank for target_date.
    Returns (actual_date, {currency_code: rate_to_czk}).
    CNB publishes on business days only; weekends/holidays return the previous day's rates.
    """
    date_str = target_date.strftime('%d.%m.%Y')
    url = (
        'https://www.cnb.cz/en/financial-markets/foreign-exchange-market/'
        'central-bank-exchange-rate-fixing/central-bank-exchange-rate-fixing/'
        f'daily.txt?date={date_str}'
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'TourTracker/1.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode('utf-8')

    lines = content.strip().split('\n')
    if len(lines) < 3:
        raise ValueError('Unexpected response format from CNB')

    # First line: "19 Mar 2026 #58"
    actual_date = datetime.strptime(lines[0].split('#')[0].strip(), '%d %b %Y').date()

    rates = {}
    for line in lines[2:]:        # skip date line and header
        parts = line.strip().split('|')
        if len(parts) == 5:
            _, _, amount_str, code, rate_str = parts
            try:
                rates[code] = float(rate_str.replace(',', '.')) / int(amount_str)
            except (ValueError, ZeroDivisionError):
                continue

    return actual_date, rates


# ---------------------------------------------------------------------------
# Tour views
# ---------------------------------------------------------------------------

class TourListView(LoginRequiredMixin, ListView):
    model = Tour
    template_name = 'tours/tour_list.html'
    context_object_name = 'tours'
    ordering = ['-tour_date']
    paginate_by = 20

    def get_queryset(self):
        return (
            Tour.objects
            .order_by('-tour_date')
            .select_related('tour_type')
            .prefetch_related('tips__currency')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        current_month_tours = list(Tour.objects.filter(
            tour_date__year=today.year, tour_date__month=today.month
        ).select_related('tour_type').prefetch_related('tips__currency'))
        ytd_tours = list(Tour.objects.filter(
            tour_date__year=today.year
        ).select_related('tour_type').prefetch_related('tips__currency'))

        month_tips = sum(t.get_total_tips() for t in current_month_tours)
        month_profit = sum(t.calculate_profit() for t in current_month_tours)
        ytd_tips = sum(t.get_total_tips() for t in ytd_tours)
        ytd_profit = sum(t.calculate_profit() for t in ytd_tours)

        # Warning icons: compute per tour for the current page only
        tour_warnings = {}
        for tour in context['tours']:
            w = tour.get_warnings()
            if w:
                tour_warnings[tour.pk] = w

        context.update({
            'current_month_name': month_name[today.month],
            'current_year': today.year,
            'month_tours': len(current_month_tours),
            'month_tips': month_tips,
            'month_profit': month_profit,
            'ytd_tours': len(ytd_tours),
            'ytd_tips': ytd_tips,
            'ytd_profit': ytd_profit,
            'tour_warnings': tour_warnings,
        })
        return context


class TourDetailView(LoginRequiredMixin, DetailView):
    model = Tour
    template_name = 'tours/tour_detail.html'
    context_object_name = 'tour'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tour = self.get_object()
        tips = tour.tips.select_related('currency').all()
        context['tips'] = tips
        context['total_tips_czk'] = tour.get_total_tips()
        context['payin'] = tour.calculate_payin()
        context['profit'] = tour.calculate_profit()
        context['tips_per_pax'] = tour.calculate_tips_per_pax()
        context['total_expenses'] = tour.get_total_expenses()
        context['tip_form'] = TipForm()
        context['currencies'] = Currency.objects.all()
        context['warnings'] = tour.get_warnings()
        return context


class TourCreateView(LoginRequiredMixin, CreateView):
    model = Tour
    form_class = TourForm
    template_name = 'tours/tour_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['tip_formset'] = TipFormSet(self.request.POST, prefix='tips')
        else:
            context['tip_formset'] = TipFormSet(prefix='tips')
        return context

    def form_valid(self, form):
        tip_formset = TipFormSet(self.request.POST, prefix='tips')
        if tip_formset.is_valid():
            self.object = form.save()
            tip_formset.instance = self.object
            tip_formset.save()
            return HttpResponseRedirect(self.get_success_url())
        # Re-render with formset errors
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse('tour-detail', kwargs={'pk': self.object.pk})


class TourUpdateView(LoginRequiredMixin, UpdateView):
    model = Tour
    form_class = TourForm
    template_name = 'tours/tour_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['tip_formset'] = TipFormSet(
                self.request.POST, instance=self.object, prefix='tips'
            )
        else:
            context['tip_formset'] = TipFormSet(instance=self.object, prefix='tips')
        return context

    def form_valid(self, form):
        tip_formset = TipFormSet(
            self.request.POST, instance=self.get_object(), prefix='tips'
        )
        if tip_formset.is_valid():
            self.object = form.save()
            tip_formset.instance = self.object
            tip_formset.save()
            return HttpResponseRedirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse('tour-detail', kwargs={'pk': self.object.pk})


class TourDeleteView(LoginRequiredMixin, DeleteView):
    model = Tour
    template_name = 'tours/tour_confirm_delete.html'
    success_url = reverse_lazy('tour-list')


# ---------------------------------------------------------------------------
# Tip views
# ---------------------------------------------------------------------------

class TipCreateView(LoginRequiredMixin, CreateView):
    """Quick-add from the tour detail page inline panel."""
    model = Tip
    form_class = TipForm

    def form_valid(self, form):
        form.instance.tour_id = self.kwargs['tour_id']
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('tour-detail', kwargs={'pk': self.kwargs['tour_id']})

    def form_invalid(self, form):
        return HttpResponseRedirect(
            reverse('tour-detail', kwargs={'pk': self.kwargs['tour_id']})
        )


class TipUpdateView(LoginRequiredMixin, UpdateView):
    """Inline edit from the tour detail page."""
    model = Tip
    form_class = TipForm

    def get_success_url(self):
        return reverse('tour-detail', kwargs={'pk': self.object.tour_id})

    def get(self, request, *args, **kwargs):
        # No dedicated GET page — redirect back to tour detail
        return HttpResponseRedirect(
            reverse('tour-detail', kwargs={'pk': self.get_object().tour_id})
        )

    def form_invalid(self, form):
        return HttpResponseRedirect(
            reverse('tour-detail', kwargs={'pk': self.get_object().tour_id})
        )


class TipDeleteView(LoginRequiredMixin, DeleteView):
    model = Tip

    def get_success_url(self):
        return reverse('tour-detail', kwargs={'pk': self.object.tour_id})

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(
            reverse('tour-detail', kwargs={'pk': self.get_object().tour_id})
        )


# ---------------------------------------------------------------------------
# Exchange rate views
# ---------------------------------------------------------------------------

class ExchangeRateView(LoginRequiredMixin, ListView):
    model = ExchangeRate
    template_name = 'tours/exchange_rates.html'
    context_object_name = 'rates'

    def get_queryset(self):
        return (
            ExchangeRate.objects
            .select_related('currency')
            .order_by('-date', 'currency__code')[:200]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ExchangeRateForm(initial={'date': date.today()})
        context['fetch_form'] = CNBFetchForm(initial={'date': date.today()})

        # Group rates by date for display
        grouped = defaultdict(list)
        for rate in context['rates']:
            grouped[rate.date].append(rate)
        context['rates_by_date'] = dict(sorted(grouped.items(), reverse=True))
        return context

    def post(self, request, *args, **kwargs):
        form = ExchangeRateForm(request.POST)
        if form.is_valid():
            try:
                obj, created = ExchangeRate.objects.update_or_create(
                    currency=form.cleaned_data['currency'],
                    date=form.cleaned_data['date'],
                    defaults={'rate_to_czk': form.cleaned_data['rate_to_czk']},
                )
                action = 'Saved' if created else 'Updated'
                messages.success(request, f'{action} rate for {obj.currency} on {obj.date}.')
            except Exception as e:
                messages.error(request, f'Could not save rate: {e}')
        else:
            messages.error(request, 'Invalid data — check the form.')
        return redirect('exchange-rates')


class CNBFetchView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = CNBFetchForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Invalid date.')
            return redirect('exchange-rates')

        target_date = form.cleaned_data['date']

        try:
            actual_date, cnb_rates = _fetch_cnb_rates(target_date)
        except Exception as e:
            messages.error(request, f'Could not fetch CNB rates: {e}')
            return redirect('exchange-rates')

        currencies = Currency.objects.exclude(code='CZK')
        saved = skipped = not_in_cnb = 0

        for currency in currencies:
            if currency.code in cnb_rates:
                ExchangeRate.objects.update_or_create(
                    currency=currency,
                    date=actual_date,
                    defaults={'rate_to_czk': cnb_rates[currency.code]},
                )
                saved += 1
            else:
                not_in_cnb += 1

        msg = f'Fetched CNB rates for {actual_date}'
        if actual_date != target_date:
            msg += f' (requested {target_date} — CNB used nearest business day)'
        msg += f': {saved} rate(s) saved'
        if not_in_cnb:
            msg += f', {not_in_cnb} currency/ies not found in CNB list'
        msg += '.'
        messages.success(request, msg)
        return redirect('exchange-rates')


# ---------------------------------------------------------------------------
# Stats views
# ---------------------------------------------------------------------------

class MonthlyStatsView(LoginRequiredMixin, ListView):
    model = Tour
    template_name = 'tours/monthly_stats.html'
    context_object_name = 'monthly_stats'

    def _get_year_month(self):
        today = datetime.now()
        try:
            year = int(self.request.GET.get('year', today.year))
            month = int(self.request.GET.get('month', today.month))
        except ValueError:
            year, month = today.year, today.month
        return year, month

    def get_queryset(self):
        year, month = self._get_year_month()
        return (
            Tour.objects
            .filter(tour_date__year=year, tour_date__month=month)
            .order_by('tour_date')
            .select_related('tour_type')
            .prefetch_related('tips__currency')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self._get_year_month()
        tours = list(self.get_queryset())

        periods = _available_periods()
        available_years = sorted(set(d.year for d in periods))
        available_months = [
            (d.month, month_name[d.month]) for d in periods if d.year == year
        ]
        if not available_months and periods:
            fallback_year = max(d.year for d in periods)
            available_months = [
                (d.month, month_name[d.month]) for d in periods if d.year == fallback_year
            ]

        breakdown = {}
        for tour in tours:
            tname = str(tour.tour_type)
            if tname not in breakdown:
                breakdown[tname] = {'tours': 0, 'pax': 0, 'tips': 0, 'payin': 0, 'profit': 0}
            b = breakdown[tname]
            b['tours'] += 1
            b['pax'] += tour.pax_count
            b['tips'] += tour.get_total_tips()
            b['payin'] += tour.get_settlement_contribution()
            b['profit'] += tour.calculate_profit()

        totals = _tour_summary(tours)

        context.update({
            'current_year': year,
            'current_month': month,
            'current_month_name': month_name[month],
            'available_years': available_years,
            'available_months': available_months,
            'breakdown': breakdown,
            **totals,
        })
        return context


class MonthlyCashReportView(LoginRequiredMixin, ListView):
    model = Tour
    template_name = 'tours/monthly_cash_report.html'
    context_object_name = 'tours'

    def _get_year_month(self):
        today = datetime.now()
        try:
            year = int(self.request.GET.get('year', today.year))
            month = int(self.request.GET.get('month', today.month))
        except ValueError:
            year, month = today.year, today.month
        return year, month

    def get_queryset(self):
        year, month = self._get_year_month()
        return (
            Tour.objects
            .filter(tour_date__year=year, tour_date__month=month)
            .order_by('tour_date')
            .select_related('tour_type')
            .prefetch_related('tips__currency')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self._get_year_month()
        tours = list(self.get_queryset())

        # --- cash box: sum tips by currency (non-cashless, non-CZK) ---
        box_by_currency = defaultdict(lambda: {'amount': 0, 'czk_value': 0})
        czk_tips_total = 0
        cashless_czk_total = 0
        food_expenses_total = 0

        for tour in tours:
            for tip in tour.tips.all():
                currency = tip.currency
                if currency.is_cashless:
                    cashless_czk_total += tip.amount_in_czk()
                elif currency.code == 'CZK':
                    czk_tips_total += tip.amount
                else:
                    box_by_currency[currency.code]['amount'] += tip.amount
                    box_by_currency[currency.code]['czk_value'] += tip.amount_in_czk()

            if tour.tour_type.is_food_tour:
                food_expenses_total += tour.get_total_expenses()

        czk_in_box = czk_tips_total - food_expenses_total

        # total settlement (positive = guide pays Pulse, negative = Pulse pays guide)
        total_settlement = sum(t.get_settlement_contribution() for t in tours)

        periods = _available_periods()
        available_years = sorted(set(d.year for d in periods))
        available_months = [
            (d.month, month_name[d.month]) for d in periods if d.year == year
        ]

        context.update({
            'current_year': year,
            'current_month': month,
            'current_month_name': month_name[month],
            'available_years': available_years,
            'available_months': available_months,
            'box_by_currency': dict(box_by_currency),
            'czk_tips_total': czk_tips_total,
            'food_expenses_total': food_expenses_total,
            'czk_in_box': czk_in_box,
            'cashless_czk_total': cashless_czk_total,
            'total_settlement': total_settlement,
        })
        return context


class YearlyStatsView(LoginRequiredMixin, ListView):
    model = Tour
    template_name = 'tours/yearly_stats.html'
    context_object_name = 'yearly_stats'

    def _get_year(self):
        try:
            return int(self.request.GET.get('year', datetime.now().year))
        except ValueError:
            return datetime.now().year

    def get_queryset(self):
        return (
            Tour.objects
            .filter(tour_date__year=self._get_year())
            .order_by('tour_date')
            .select_related('tour_type')
            .prefetch_related('tips__currency')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = self._get_year()
        all_tours = list(self.get_queryset())

        monthly_data = []
        for m in range(1, 13):
            month_tours = [t for t in all_tours if t.tour_date.month == m]
            if not month_tours:
                continue
            tips = sum(t.get_total_tips() for t in month_tours)
            payin = sum(t.get_settlement_contribution() for t in month_tours)
            monthly_data.append({
                'month_num': m,
                'month': month_name[m],
                'tours': len(month_tours),
                'pax': sum(t.pax_count for t in month_tours),
                'tips': tips,
                'payin': payin,
                'profit': sum(t.calculate_profit() for t in month_tours),
            })

        periods = _available_periods()
        available_years = sorted(set(d.year for d in periods))
        totals = _tour_summary(all_tours)

        context.update({
            'current_year': year,
            'available_years': available_years,
            'monthly_data': monthly_data,
            **totals,
        })
        return context
