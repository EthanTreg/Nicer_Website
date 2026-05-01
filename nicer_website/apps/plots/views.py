"""
Main functions for backend functionality of the interactive plot page
"""
import os
import re
import zipfile
import tempfile
import logging as log
from time import time
from pathlib import Path
from astropy.io import fits
from dataclasses import dataclass
from typing import Any, cast, Callable

import numpy as np
from django.conf import settings
from django.shortcuts import render
from django.db.models import QuerySet, Q
from django.http import HttpRequest, HttpResponse, JsonResponse, FileResponse

from nicer_website.apps.file_mgr.models import Item
from src.apps.plots.spectrum_preprocessing import spectrum_plot
from src.apps.plots.light_curve_preprocessing import light_curve_plot
from src.apps.plots.power_density_processing import get_pds_data_and_plot
from src.apps.plots.summed_spectrum_preprocessing import summed_spectrum_plot
from src.apps.plots.hardness_intensity_preprocessing import get_hid_data_and_plot
from src.utils.background_screening import screen_gti_files, get_screening_summary


# Log axis
# Info field (avg count)
# Ability to choose grouping binning


@dataclass
class PlotType:
    exists: bool
    min_value: int
    file_type: str
    function: Callable


@dataclass
class PlotRequest:
    """
    Dataclass for plot request parameters.

    Attributes
    ----------
    obs_search : bool
        Flag indicating if the search is by observation ID (True) or source name (False)
    obs_id : int
        Observation ID
    min_value : float
        Minimum value for adaptive binning or plotting
    source : str
        Source name
    quality : str
        Pipeline quality
    gti_query : str | list[str]
        GTI query string or list of GTIs
    combined_obs_ids : list[int] | None
        List of combined observation IDs for multi-observation plots
    plot_types : list[str] | None
        List of plot types to generate
    """
    obs_search: bool = True
    obs_id: int | None = None
    min_value: float = 0
    source: str = ''
    quality: str = ''
    gti_query: str | list[str] = ''
    combined_obs_ids: list[int] | None = None
    plot_types: list[str] = None
    apply_screening: bool = False
    screening_energy_low: float = 2.0
    screening_energy_high: float = 5.0
    screening_min_bad_channels: int = 2

    def __repr__(self) -> str:
        return (f"PlotRequest({', '.join(
            f'{key}={value}' for key, value in self.__dict__.items() if value
        )})")

    @classmethod
    def from_request(cls, request: HttpRequest) -> 'PlotRequest':
        post: dict[str, str] = request.POST.dict()
        instance: PlotRequest = cls(
            obs_search=post.pop('obs_search', 'true').lower() == 'true',
            obs_id=int(post.pop('obs_id', 0) or 0),
            source=post.pop('source', ''),
            quality=post.pop('quality', ''),
            gti_query=post.pop('gti-search', ''),
            combined_obs_ids=[
                int(obs) for obs in post.pop('combined_obs_ids', '').split(',')
            ] if 'combined_obs_ids' in post else None,
            apply_screening=post.pop('apply_screening', 'false').lower() == 'true',
            screening_energy_low=float(post.pop('screening_energy_low', 2.0)),
            screening_energy_high=float(post.pop('screening_energy_high', 5.0)),
            screening_min_bad_channels=int(post.pop('screening_min_bad_channels', 2)),
            plot_types=[],
        )
        for key in post:
            key = key.replace('-', '_')

            if key == 'csrfmiddlewaretoken':
                continue
            if key == 'plot_type':
                instance.plot_types.append(post[key].replace('-', '_'))
            if key not in PLOTS:
                LOGGER.error(f'Invalid plot type in HTTP request: {key}')
                continue
            instance.plot_types.append(key)
        return instance


PLOTS: dict[str, PlotType] = {
    'spectrum': PlotType(False, 0, 'jsgrp', spectrum_plot),
    'light_curve': PlotType(False, 100, 'lc.gz', light_curve_plot),
    'summed_spectrum': PlotType(False, 0, 'jsgrp', summed_spectrum_plot),
    'power_density_spectrum': PlotType(False, 10, 'pds', get_pds_data_and_plot),
    'hardness_intensity_diagram': PlotType(False, 25, 'lc.gz', get_hid_data_and_plot),
}
LOGGER: log.Logger = log.getLogger(__name__)


