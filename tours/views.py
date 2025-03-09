from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncMonth
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime, date
from calendar import month_name

from .models import Tour, Tip

class TourListView(LoginRequiredMixin, ListView):
    model = Tour
    template_name = 'tours/tour_list.html'
    context_object_name = 'tours'
    ordering = ['-tour_date']
    paginate_by = 20

class TourDetailView(LoginRequiredMixin, DetailView):
    model = Tour
    template_name = 'tours/tour_detail.html'
    context_object_name = 'tour'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tour = self.get_object()
        context['tips'] = tour.tips.all()
        context['total_tips_czk'] = sum(tip.amount_in_czk() for tip in tour.tips.all())
        context['payin'] = tour.calculate_payin()
        context['profit'] = tour.calculate_profit()
        context['tips_per_pax'] = tour.calculate_tips_per_pax()
        return context

class TourCreateView(LoginRequiredMixin, CreateView):
    model = Tour
    fields = ['tour_type', 'tour_date', 'pax_count', 'notes']
    template_name = 'tours/tour_form.html'
    success_url = reverse_lazy('tour-list')

class TourUpdateView(LoginRequiredMixin, UpdateView):
    model = Tour
    fields = ['tour_type', 'tour_date', 'pax_count', 'notes']
    template_name = 'tours/tour_form.html'
    
    def get_success_url(self):
        return reverse_lazy('tour-detail', kwargs={'pk': self.object.pk})

class TipCreateView(LoginRequiredMixin, CreateView):
    model = Tip
    fields = ['amount', 'currency']
    template_name = 'tours/tip_form.html'
    
    def form_valid(self, form):
        form.instance.tour_id = self.kwargs['tour_id']
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('tour-detail', kwargs={'pk': self.kwargs['tour_id']})

class MonthlyStatsView(LoginRequiredMixin, ListView):
    model = Tour
    template_name = 'tours/monthly_stats.html'
    context_object_name = 'monthly_stats'
    
    def get_queryset(self):
        year = self.request.GET.get('year', datetime.now().year)
        month = self.request.GET.get('month', datetime.now().month)

        try:
            year = int(year)
            month = int(month)
            return Tour.objects.filter(
                tour_date__year=year,
                tour_date__month=month
            ).order_by('tour_date')
        except ValueError:
            return Tour.objects.none()  # Handle invalid input gracefully

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tours = self.get_queryset()
        year = self.request.GET.get('year', datetime.now().year)
        month = self.request.GET.get('month', datetime.now().month)
        
        total_pax = sum(tour.pax_count for tour in tours)
        total_payin = sum(tour.calculate_payin() for tour in tours)
        total_tips = sum(
            sum(tip.amount_in_czk() for tip in tour.tips.all())
            for tour in tours
        )
        
        context.update({
            'current_year': year,
            'current_month': month,
            'years': range(2020, date.today().year + 1), # Adjust range as needed
            'months': [(i, month_name[i]) for i in range(1, 13)],
            'total_tours': tours.count(),
            'total_pax': total_pax,
            'total_payin': total_payin,
            'total_tips': total_tips,
            'total_profit': total_tips - total_payin,
            'avg_tips_per_pax': total_tips / total_pax if total_pax else 0,
        })
        
        return context