from django.contrib import admin
from .models import TourType, Currency, PayinRate, Tour, Tip, ExchangeRate


@admin.register(TourType)
class TourTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_food_tour')
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
    fieldsets = (
        (None, {
            'fields': ('tour_type', 'tour_date', 'pax_count', 'notes')
        }),
        ('Food Tour', {
            'classes': ('collapse',),
            'fields': (
                'fixed_income',
                'expense_1_name', 'expense_1_amount',
                'expense_2_name', 'expense_2_amount',
                'expense_3_name', 'expense_3_amount',
            ),
        }),
    )

    def get_total_tips(self, obj):
        return round(sum(tip.amount_in_czk() for tip in obj.tips.all()), 2)
    get_total_tips.short_description = 'Tips (CZK)'

    def get_payin(self, obj):
        return obj.calculate_payin()
    get_payin.short_description = 'Payin (CZK)'

    def get_profit(self, obj):
        return round(obj.calculate_profit(), 2)
    get_profit.short_description = 'Profit (CZK)'


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency', 'rate_to_czk', 'date')
    list_filter = ('currency', 'date')
    date_hierarchy = 'date'