def process_obs_id_search(plot_req: PlotRequest) -> JsonResponse | None:
    """
    Processes the observation ID search from either a provided observation ID or source name.
    If multiple observations are found for a source, returns a JSON response with the options.
    If no observation IDs are found, returns a JSON response with an error message.

    Parameters
    ----------
    plot_req : PlotRequest
        Plot request containing either an observation ID or source name and a flag indicating if the
        search is by observation ID or source name

    Returns
    -------
    JsonResponse | None
        JsonResponse with multiple observation options or error message, or None if a single
        observation ID is successfully found
    """
    obs_ids: list[dict[str, int | str | None]] = []

    if plot_req.obs_search and plot_req.obs_id:
        return None
    if not plot_req.obs_search and plot_req.source:
        obs_items = Item.objects.filter(
            source=plot_req.source,
            type=Item.dir,
        ).distinct('path', 'source')

        for item in obs_items:
            obs_ids.append({'obs_id': item.obs_id, 'source': item.source})

        if len(obs_ids) > 1:
            return JsonResponse({
                'multiple_observations': True,
                'obs_ids': obs_ids,
                'source': plot_req.source,
            })

        plot_req.obs_id = cast(int | None, obs_ids[0]['obs_id'])

    if not plot_req.obs_id:
        return JsonResponse({
            'error': f'No observable data found for {
                f'observation ID: {plot_req.obs_id}' if plot_req.obs_search else
                f'source: {plot_req.source}'
            }'
        })
    return None


def process_plots(
        files: QuerySet[Item],
        plot_req: PlotRequest,
        labels: list[str] | None = None):
    ti: float
    plot_type: str
    max_gti: list[int] = []
    plot_divs: list[str] = []
    default_binnings: dict[str, int] = {}
    screening_summaries: dict = {}
    plot_files: QuerySet[Item]
    plot: PlotType

    if not plot_req.plot_types:
        return [], [], {}, {}

    for plot_type, plot in PLOTS.items():
        if not plot_type in plot_req.plot_types:
            continue

        LOGGER.info(f'Processing plot type: {plot_type}')
        plot.exists = True
        plot_files = files.filter(
            file_type=plot.file_type,
        ).exclude(name__regex=r'_BAND\d+')

        if plot_files.exists():
            ti = time()
            plot_files = plot_files.order_by('gti')
            max_gti.append(files.last().gti)
            
            final_file_paths = [os.path.join(
                settings.DATA_DIR,
                str(file.obs_id),
                'jspipe',
                file.name,
            ) for file in plot_files]
            final_gti_numbers = list(plot_files.values_list('gti', flat=True))
            
            # calculate default binning
            calculated_default = calculate_default_binning(final_file_paths[0], plot_type)
            default_binnings[plot_type] = calculated_default
            default_binnings[plot_type.replace('_', '-')] = calculated_default
            if plot_type == 'hardness_intensity_diagram':
                default_binnings['time'] = calculated_default
                
            use_min_value = plot_req.min_value if plot_req.min_value else calculated_default

            bg_dash = 'solid'
            if plot_req.apply_screening and plot_type in ['spectrum', 'summed_spectrum']:
                passed_files, passed_gtis, results = screen_gti_files(
                    final_file_paths,
                    final_gti_numbers,
                    energy_low=plot_req.screening_energy_low,
                    energy_high=plot_req.screening_energy_high,
                    min_bad_channels=plot_req.screening_min_bad_channels
                )
                summary = get_screening_summary(results)
                screening_summaries[plot_type.replace('_', '-')] = summary
                
                if passed_files:
                    final_file_paths = passed_files
                    final_gti_numbers = passed_gtis
                else:
                    bg_dash = 'dash'
                    summary['all_failed'] = True

            kwargs = {}
            if plot_type in ['spectrum', 'summed_spectrum']:
                kwargs['bg_dash'] = bg_dash

            plot_div = plot.function(
                use_min_value,
                ' '.join(map(str, plot_req.combined_obs_ids)) if plot_req.combined_obs_ids else
                plot_req.obs_id,
                final_file_paths,
                final_gti_numbers,
                gti_labels=labels,
                **kwargs
            )
            LOGGER.info(f'{plot_type} function completed in {time() - ti:.3f}s')
            plot_divs.append(plot_div)
        else:
            LOGGER.warning(f'No files found for plot type: {plot_type}')
    return max_gti, plot_divs, default_binnings, screening_summaries


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


