from django.db import models
from django.utils import timezone


class TourType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_food_tour = models.BooleanField(
        default=False,
        help_text="Food tours have a fixed income, no per-pax payin, and tracked expenses."
    )

    def __str__(self):
        return self.name


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)  # EUR, USD, CZK, etc.
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.code


class PayinRate(models.Model):
    amount_per_pax = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.amount_per_pax} CZK (from {self.effective_from})"


class Tour(models.Model):
    tour_type = models.ForeignKey(TourType, on_delete=models.CASCADE)
    tour_date = models.DateField()
    pax_count = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    # Food tour fields
    fixed_income = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Fixed salary paid by Pulse Tours (CZK). Food tours only."
    )
    expense_1_name = models.CharField(max_length=100, blank=True, help_text="Name of first expense location")
    expense_1_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    expense_2_name = models.CharField(max_length=100, blank=True, help_text="Name of second expense location")
    expense_2_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    expense_3_name = models.CharField(max_length=100, blank=True, help_text="Name of third expense location")
    expense_3_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def get_payin_rate(self):
        """Get the applicable payin rate for this tour's date."""
        today = self.tour_date
        return PayinRate.objects.filter(
            effective_from__lte=today
        ).filter(
            models.Q(effective_to__gte=today) | models.Q(effective_to__isnull=True)
        ).first()

    def calculate_payin(self):
        """For regular tours: pax × rate. Food tours have no per-pax payin."""
        if self.tour_type.is_food_tour:
            return 0
        rate = self.get_payin_rate()
        if rate:
            return rate.amount_per_pax * self.pax_count
        return 0

    def get_total_expenses(self):
        """Sum of all three expense amounts (food tours only)."""
        total = 0
        for amount in [self.expense_1_amount, self.expense_2_amount, self.expense_3_amount]:
            if amount:
                total += amount
        return total

    def calculate_tips_per_pax(self):
        total_tips_czk = self.get_total_tips()
        if self.pax_count > 0:
            return total_tips_czk / self.pax_count
        return 0

    def get_total_tips(self):
        return sum(tip.amount_in_czk() for tip in self.tips.all())

    def get_settlement_contribution(self):
        """
        Net contribution of this tour to the monthly settlement with Prague Pulse Tours.
        Positive  → guide owes Pulse Tours this amount.
        Negative  → this tour credits the guide (reduces total payin, or triggers a payout).

        Regular tour: +payin (per-pax rate × PAX)
        Food tour:    −(fixed_income + expenses)
                      The salary and reimbursable expenses offset what the guide owes.
        """
        if self.tour_type.is_food_tour:
            return -((self.fixed_income or 0) + self.get_total_expenses())
        return self.calculate_payin()

    def calculate_profit(self):
        """
        The guide's net earnings from this tour.
        Regular tour: Tips − Payin
        Food tour:    Fixed Income + Tips
                      (Expenses are 100 % reimbursed at month end — not deducted here.)
        """
        if self.tour_type.is_food_tour:
            return (self.fixed_income or 0) + self.get_total_tips()
        return self.get_total_tips() - self.calculate_payin()

    def get_warnings(self):
        """
        Return a list of human-readable warning strings for this tour.
        Checks for missing payin rate and missing exchange rates for non-CZK tips.
        Works best when tips are prefetched with select_related('currency').
        """
        warnings = []

        if not self.tour_type.is_food_tour and not self.get_payin_rate():
            warnings.append('No active payin rate covers this tour date')

        seen_missing = set()
        for tip in self.tips.all():
            code = tip.currency.code
            if code != 'CZK' and code not in seen_missing:
                has_rate = ExchangeRate.objects.filter(
                    currency=tip.currency,
                    date__lte=self.tour_date,
                ).exists()
                if not has_rate:
                    warnings.append(f'No exchange rate found for {code}')
                    seen_missing.add(code)

        return warnings

    def __str__(self):
        return f"{self.tour_type} on {self.tour_date} ({self.pax_count} pax)"


class ExchangeRate(models.Model):
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    rate_to_czk = models.DecimalField(max_digits=10, decimal_places=4)
    date = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ('currency', 'date')

    def __str__(self):
        return f"{self.currency} to CZK: {self.rate_to_czk} on {self.date}"


class Tip(models.Model):
    tour = models.ForeignKey(Tour, related_name='tips', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)

    def amount_in_czk(self):
        """Convert the tip amount to CZK based on the nearest available exchange rate."""
        if self.currency.code == 'CZK':
            return self.amount

        exchange_rate = ExchangeRate.objects.filter(
            currency=self.currency,
            date__lte=self.tour.tour_date
        ).order_by('-date').first()

        if exchange_rate:
            return self.amount * exchange_rate.rate_to_czk
        return 0  # No exchange rate found

    def __str__(self):
        return f"{self.amount} {self.currency} for {self.tour}"
