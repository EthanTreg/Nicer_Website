"""
Main functions for backend functionality of the interactive plot page
"""
import re
import logging as log

from django.conf import settings
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse

from nicer_website.apps.file_mgr.models import Item
from src.utils.spectrum_preprocessing import spectrum_plot
from src.utils.light_curve_preprocessing import light_curve_plot

# 100 Counts minimum
# Adaptive binning
# Log axis
# Get feedback

plots = {
    'spectrum': {
        'exists': False,
        'file_type': '.jsgrp',
        'function': spectrum_plot,
    },
    'light_curve': {
        'exists': False,
        'file_type': '.lc.gz',
        'function': light_curve_plot,
    }
}


def fetch_obs_files(request: HttpRequest) -> JsonResponse:
    """
    Fetches files from the specified observation ID using POST request

    Parameters
    ----------
    request : HttpRequest
        POST request containing the variable 'obs_id', which corresponds to the desired observation ID

    Returns
    -------
    JsonResponse
        Json response containing a list of files for the corresponding observation ID
    """
    # Constants

    print(request.POST)

    # Get file information
    obs_id = settings.DATA_DIR + request.POST.get('obs_id')
    dir_path = f'/{obs_id}/jspipe/'

    files = Item.objects.filter(path=dir_path, type=Item.item_type[1][0]).order_by('name')

    for plot_type in plots.values():
        files.filter(name__contains=plot_type['file_type'])

    return JsonResponse({'files': list(files.values())})


def plot_gti(request: HttpRequest) -> JsonResponse:
    gti_query = request.POST['gti-search']
    obs_id = request.POST['obs_id']
    quality = request.POST['quality']
    plot_type = request.POST['plot_type']
    dir_path = f"{obs_id}/jspipe/"
    gti_list = []
    file_names = []

    gti_query = re.sub('[^\d,-]', '', gti_query).split(',')

    for gti in gti_query:
        if '-' in gti:
            gti_range = list(map(int, gti.split('-')))
            gti_range[-1] += 1
            gti_list.extend(range(*gti_range))
        else:
            gti_list.append(int(gti))

    files = Item.objects.filter(
        name__contains=quality,
        path=dir_path,
        type=Item.item_type[1][0],
    ).order_by('name')

    dir_path = f'{settings.DATA_DIR}/{dir_path}'
    files = files.filter(name__contains=plots[plot_type]['file_type'])

    for gti in gti_list:
        file_name = files.filter(name__regex=fr'^\w*GTI{gti}[^\d][-_.\w]*$').first()

        if file_name:
            file_names.append(dir_path + file_name.name)

    plot_divs = plots[plot_type]['function'](file_names, gti_list)

    return JsonResponse({'plotDivs': [plot_divs]})


def plot_data(request: HttpRequest) -> JsonResponse:
    """
    Tries to plot the specified data, matching the correct plot type

    Supports energy spectrum and light curve

    Parameters
    ----------
    request : HttpRequest
        POST request containing the variables observation ID (obs_id),
        pipeline (quality), and file types to be plotted (.jsgrp, .lc.gz)

    Returns
    -------
    JsonResponse
        Json response containing the plots as HTML elements (plot_divs), observation ID (obs_id),
        quality (quality), if spectrum is plotted (spectrum),
        and if light curve is plotted (light_curve)
    """
    # Constants
    quality = ''
    obs_id = request.POST['obs_id']
    quality = request.POST['quality']
    dir_path = f"{obs_id}/jspipe/"
    plot_divs = []
    max_gti = []

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
        for plot_type in plots.values():
            if plot_type['file_type'] in request.POST.values():
                plot_type['exists'] = True
                file_names = files.filter(name__contains=plot_type['file_type'])
                file_name = file_names.first().name
                max_gti.append(len(file_names))

                plot_divs.append(plot_type['function']([dir_path + file_name], [0]))

    except AttributeError:
        log.error(f'No valid data in {dir_path}')

    return JsonResponse({
        'plotDivs': plot_divs,
        'obsID': obs_id,
        'quality': quality,
        'spectrum': plots['spectrum']['exists'],
        'lightCurve': plots['light_curve']['exists'],
        'maxGTI': max_gti,
    })


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

    Parameters
    ----------
    request : HttpRequest
        Request for the interactive plot page

    Returns
    -------
    HttpResponse
        Interactive plot page
    """
    return render(request, 'plots/plot.html', {
        'plot_divs': None,
    })
