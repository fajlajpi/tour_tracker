from django.contrib import admin
from django.urls import path
from tours import views

urlpatterns = [
    path('', views.TourListView.as_view(), name='tour-list'),
    path('tour/<int:pk>/', views.TourDetailView.as_view(), name='tour-detail'),
    path('tour/new/', views.TourCreateView.as_view(), name='tour-create'),
    path('tour/<int:pk>/edit/', views.TourUpdateView.as_view(), name='tour-update'),
    path('tour/<int:pk>/delete/', views.TourDeleteView.as_view(), name='tour-delete'),
    path('tour/<int:tour_id>/add-tip/', views.TipCreateView.as_view(), name='tip-create'),
    path('tip/<int:pk>/edit/', views.TipUpdateView.as_view(), name='tip-update'),
    path('tip/<int:pk>/delete/', views.TipDeleteView.as_view(), name='tip-delete'),
    path('stats/', views.MonthlyStatsView.as_view(), name='current-stats'),
    path('stats/yearly/', views.YearlyStatsView.as_view(), name='yearly-stats'),
    path('rates/', views.ExchangeRateView.as_view(), name='exchange-rates'),
    path('rates/fetch-cnb/', views.CNBFetchView.as_view(), name='cnb-fetch'),
    path('admin/', admin.site.urls, name='admin-page'),
]
