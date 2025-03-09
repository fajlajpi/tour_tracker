from django.contrib import admin
from .models import TourType, Currency, PayinRate, Tour, Tip, ExchangeRate

@admin.register(TourType)
class TourTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

@admin.register(PayinRate)
class PayinRateAdmin(admin.ModelAdmin):
    list_display = ('amount_per_pax', 'effective_from', 'effective_to')
    date_hierarchy = 'effective_from'

class TipInline(admin.TabularInline):
    model = Tip
    extra = 1

@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ('tour_type', 'tour_date', 'pax_count', 'get_total_tips', 'get_payin', 'get_profit')
    list_filter = ('tour_type', 'tour_date')
    date_hierarchy = 'tour_date'
    search_fields = ('notes',)
    inlines = [TipInline]
    
    def get_total_tips(self, obj):
        return sum(tip.amount_in_czk() for tip in obj.tips.all())
    get_total_tips.short_description = 'Tips (CZK)'
    
    def get_payin(self, obj):
        return obj.calculate_payin()
    get_payin.short_description = 'Payin (CZK)'
    
    def get_profit(self, obj):
        return obj.calculate_profit()
    get_profit.short_description = 'Profit (CZK)'

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency', 'rate_to_czk', 'date')
    list_filter = ('currency', 'date')
    date_hierarchy = 'date'