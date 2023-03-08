"""
Main functions for backend functionality of the interactive plot page
"""
import logging as log

from django.conf import settings
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse

from nicer_website.apps.file_mgr.models import Item
from src.utils.spectrum_preprocessing import spectrum_plot
from src.utils.light_curve_preprocessing import light_curve_plot


def fetch_obs_files(request: HttpRequest) -> JsonResponse:
    """
    Fetches files from the specified observation ID

    Parameters
    ----------
    request : HttpRequest
        Request containing the variable 'obs_id', which corresponds to the desired observation ID

    Returns
    -------
    JsonResponse
        Json response containing a list of files for the corresponding observation ID
    """
    # Constants
    supported_files = ['.jsgrp', '.lc.gz']

    # Get file information
    obs_id = settings.DATA_DIR + request.POST.get('obs_id')
    dir_path = f'/{obs_id}/jspipe/'

    files = Item.objects.filter(path=dir_path, type=Item.item_type[1][0]).order_by('name')

    for file_type in supported_files:
        files.filter(name__contains=file_type)

    return JsonResponse({'files': list(files.values())})


def fetch_observations(request: HttpRequest, count: int = 5) -> JsonResponse:
    """
    Queries the data base with a provided path to return the first 5 items
    that contain the path and item name sorted by type first, then name

    Parameters
    ----------
    request : HttpRequest
        Request containing the variable 'path' which contains the path and item name
    count : integer, default = 5
        Number of items to return

    Returns
    -------
    JsonResponse
        Json response containing a dictionary with 5 items matching the query
    """
    # Get the queried observation ID from the request and root path
    root = Item._meta.get_field('path').get_default() # pylint: disable=protected-access
    obs_id = request.GET.get('obs_id')

    # Query the database for the first 5 observation IDs that match the query
    suggested_obs = Item.objects.filter(
        name__contains=obs_id,
        path=root,
        type=Item.item_type[0][0],
    ).order_by('name')[:count]

    return JsonResponse({'dir_suggestions': list(suggested_obs.values())})


def interactive_plot(request: HttpRequest) -> HttpResponse:
    """
    Loads the interactive plot page

    If the request is a POST, tries to plot the data matching the correct plot type

    Supports energy spectrum and light curve

    Parameters
    ----------
    request : HttpRequest
        Request for the interactive plot page and if it is a POST,
        it contains the variable 'file_path'

    Returns
    -------
    HttpResponse
        Interactive plot page and if request contained POST, also returns list of plotly HTML plot
    """
    # If method isn't POST, or plotting data failed, return None for the plot
    spectrum = False
    light_curve = False
    obs_id = ''
    quality = ''
    plot_divs = []

    # If request contains POST method, generate plot
    if request.method == 'POST':
        # Constants
        obs_id = request.POST['obs_id']
        quality = request.POST['quality']
        dir_path = f"{obs_id}/jspipe/"

        # Get all files in observation ID
        files = Item.objects.filter(
            name__contains=quality,
            path=dir_path,
            type=Item.item_type[1][0],
        ).order_by('name')

        dir_path = f'{settings.DATA_DIR}/{dir_path}'

        # Try to get data for specified plots
        try:
            # Plot depending on the data type
            if '.jsgrp' in request.POST.values():
                spectrum = True

                file_name = files.filter(name__contains='.jsgrp').first().name

                plot_divs.append(spectrum_plot(
                    file_name,
                    dir_path + file_name,
                    background_dir=dir_path
                ))

            if '.lc.gz' in request.POST.values():
                light_curve = True

                file_name = files.filter(name__contains='.lc.gz').first().name

                plot_divs.append(light_curve_plot(file_name, dir_path + file_name))
        except AttributeError:
            log.error(f'No valid data in {dir_path}')

    return render(request, 'plots/plot.html', {
        'plot_divs': plot_divs,
        'obs_id': obs_id,
        'quality': quality,
        'spectrum': spectrum,
        'light_curve': light_curve,
    })
