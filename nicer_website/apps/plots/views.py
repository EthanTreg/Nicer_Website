import logging as log

from django.conf import settings
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse

from nicer_website.apps.file_mgr.models import Item
from src.utils.spectrum_preprocessing import spectrum_plot
from src.utils.light_curve_preprocessing import light_curve_plot


def fetch_observations(request: HttpRequest, count: int = 5) -> JsonResponse:
    """
    Queries the data base with a provided path to return the first 5 items
    that contain the path and item name sorted by type first, then name

    Parameters
    ----------
    request : HttpRequest
        Http request containing the variable 'path' which contains the path and item name
    count : integer, default = 5
        Number of items to return

    Returns
    -------
    JsonResponse
        Json response containing a dictionary with 5 items matching the query
    """
    # Get the queried path from the request
    path = request.GET.get('path')
    
    # Get the parent path and item name
    parent_path = '/'.join(path.split('/')[:-1]).lstrip('/')
    path = path.split('/')[-1]

    # Query the database for the first 5 items
    items = Item.objects.filter(
        name__contains=path,
        path=parent_path + '/'
    ).order_by('type', 'name')[:count]

    return JsonResponse({'dir_suggestions': list(items.values())})


def interactive_plot(request: HttpRequest) -> HttpResponse:
    """
    Loads the interactive plot page

    If the request is a POST, tries to plot the data matching the correct plot type

    Supports energy spectrum and light curve

    Parameters
    ----------
    request : HttpRequest
        Request for the interactive plot page and if it is a POST, it contains the variable 'file_path'
    
    Returns
    -------
    HttpResponse
        Interactive plot page and if request contained POST, also return HTML plotly plot
    """
    # If method isn't POST, or plotting data failed, return None for the plot
    plot_div = ''

    # If request contains POST method, generate plot
    if request.method == 'POST':
        # Get file information
        file_path = settings.DATA_DIR + request.POST.get('file_path')
        file_dir = '/'.join(file_path.split('/')[:-1]) + '/'
        file_name = file_path.split('/')[-1]
        
        try:
            # Plot depending on the data type
            if '.jsgrp' in file_name:
                plot_div = spectrum_plot(file_name, file_path, background_dir=file_dir)
            elif '.lc.gz' in file_name:
                plot_div = light_curve_plot(file_name, file_path)
            else:
                log.error(f'File type of {file_name} not supported')
        except (FileNotFoundError, IsADirectoryError):
            log.error(f'{file_path} or corresponding background not found')

    return render(request, 'plots/plot.html', {'plot_div': plot_div})