def parse_num_query(num_query: str) -> list[int]:
    """
    Parses a number query string into a list of numbers.

    Parameters
    ----------
    num_query : str
        Number query string containing individual numbers and/or ranges (e.g. "1,3-5,7")

    Returns
    -------
    list[int]
        List of numbers extracted from the query
    """
    end: int
    start: int
    nums: list[int] = []
    parts: list[str] = re.sub(r'[^\d,-]', '', num_query).split(',')

    for part in parts:
        if re.match(r'^\d+-\d+$', part):
            start, end = map(int, part.split('-'))
            nums.extend(range(start, end + 1))
        elif part.isdigit():
            nums.append(int(part))
    return sorted(set(nums))


def calculate_default_binning(file_path, plot_type):
    """
    Calculate default binning to reduce number of plotted points for faster rendering.
    Target: ~500-1000 points per plot for optimal performance.

    Parameters
    ----------
    file_path : str
        Path to the data file
    plot_type : str
        Type of plot (spectrum, light_curve, etc.)

    Returns
    -------
    int
        Calculated default binning value
    """
    if plot_type in ['spectrum', 'summed_spectrum']:
        # For spectrum: reduce number of energy bins
        with fits.open(file_path) as hdul:
            if 'SPECTRUM' in hdul:
                counts = hdul['SPECTRUM'].data['COUNTS']
                total_bins = len(counts)
                max_counts = np.max(counts)

                # set for fast rendering
                target_points = 500

                # Calculate binning factor
                bin_factor = max(1, total_bins // target_points)

                # 1% of max as minimum
                min_counts = max(1, int(max_counts * 0.01))

                default_bin = max(bin_factor, min_counts)
                return default_bin

    elif plot_type == 'light_curve':
        #  have < 100 bins per GTI
        # ensure minimum counts per bin
        with fits.open(file_path) as hdul:
            if 'RATE' in hdul:
                rate = hdul['RATE'].data['RATE']
                total_bins = len(rate)
                mean_rate = np.mean(rate)

                # Target 100 final bins per GTI
                target_bins = 100
                bins_to_combine = max(1, total_bins // target_bins)

                # at least 100 counts per bin
                if mean_rate > 0:
                    min_bins_for_100_counts = max(1, int(100 / mean_rate))
                else:
                    min_bins_for_100_counts = 1

                # Use one that combines more bins
                default_bin = max(bins_to_combine, min_bins_for_100_counts)

                final_points = total_bins / default_bin
                final_counts_per_bin = mean_rate * default_bin
                return default_bin

    elif plot_type == 'power_density_spectrum':
        # For PDS: the min_value controls significance-based binning (higher number means more agressive binning)
        default_significance = 15
        return default_significance

    elif plot_type == 'hardness_intensity_diagram':
        # Return fixed default of 1 (no binning)
        return 1

    # Fallback to predefined defaults
    fallback = PLOTS.get(plot_type, {}).get('min_value', 1)
    return fallback


def plot_gti(request: HttpRequest) -> JsonResponse:
    """
    Plots multiple GTI observations for a single plot

    Parameters
    ----------
    request : HttpRequest
        Http request containing either:
        - Single observation: GTI query (gti-search), observation ID (obs_id)
        - Multiple observations: comma-separated observation IDs (combined_obs_ids)
        Also includes pipeline quality (quality) and plot type (plot_type)

    Returns
    -------
    JsonResponse
        Json response containing the plot as a list of the HTML element (plotDivs)
    """
    ti: float
    data_dir: str
    gti_nums: list[int]
    file_paths: list[str]
    labels: list[str] | None = None
    plot_req: PlotRequest = PlotRequest.from_request(request)
    plot: PlotType = PLOTS[cast(list[str], plot_req.plot_types)[0]]

    # Parse screening parameters with explicit logging
    apply_screening_str = request.POST.get('apply_screening', 'false')
    apply_screening = apply_screening_str.lower() == 'true'

    if not plot_req.min_value:
        plot_req.min_value = plot.min_value

    if apply_screening:
        try:
            screening_energy_low = float(request.POST.get('screening_energy_low', 2.0))
            screening_energy_high = float(request.POST.get('screening_energy_high', 5.0))
            screening_min_bad_channels = int(request.POST.get('screening_min_bad_channels', 2))
        except (ValueError, TypeError) as e:
            screening_energy_low = 2.0
            screening_energy_high = 5.0
            screening_min_bad_channels = 2
    else:
        screening_energy_low = 2.0
        screening_energy_high = 5.0
        screening_min_bad_channels = 2

    LOGGER.info(f'Received POST data: {plot_req}')

    if not plot_req.obs_id and not plot_req.combined_obs_ids:
        LOGGER.error("obs_id is missing from POST data.")
        return JsonResponse({'error': 'obs_id is required.'}, status=400)

    gti_nums = parse_num_query(plot_req.gti_query)
    files = Item.objects.filter(
        quality=plot_req.quality,
        file_type=plot.file_type,
        **{'obs_id__in': plot_req.combined_obs_ids} if plot_req.combined_obs_ids else
        {'obs_id': plot_req.obs_id},
        **{'gti__in': gti_nums} if gti_nums else {},
    )

    if not files.exists():
        return JsonResponse({
            'error': f"No GTI data found for observation ID: {plot_req.obs_id} with GTI query: "
                     f"'{plot_req.gti_query}'"
        })

    if plot_req.combined_obs_ids:
        labels = [f'GTI{file.gti} (Obs {file.obs_id})' for file in files]

    max_gti, plot_divs, default_binnings, screening_summaries = process_plots(files, plot_req, labels=labels)
    return JsonResponse({'plotDivs': plot_divs, 'screeningSummary': screening_summaries.get(plot_req.plot_types[0].replace('_', '-')) if screening_summaries else None})



def plot_data(request: HttpRequest) -> JsonResponse:
    """
    Tries to plot the specified data, matching the correct plot type.

    Supports energy spectrum, light curve, and power density.

    Parameters
    ----------
    request : HttpRequest
        POST request containing the variables observation ID (obs_id) or source name (source),
        pipeline (quality), and file types to be plotted (.jsgrp, .lc.gz)

    Returns
    -------
    JsonResponse
        Json response containing the plots as a list of HTML elements (plotDivs),
        observation ID (obsID), quality (quality), if spectrum is plotted (spectrum),
        and if light curve is plotted (lightCurve)
    """
    data_dir: str
    file_name: str
    plot_type: str
    infos: list[dict[str, Any]] = []
    obs_info: dict[str, int | float | str | None]
    result: JsonResponse | None
    files: QuerySet[Item]
    obs_items: QuerySet[Item]
    item: Item
    plot_info: PlotType
    plot_req: PlotRequest = PlotRequest.from_request(request)

    if result := process_obs_id_search(plot_req):
        return result

    files = Item.objects.filter(
        obs_id=plot_req.obs_id,
        quality=plot_req.quality,
        type=Item.file,
    )
    LOGGER.info(f'Found {files.count()} files for obs_id {plot_req.obs_id}')

    if not files.exists():

        return JsonResponse({
            'error': f"No observable data found for {
                f'observation ID: {plot_req.obs_id}' if plot_req.obs_search else
                f'source: {plot_req.source}'
            }"
        })

    item = cast(Item, files.first())
    plot_req.source = plot_req.source or item.source

    obs_info = {
        'ra': item.ra,
        'dec': item.dec,
        'tstart_tt': item.tstart_tt,
        'tstop_tt': item.tstop_tt,
        'obs_id': plot_req.obs_id,
        'source': plot_req.source,
        'ndets_used': item.ndets_used,
        'ushoot_net_rate': item.ushoot_net_rate,
        'oshoot_net_rate': item.oshoot_net_rate,
        'goodx_0p5_12_rate': item.goodx_0p5_12_rate,
    }
    data_dir = os.path.join(settings.DATA_DIR, str(plot_req.obs_id), 'jspipe')

    for file in files.filter(
        file_type='summary',
        gti__isnull=False,
    ).distinct('gti').order_by('gti'):
        infos.append(dict(zip(*np.char.replace(np.loadtxt(
            os.path.join(data_dir, file.name),
            dtype=str,
            unpack=True,
        ), "'", ''))) | {'GTI': f'GTI{file.gti}'})

        if not plot_req.source and 'OBJECT' in infos[-1]:
            plot_req.source = infos[-1]['OBJECT']

    max_gti, plot_divs, default_binnings, screening_summaries = process_plots(files, plot_req)


    if not infos and not plot_divs:
        return JsonResponse({
            'error': f'No plottable data found for observation ID {plot_req.obs_id} '
                     f'with quality {plot_req.quality}',
        })
    return JsonResponse({
        'plotDivs': plot_divs,
        'obsID': plot_req.obs_id,
        'quality': plot_req.quality,
        'spectrum': PLOTS['spectrum'].exists,
        'summedSpectrum': PLOTS['summed_spectrum'].exists,
        'lightCurve': PLOTS['light_curve'].exists,
        'powerSpectrum': PLOTS['power_density_spectrum'].exists,
        'hardnessIntensity': PLOTS['hardness_intensity_diagram'].exists,
        'maxGTI': max_gti,
        'info': infos,
        'source': plot_req.source,
        'obs_info': obs_info,
        'defaultBinnings': default_binnings,
        'screeningSummaries': screening_summaries,

    })


def fetch_observations(request: HttpRequest, count: int = 5) -> JsonResponse:
    """
    Queries the database with a provided path to return the first 5 items
    that contain the path and item name sorted by type first, then name.

    Parameters
    ----------
    request : HttpRequest
        Request containing the variable 'obs_id' or 'source' for search
    count : int, default = 5
        Number of items to return

    Returns
    -------
    JsonResponse
        JSON response containing a dictionary with matching items
    """
    obs_id: str = request.GET.get('obs_id', '')
    source: str = request.GET.get('source', '')
    suggested_obs: list[str]

    # Query the database for the first 5 observation IDs or source names that match the query
    if obs_id:
        suggested_obs = list(Item.objects.filter(
            name__startswith=obs_id,
            path=Item.root,
            type=Item.dir,
        ).order_by('name')[:count].values_list('name', flat=True))
    elif source:
        suggested_obs = list(Item.objects.filter(
            source__istartswith=source,
            type=Item.dir,
        ).distinct().order_by('source')[:count].values_list('source', flat=True))
    else:
        return JsonResponse({
            'suggestions': [],
            'error': 'No observation ID or source name provided',
        })

    # Check if any results were found and return them
    if len(suggested_obs):
        return JsonResponse({'suggestions': suggested_obs})
    return JsonResponse({'suggestions': [], 'error': 'Observational data not found'})


def fetch_sources(request: HttpRequest, count: int = 5) -> JsonResponse:
    """
    Queries the data base for source names that contain the provided string
    """
    source_query = request.GET.get('source')
    suggested_sources = Item.objects.filter(
        source__icontains=source_query
    ).values('source').distinct().order_by('source')[:count]
    return JsonResponse({'source_suggestions': list(suggested_sources)})


def create_gti_archive(obs_id, gti_list, base_path):
    """Create a zip archive of GTI files"""
    LOGGER.info(f"Creating GTI archive for OBS_ID {obs_id}, GTIs: {gti_list}")
    jspipe_dir = base_path / obs_id / 'jspipe'

    if not jspipe_dir.exists():
        return HttpResponse(f'Directory not found: {jspipe_dir}', status=404)

    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, 'w') as archive:
            files_added = False

            if not gti_list:
                for file in jspipe_dir.glob(f'js_ni{obs_id}*_GTI*'):
                    LOGGER.info(f"Adding file to archive: {file}")
                    archive.write(str(file), file.name)
                    files_added = True
            else:
                for gti_num in gti_list:
                    for file in jspipe_dir.glob(f'js_ni{obs_id}*_GTI{gti_num}'):
                        if f'_GTI{gti_num}' in str(file):
                            LOGGER.info(f"Adding file to archive: {file}")
                            archive.write(str(file), file.name)
                            files_added = True

            if not files_added:
                return HttpResponse('No GTI files found', status=404)

        return FileResponse(
            open(tmp.name, 'rb'),
            as_attachment=True,
            filename=f'{obs_id}_GTI_{"-".join(gti_list) if gti_list else "all"}.zip'
        )


