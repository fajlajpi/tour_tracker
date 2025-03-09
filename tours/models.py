from django.db import models
from django.utils import timezone

class TourType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
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
    
    def get_payin_rate(self):
        """Get the applicable payin rate for this tour's date."""
        today = self.tour_date
        return PayinRate.objects.filter(
            effective_from__lte=today
        ).filter(
            models.Q(effective_to__gte=today) | models.Q(effective_to__isnull=True)
        ).first()
    
    def calculate_payin(self):
        rate = self.get_payin_rate()
        if rate:
            return rate.amount_per_pax * self.pax_count
        return 0
    
    def calculate_tips_per_pax(self):
        total_tips_czk = self.get_total_tips()
        if self.pax_count > 0:
            return total_tips_czk / self.pax_count
        return 0
    
    def get_total_tips(self):
        total_tips_czk = sum(tip.amount_in_czk() for tip in self.tips.all())
        return total_tips_czk

    def calculate_profit(self):
        return self.get_total_tips() - self.calculate_payin()

    
    def __str__(self):
        return f"{self.tour_type} on {self.tour_date.strftime('%Y-%m-%d %H:%M')} ({self.pax_count} pax)"

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
        """Convert the tip amount to CZK based on the exchange rate."""
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