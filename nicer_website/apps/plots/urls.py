"""
URLs for the plots app to call functions in views
"""
from django.urls import path

from . import views


app_name = 'plots'  # pylint: disable=invalid-name
urlpatterns = [
    path('interactive_plot/', views.interactive_plot, name='plots'),
    path('fetch_observations', views.fetch_observations, name='fetch_observations'),
    path('plot_data', views.plot_data, name='plot_data'),
    path('plot_gti', views.plot_gti, name='plot_gti'),
]