def download_data(request: HttpRequest):
    """Handle data downloads for observations and GTIs"""
    data_type = request.GET.get('type')
    obs_id = request.GET.get('obs_id')
    gti_numbers_str = request.GET.get('gti_numbers')
    quality = request.GET.get('quality')
    LOGGER.info(f"Download request - Type: {data_type}, OBS_ID: {obs_id}, GTI: {gti_numbers_str}, Quality: {quality}")

    if not obs_id:
        return HttpResponse('OBS_ID is required', status=400)

    if not quality:
        return HttpResponse('Quality is required', status=400)

    quality = quality.lower()

    try:
        base_path = Path(settings.DATA_DIR)
        jspipe_dir = base_path / obs_id / 'jspipe'

        if not jspipe_dir.exists():
            return HttpResponse(f'Directory not found: {jspipe_dir}', status=404)

        if data_type == 'gti':
            if gti_numbers_str:
                gti_numbers = gti_numbers_str.split(',')

                if len(gti_numbers) == 1:
                    gti_num = gti_numbers[0]
                    gti_files = list(jspipe_dir.glob(f'js_ni{obs_id}*_{quality}_GTI{gti_num}*'))

                    if not gti_files:
                        return HttpResponse(f'No files found for GTI{gti_num} with quality {quality}', status=404)

                    if len(gti_files) == 1:
                        return FileResponse(
                            open(str(gti_files[0]), 'rb'),
                            as_attachment=True,
                            filename=gti_files[0].name
                        )

                    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                        with zipfile.ZipFile(tmp.name, 'w') as archive:
                            for file in gti_files:
                                archive.write(str(file), file.name)

                        return FileResponse(
                            open(tmp.name, 'rb'),
                            as_attachment=True,
                            filename=f'{obs_id}_GTI{gti_num}_{quality}.zip'
                        )

                else:
                    # multiple GTIs as a zip
                    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                        with zipfile.ZipFile(tmp.name, 'w') as archive:
                            files_added = False
                            for gti_num in gti_numbers:
                                gti_files = list(jspipe_dir.glob(f'js_ni{obs_id}*_{quality}_GTI{gti_num}*'))
                                if gti_files:
                                    for file in gti_files:
                                        archive.write(str(file), file.name)
                                        files_added = True
                                else:
                                    LOGGER.warning(f"No files found for GTI{gti_num} with quality {quality}")

                            if not files_added:
                                return HttpResponse('No GTI files found for the selected GTIs', status=404)
                        return FileResponse(
                            open(tmp.name, 'rb'),
                            as_attachment=True,
                            filename=f'{obs_id}_GTI_{"-".join(gti_numbers)}_{quality}.zip'
                        )
            else:
                gti_files = list(jspipe_dir.glob(f'js_ni{obs_id}*_{quality}_GTI*'))
                if not gti_files:
                    return HttpResponse(f'No GTI files found for the observation with quality {quality}', status=404)
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                    with zipfile.ZipFile(tmp.name, 'w') as archive:
                        for file in gti_files:
                            archive.write(str(file), file.name)
                    return FileResponse(
                        open(tmp.name, 'rb'),
                        as_attachment=True,
                        filename=f'{obs_id}_all_GTI_{quality}.zip'
                    )
        elif data_type == 'obs':
            return create_obs_archive(obs_id, base_path)
        else:
            return HttpResponse('Invalid data type', status=400)

    except Exception as e:
        LOGGER.exception("Error in download_data")
        return HttpResponse(f'Error: {str(e)}', status=500)


def create_obs_archive(obs_id, base_path):
    """Create a zip archive of an entire observation"""
    obs_path = base_path / obs_id
    if not obs_path.exists():
        return HttpResponse('Observation not found', status=404)

    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, 'w') as archive:
            for root, _, files in os.walk(str(obs_path)):
                for file in files:
                    file_path = os.path.join(root, file)
                    archive_path = os.path.relpath(file_path, str(obs_path))
                    archive.write(file_path, archive_path)

        return FileResponse(
            open(tmp.name, 'rb'),
            as_attachment=True,
            filename=f'{obs_id}_full.zip'
        )
