from django.urls import path

from . import views


app_name = 'plots'
urlpatterns = [
    path('interactive_plot/', views.interactive_plot, name='plots'),
    path('fetch_observations', views.fetch_observations, name='fetch_observations'),
    path('fetch_observation_files', views.fetch_obs_files, name='obs_files'),
    path('plot_data', views.plot_data, name='plot_data'),
    path('plot_gti', views.plot_gti, name='plot_gti'),
]
