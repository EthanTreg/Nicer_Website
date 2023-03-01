from django.urls import path
from . import views


app_name = 'plots'
urlpatterns = [
    path('interactive_plot/', views.interactive_plot, name='plots'),
    path('fetch_observations', views.fetch_observations, name='fetch_observations'),
]
