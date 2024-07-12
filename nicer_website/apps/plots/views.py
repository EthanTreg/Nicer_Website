"""
Main functions for backend functionality of the interactive plot page
"""
import re
import logging as log
from typing import Any

import numpy as np
from numpy import ndarray
from django.conf import settings
from django.shortcuts import render
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse

from nicer_website.apps.file_mgr.models import Item
from src.utils.spectrum_preprocessing import spectrum_plot
from src.utils.light_curve_preprocessing import light_curve_plot

# Log axis
# Info field (avg count)
# Ability to choose grouping binning

# Global variable
PLOTS: dict[str, dict[str, Any]] = {
    'spectrum': {
        'exists': False,
        'min_value': None,
        'file_type': '.jsgrp',
        'function': spectrum_plot,
    },
    'light_curve': {
        'exists': False,
        'min_value': 100,
        'file_type': '.lc.gz',
        'function': light_curve_plot,
    }
}


def plot_gti(request: HttpRequest) -> JsonResponse:
    """
    Plots multiple GTI observations for a single plot

    Parameters
    ----------
    request : HttpRequest
        Http request containing the variables GTI query (gti-search), observation ID (obs_id),
        pipeline quality (quality) and plot type (plot_type)

    Returns
    -------
    JsonResponse
        Json response containing the plot as a list of the HTML element (plotDivs)
    """
    gti: int | str
    min_value: int = int(request.POST['min_value'])
    plot_divs: str
    obs_id: str = request.POST['obs_id']
    quality: str = request.POST['quality']
    plot_type: str = request.POST['plot_type']
    dir_path: str = f'{obs_id}/jspipe/'
    gti_query: str | list[str] = request.POST['gti-search']
    gti_range: list[int]
    gti_list: list[int | range] = []
    file_names: list[str] = []
    files: QuerySet
    file_name: Item

    # Filter by quality, observation ID, and filter for files
    files = Item.objects.filter(
        name__contains=quality,
        path=dir_path,
        type=Item.item_type[1][0],
    ).order_by('name')

    # Filter by the plot type and append relative file location to data path
    dir_path = f'{settings.DATA_DIR}/{dir_path}'
    files = files.filter(name__contains=PLOTS[plot_type]['file_type'])

    # Remove characters that are not numbers or dashes, and separate by commas
    gti_query = re.sub(r'[^\d,-]', '', gti_query).split(',')

    # Convert dashes to a list of integers in the range of the two numbers
    for gti in gti_query:
        if re.search(r'\d+-\d+', gti):
            gti_range = list(map(int, gti.split('-')))
            gti_range[-1] += 1
            gti_list.extend(range(*gti_range))
        elif gti.isdigit():
            gti_list.append(int(gti))

    # Filter for each GTI
    for gti in gti_list:
        file_name = files.filter(name__regex=fr'^\w*GTI{gti}[^\d][-_.\w]*$').first()

        if file_name:
            file_names.append(dir_path + file_name.name)

    # If not GTI found, use the first available GTI
    if not file_names:
        file_name = files.first().name
        gti_list = re.search(r'GTI(\d+)', file_name).group(1)
        file_names.append(dir_path + file_name)

    # Plot each GTI
    plot_divs = PLOTS[plot_type]['function'](min_value, file_names, gti_list)
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
        Json response containing the plots as a list of HTML elements (plotDivs),
        observation ID (obsID), quality (quality), if spectrum is plotted (spectrum),
        and if light curve is plotted (lightCurve)
    """
    file_name: str
    obs_id: str = request.POST['obs_id']
    quality: str = request.POST['quality']
    dir_path: str = f'{obs_id}/jspipe/'
    max_gti: list[int] = []
    plot_divs: list[str] = []
    infos: list[dict[str, Any]] = []
    plot_type: dict[str, Any]
    info: ndarray
    indices: ndarray
    file_names: ndarray
    files: QuerySet

    # Get all files in observation ID
    files = Item.objects.filter(
        name__contains=quality,
        path=dir_path,
        type=Item.item_type[1][0],
    ).order_by('name')

    dir_path = f'{settings.DATA_DIR}/{dir_path}'

    # Try to get data for specified plots
    try:
        # Get summary files for each GTI
        file_names = np.array(
            files.filter(name__contains='BGDATA.summary').values_list('name', flat=True)
        )

        # Sort by GTI number
        indices = np.argsort(
            [int(re.search(r'GTI(\d+)', file_name).group(1)) for file_name in file_names]
        )

        # Get GTI info
        for file_name in file_names[indices]:
            file_name = dir_path + file_name
            info = np.char.replace(np.loadtxt(file_name, dtype=str, unpack=True), "'", '')
            infos.append(dict(zip(*info)) | {'GTI': re.search(r'GTI\d+', file_name).group(0)})

        # Plot depending on the data type
        for plot_type in PLOTS.values():
            if plot_type['file_type'] in request.POST.values():
                plot_type['exists'] = True
                file_names = files.filter(name__contains=plot_type['file_type'])
                file_name = file_names.first().name
                max_gti.append(len(file_names))

                plot_divs.append(plot_type['function'](
                    plot_type['min_value'],
                    [dir_path + file_name],
                    [0],
                ))

    except AttributeError as error:
        log.error(f'{error}\nNo valid data in {dir_path}')

    return JsonResponse({
        'plotDivs': plot_divs,
        'obsID': obs_id,
        'quality': quality,
        'spectrum': PLOTS['spectrum']['exists'],
        'lightCurve': PLOTS['light_curve']['exists'],
        'maxGTI': max_gti,
        'info': infos,
    })


def fetch_observations(request: HttpRequest, count: int = 5) -> JsonResponse:
    """
    Queries the data base with a provided path to return the first 5 items
    that contain the path and item name sorted by type first, then name

    Parameters
    ----------
    request : HttpRequest
        Request containing the variable 'path' which contains the path and item name
    count : int, default = 5
        Number of items to return

    Returns
    -------
    JsonResponse
        Json response containing a dictionary with 5 items matching the query
    """
    # Get the queried observation ID from the request and root path
    root: str = Item._meta.get_field('path').get_default()  # pylint: disable=protected-access
    obs_id: str = request.GET.get('obs_id')
    suggested_obs: QuerySet

    # Query the database for the first 5 observation IDs that match the query
    suggested_obs = Item.objects.filter(
        name__startswith=obs_id,
        path=root,
        type=Item.item_type[0][0],
    ).order_by('name')[:count]

    return JsonResponse({'dir_suggestions': list(suggested_obs.values_list('name', flat=True))})


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
