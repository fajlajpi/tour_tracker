from django.contrib import admin
from django.urls import path
from tours import views

urlpatterns = [
    path('', views.TourListView.as_view(), name='tour-list'),
    path('tour/<int:pk>/', views.TourDetailView.as_view(), name='tour-detail'),
    path('tour/new/', views.TourCreateView.as_view(), name='tour-create'),
    path('tour/<int:pk>/edit/', views.TourUpdateView.as_view(), name='tour-update'),
    path('tour/<int:tour_id>/add-tip/', views.TipCreateView.as_view(), name='tip-create'),
    path('stats/<int:year>/<int:month>/', views.MonthlyStatsView.as_view(), name='monthly-stats'),
    path('stats/', views.MonthlyStatsView.as_view(), name='current-stats'),
    path('admin/', admin.site.urls, name='admin-page')
]
