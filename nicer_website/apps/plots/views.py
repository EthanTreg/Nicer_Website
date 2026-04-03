"""
Main functions for backend functionality of the interactive plot page
"""
import os
import re
import time
import logging as log
from typing import Any
from pathlib import Path
import tempfile
import zipfile


import numpy as np
from django.conf import settings
from django.shortcuts import render
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse, FileResponse


from nicer_website.apps.file_mgr.models import Item
from src.utils.spectrum_preprocessing import spectrum_plot
from src.utils.light_curve_preprocessing import light_curve_plot
from src.utils.power_density_processing import get_pds_data_and_plot
from src.utils.hardness_intensity_preprocessing import get_hid_data_and_plot
from src.utils.summed_spectrum_preprocessing import summed_spectrum_plot
from src.utils.background_screening import screen_gti_files, get_screening_summary


import logging
logger: logging.Logger = logging.getLogger(__name__)






# Log axis
# Info field (avg count)
# Ability to choose grouping binning


# Global variable
PLOTS: dict[str, dict[str, Any]] = {
   'spectrum': {
       'exists': False,
       'min_value': None,  # Default min_value for spectrum
       'file_type': '.jsgrp',
       'function': spectrum_plot,
   },
   'summed_spectrum': {
       'exists': False,
       'min_value': None,  # Default min_value for summed spectrum
       'file_type': '.jsgrp',
       'function': summed_spectrum_plot,
   },
   'light_curve': {
       'exists': False,
       'min_value': 100, # Default min_value for light_curve
       'file_type': '.lc.gz',
       'function': light_curve_plot,
   },
   'power_density_spectrum': {
       'exists': False,
       'min_value': 10,  # Default min_value for PDS adaptive binning (significance-based)
       'file_type': '-bin.pds',
       'function': get_pds_data_and_plot,
   },
   'hardness_intensity_diagram': {
       'exists': False,
       'min_value': 1,  # Default min_value for HID adaptive binning
       'file_type': '.lc.gz',
       'function': get_hid_data_and_plot,
   },
}




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
    try:
        from astropy.io import fits
        
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
                    
                    logger.info(f"[calculate_default_binning] Spectrum: total_bins={total_bins}, "
                              f"max_counts={max_counts}, target_points={target_points}, "
                              f"bin_factor={bin_factor}, min_counts={min_counts}, "
                              f"final_default_bin={default_bin}")
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
                    
                    logger.info(f"[calculate_default_binning] Light curve: total_bins={total_bins}, "
                              f"mean_rate={mean_rate:.2f}, target_bins={target_bins}, "
                              f"bins_to_combine={bins_to_combine}, "
                              f"min_bins_for_100_counts={min_bins_for_100_counts}, "
                              f"final_default_bin={default_bin}, "
                              f"final_points={final_points:.0f}, "
                              f"final_counts_per_bin={final_counts_per_bin:.1f}")
                    return default_bin
                    
        elif plot_type == 'power_density_spectrum':
            # For PDS: the min_value controls significance-based binning (higher number means more agressive binning)
            default_significance = 15 
            logger.info(f"[calculate_default_binning] PDS: using significance threshold={default_significance} "
                       f"(higher = fewer bins = faster rendering)")
            return default_significance
            
        elif plot_type == 'hardness_intensity_diagram':
            # Return fixed default of 1 (no binning)
            return 1
            
    except Exception as e:
        logger.warning(f"[calculate_default_binning] Error calculating default binning for {plot_type}: {e}")
    
    # Fallback to predefined defaults
    fallback = PLOTS.get(plot_type, {}).get('min_value', 1)
    logger.info(f"[calculate_default_binning] Using fallback for {plot_type}: {fallback}")
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
   logger.info(f"[plot_gti START] ===== BACKEND ENTRY =====")
   logger.info(f"[plot_gti START] Request method: {request.method}")
   logger.info(f"[plot_gti START] Request path: {request.path}")
   logger.info(f"[plot_gti START] All POST data: {dict(request.POST)}")
   logger.info(f"[plot_gti START] Request headers: {dict(request.headers)}")
   
   obs_id: str = request.POST.get('obs_id', '')
   quality: str = request.POST.get('quality', '')
   plot_type_str: str = request.POST.get('plot_type', '')
   gti_query_str: str = request.POST.get('gti-search', '')
   requested_min_value_str = request.POST.get('min_value')
   
   # Parse screening parameters with explicit logging
   apply_screening_str = request.POST.get('apply_screening', 'false')
   apply_screening = apply_screening_str.lower() == 'true'
   
   logger.info(f"[plot_gti] Screening parameter raw value: '{apply_screening_str}'")
   logger.info(f"[plot_gti] Screening enabled: {apply_screening}")
   
   if apply_screening:
       try:
           screening_energy_low = float(request.POST.get('screening_energy_low', 2.0))
           screening_energy_high = float(request.POST.get('screening_energy_high', 5.0))
           screening_min_bad_channels = int(request.POST.get('screening_min_bad_channels', 2))
           logger.info(f"[plot_gti] Screening params: energy={screening_energy_low}-{screening_energy_high} keV, min_bad={screening_min_bad_channels}")
       except (ValueError, TypeError) as e:
           logger.warning(f"[plot_gti] Error parsing screening params: {e}, using defaults")
           screening_energy_low = 2.0
           screening_energy_high = 5.0
           screening_min_bad_channels = 2
   else:
       screening_energy_low = 2.0
       screening_energy_high = 5.0
       screening_min_bad_channels = 2

   logger.info(f"[plot_gti] Raw received values:")
   logger.info(f"[plot_gti]   - obs_id: '{obs_id}'")
   logger.info(f"[plot_gti]   - quality: '{quality}'")
   logger.info(f"[plot_gti]   - plot_type: '{plot_type_str}'")
   logger.info(f"[plot_gti]   - gti-search: '{gti_query_str}'")
   logger.info(f"[plot_gti]   - min_value: '{requested_min_value_str}'")
   logger.info(f"[plot_gti]   - apply_screening: {apply_screening}")

   # Check if this is a combined observations request
   is_combined_request = 'combined_obs_ids' in request.POST
   logger.info(f"[plot_gti] Is combined request: {is_combined_request}")

   if not obs_id and not is_combined_request:
       logger.error("[plot_gti] obs_id is missing from POST data.")
       return JsonResponse({'error': 'obs_id is required.'}, status=400)
   if not plot_type_str:
       logger.error("[plot_gti] plot_type is missing from POST data.")
       return JsonResponse({'error': 'plot_type is required.'}, status=400)

   # Enhanced plot type mapping - handle both underscore and hyphen formats
   plot_type_mapping = {
       'time': 'hardness_intensity_diagram',
       'hardness-intensity-diagram': 'hardness_intensity_diagram',
       'hardness_intensity_diagram': 'hardness_intensity_diagram',
       'power-density-spectrum': 'power_density_spectrum',
       'power_density_spectrum': 'power_density_spectrum',
       'light-curve': 'light_curve',
       'light_curve': 'light_curve',
       'summed-spectrum': 'summed_spectrum',
       'summed_spectrum': 'summed_spectrum',
       'spectrum': 'spectrum',
   }
   
   original_plot_type = plot_type_str
   logger.info(f"[plot_gti] Original plot_type_str: '{original_plot_type}'")
   logger.info(f"[plot_gti] Available mappings: {list(plot_type_mapping.keys())}")
   
   # Try direct mapping first
   plot_type = plot_type_mapping.get(plot_type_str)
   logger.info(f"[plot_gti] Direct mapping result: '{plot_type}'")
   
   # If no direct mapping found, try with underscores converted to hyphens
   if not plot_type:
       plot_type_key = plot_type_str.replace('-', '_')
       plot_type = plot_type_mapping.get(plot_type_key, plot_type_key)
       logger.info(f"[plot_gti] Fallback mapping with key '{plot_type_key}': '{plot_type}'")
   
   logger.info(f"[plot_gti] Final mapped plot_type: '{plot_type}'")
   logger.info(f"[plot_gti] Available PLOTS keys: {list(PLOTS.keys())}")
   
   if plot_type not in PLOTS:
       logger.error(f"[plot_gti] Invalid plot_type: '{original_plot_type}'")
       return JsonResponse({'error': f'Invalid plot type: {plot_type_str}'}, status=400)

   logger.info(f"[plot_gti] Plot type validation passed. Proceeding with '{plot_type}'")

   default_min_value = PLOTS[plot_type].get('min_value')
   min_value: int | None

   if requested_min_value_str is not None and requested_min_value_str != '':
       try:
           min_value = int(requested_min_value_str)
       except ValueError:
           min_value = default_min_value
   else:
       min_value = default_min_value

   logger.info(f"[plot_gti] Final min_value for plotting: {min_value}")


   # Handle combined observations case - Assuming this part is okay for now based on logs
   if 'combined_obs_ids' in request.POST:
       logger.info("[plot_gti] Handling combined observations.")
       # For brevity, assuming this path is less critical for the current bug
       # but should be reviewed for logging consistency if issues arise there.
       obs_ids_str = request.POST.get('combined_obs_ids')
       obs_ids = obs_ids_str.split(',')
       all_file_names = []
       all_gti_list = []
       gti_obs_mapping = []


       for current_obs_id_combined in obs_ids:
           current_dir_path_combined = os.path.join(current_obs_id_combined, 'jspipe/')
           # Ensure 'quality' and 'plot_type' are used correctly here
           files_combined_qs = Item.objects.filter(
               name__contains=quality, # Make sure quality is available and correct
               path=current_dir_path_combined,
               type=Item.item_type[1][0],
           ).filter(name__contains=PLOTS[plot_type]['file_type']).order_by('name')


           for file_item_combined in files_combined_qs:
               if match := re.search(r'GTI(\d+)', file_item_combined.name):
                   gti_num_combined = int(match.group(1))
                   full_path_combined = os.path.join(settings.DATA_DIR, current_dir_path_combined, file_item_combined.name)
                   all_file_names.append(full_path_combined)
                   all_gti_list.append(gti_num_combined)
                   gti_obs_mapping.append(current_obs_id_combined)


       if not all_file_names:
           logger.error("[plot_gti] Combined: No GTI files found.")
           return JsonResponse({'error': 'No GTI files found for the specified combined observations'})


       gti_labels = [f'GTI{gti_num} (Obs {obs_id_map})' for gti_num, obs_id_map in zip(all_gti_list, gti_obs_mapping)]
       plot_kwargs = {
           'min_value': min_value,
           'obs_id': obs_id, # This might need to be a list or handled differently by the plotting function
           'data_paths': all_file_names,
           'gti_numbers': all_gti_list,
           'gti_labels': gti_labels,
       }
       if 'is_combined_obs' in PLOTS[plot_type].get('optional_params', []):
           plot_kwargs['is_combined_obs'] = True


       try:
           plot_divs = PLOTS[plot_type]['function'](**plot_kwargs)
           logger.info(f"[plot_gti] Combined: Successfully generated plot divs.")
           return JsonResponse({'plotDivs': [plot_divs]})
       except Exception as e:
           logger.exception(f"[plot_gti] Combined: Error during plot generation: {e}")
           return JsonResponse({'error': f'Error generating combined plot: {str(e)}'}, status=500)




   # Handle single observation case
   logger.info(f"[plot_gti] Handling single observation for obs_id: {obs_id}")
   single_obs_dir_path_relative = os.path.join(obs_id, 'jspipe/')


   files_qs = Item.objects.filter(
       name__contains=quality,
       path=single_obs_dir_path_relative,
       type=Item.item_type[1][0],
   ).order_by('name')
   logger.info(f"[plot_gti] Found {files_qs.count()} items for obs_id '{obs_id}', quality '{quality}' in path '{single_obs_dir_path_relative}'")


   plot_specific_files_qs = files_qs.filter(name__contains=PLOTS[plot_type]['file_type'])
   logger.info(f"[plot_gti] Found {plot_specific_files_qs.count()} files matching plot type '{plot_type}' (file_type: '{PLOTS[plot_type]['file_type']}')")


   if not plot_specific_files_qs.exists():
       logger.error(f"[plot_gti] No files found for plot type '{plot_type}' in obs '{obs_id}'. Cannot plot.")
       return JsonResponse({'error': f'No files found for plot type {plot_type} in observation {obs_id}'}, status=404)


   gti_list_parsed: list[int] = []
   if gti_query_str:
       processed_gti_query_parts = re.sub(r'[^\d,-]', '', gti_query_str).split(',')
       for gti_val_part in processed_gti_query_parts:
           if not gti_val_part: continue
           if re.search(r'^\d+-\d+$', gti_val_part):
               start_str, end_str = gti_val_part.split('-')
               start, end = int(start_str), int(end_str)
               if start > end: start, end = end, start
               gti_list_parsed.extend(range(start, end + 1))
           elif gti_val_part.isdigit():
               gti_list_parsed.append(int(gti_val_part))
       gti_list_parsed = sorted(list(set(gti_list_parsed)))

   use_all_hid_files = (plot_type == 'hardness_intensity_diagram' and not gti_list_parsed)

   final_file_paths_to_plot: list[str] = []
   final_gti_numbers_for_plot_func: list[int] = []
   full_dir_path_for_files = os.path.join(settings.DATA_DIR, single_obs_dir_path_relative)

   if gti_list_parsed:
       for gti_num in gti_list_parsed:
           file_match_item = plot_specific_files_qs.filter(
               name__regex=fr'GTI0*{gti_num}([^\d]|$)'
           ).first()
           if file_match_item:
               final_file_paths_to_plot.append(os.path.join(full_dir_path_for_files, file_match_item.name))
               final_gti_numbers_for_plot_func.append(gti_num)

   if not final_file_paths_to_plot:
       default_file_item = plot_specific_files_qs.first()
       if default_file_item:
           final_file_paths_to_plot.append(os.path.join(full_dir_path_for_files, default_file_item.name))
           match = re.search(r'GTI(\d+)', default_file_item.name)
           if match:
               final_gti_numbers_for_plot_func = [int(match.group(1))]
           else:
               final_gti_numbers_for_plot_func = [0]
       else:
           return JsonResponse({'error': 'No data files could be selected for plotting.'}, status=404)

   # Apply background screening if requested for spectrum plots
   screening_summary = None
   if apply_screening and plot_type in ['spectrum', 'summed_spectrum']:
       logger.info(f"[plot_gti] *** APPLYING BACKGROUND SCREENING ***")
       logger.info(f"[plot_gti] Energy range: {screening_energy_low}-{screening_energy_high} keV")
       logger.info(f"[plot_gti] Min bad channels: {screening_min_bad_channels}")
       logger.info(f"[plot_gti] Files to screen: {len(final_file_paths_to_plot)}")
       
       screened_files, screened_gtis, screening_results = screen_gti_files(
           final_file_paths_to_plot,
           final_gti_numbers_for_plot_func,
           energy_low=screening_energy_low,
           energy_high=screening_energy_high,
           min_bad_channels=screening_min_bad_channels
       )
       
       screening_summary = get_screening_summary(screening_results)
       logger.info(f"[plot_gti] Screening summary: {screening_summary}")
       
       if screened_files:
           original_count = len(final_file_paths_to_plot)
           final_file_paths_to_plot = screened_files
           final_gti_numbers_for_plot_func = screened_gtis
           logger.info(f"[plot_gti] Screening reduced files from {original_count} to {len(screened_files)}")
       else:
           logger.warning("[plot_gti] All GTI failed screening, using original files")
           screening_summary['all_failed'] = True
   elif apply_screening:
       logger.info(f"[plot_gti] Screening requested but plot type '{plot_type}' doesn't support it (only spectrum/summed_spectrum)")

   # Special handling for summed spectrum — use the already-screened files
   # from the block above.  No need to re-gather from the DB and re-screen;
   # that threw away the user's GTI selection AND duplicated the screening work.
   if plot_type == 'summed_spectrum':
       # final_file_paths_to_plot / final_gti_numbers_for_plot_func are
       # already correctly set (and already screened if screening was requested).
       logger.info(f"[plot_gti] Summed spectrum - using {len(final_file_paths_to_plot)} "
                   f"pre-selected/screened GTI files: GTIs {final_gti_numbers_for_plot_func}")

   # Special handling for HID - use all available GTI files only if no GTI were specified
   elif use_all_hid_files:
       logger.info(f"[plot_gti] HID detected with no GTI filter - using all available GTI files by default")
       all_gti_files = []
       all_gti_numbers = []
       for file_item in plot_specific_files_qs.order_by('name'):
           file_path = os.path.join(full_dir_path_for_files, file_item.name)
           all_gti_files.append(file_path)
           gti_match = re.search(r'GTI(\d+)', file_item.name)
           all_gti_numbers.append(int(gti_match.group(1)) if gti_match else 0)
       final_file_paths_to_plot = all_gti_files
       final_gti_numbers_for_plot_func = all_gti_numbers
       logger.info(f"[plot_gti] HID using {len(all_gti_files)} GTI files: GTIs {all_gti_numbers}")

   # Calculate default binning if needed
   if requested_min_value_str is None or requested_min_value_str == '':
       calculated_default = calculate_default_binning(final_file_paths_to_plot[0], plot_type)
       min_value = calculated_default

   logger.info(f"[plot_gti] Calling plotting function with {len(final_file_paths_to_plot)} files")

   # Determine if background should be dashed (unreliable screening)
   bg_dash = 'solid'
   if screening_summary and screening_summary.get('all_failed'):
       bg_dash = 'dash'
       logger.info(f"[plot_gti] Background line will be dashed (all GTIs failed screening)")

   try:
       # Only spectrum types accept bg_dash (they have background traces)
       if plot_type in ('spectrum', 'summed_spectrum'):
           plot_divs_html = PLOTS[plot_type]['function'](
               min_value,
               obs_id,
               final_file_paths_to_plot,
               final_gti_numbers_for_plot_func,
               bg_dash=bg_dash,
           )
       else:
           plot_divs_html = PLOTS[plot_type]['function'](
               min_value,
               obs_id,
               final_file_paths_to_plot,
               final_gti_numbers_for_plot_func,
           )
   except Exception as e:
       logger.exception(f"[plot_gti] Error during plot generation: {e}")
       return JsonResponse({'error': f'Error generating plot: {str(e)}'}, status=500)

   if plot_type == 'hardness_intensity_diagram':
       original_plot_type = 'time'

   response_data = {
       'plotDivs': [plot_divs_html],
       'defaultBinning': min_value,
       'plotType': original_plot_type,
       'resolvedPlotType': original_plot_type,
       'plotKeyHyphen': original_plot_type.replace('_', '-'),
       'plotKeyUnderscore': original_plot_type.replace('-', '_'),
   }
   
   # Include screening summary in response
   if screening_summary:
       response_data['screeningSummary'] = screening_summary
       logger.info(f"[plot_gti] Including screening summary in response: {screening_summary}")

   return JsonResponse(response_data)
    


def plot_data(request: HttpRequest) -> JsonResponse:
    """
    Tries to plot the specified data, matching the correct plot type


    Supports energy spectrum, light curve, and power density


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
    dir_path: str
    file_name: str
    obs_id: str = request.POST.get('obs_id')
    source: str = request.POST.get('source')
    quality: str = request.POST.get('quality')
    search_type: str = request.POST.get('search_type')
    max_gti: list[int] = []
    plot_divs: list[str] = []
    infos: list[dict[str, Any]] = []
    default_binnings: dict[str, int] = {}
    obs_ids: list[dict[str, str]]
    plot_type: dict[str, Any]
    logger: log.Logger = log.getLogger(__name__)
    info: np.ndarray
    indices: np.ndarray
    file_names: np.ndarray
    files: QuerySet
    obs_items: QuerySet

    # Extract screening parameters with EXTENSIVE logging
    logger.info("=" * 80)
    logger.info("[plot_data] *** BEGINNING SCREENING PARAMETER EXTRACTION ***")
    logger.info(f"[plot_data] Full POST data: {dict(request.POST)}")
    
    apply_screening_str = request.POST.get('apply_screening', 'false')
    logger.info(f"[plot_data] apply_screening raw string: '{apply_screening_str}' (type: {type(apply_screening_str)})")
    
    apply_screening = apply_screening_str.lower() == 'true'
    logger.info(f"[plot_data] apply_screening boolean: {apply_screening} (type: {type(apply_screening)})")
    
    screening_energy_low = 2.0
    screening_energy_high = 5.0
    screening_min_bad_channels = 2
    
    if apply_screening:
        logger.info("[plot_data] *** SCREENING IS ENABLED - EXTRACTING PARAMETERS ***")
        try:
            screening_energy_low = float(request.POST.get('screening_energy_low', 2.0))
            screening_energy_high = float(request.POST.get('screening_energy_high', 5.0))
            screening_min_bad_channels = int(request.POST.get('screening_min_bad_channels', 2))
            logger.info(f"[plot_data] Extracted screening params:")
            logger.info(f"[plot_data]   - energy_low: {screening_energy_low} keV")
            logger.info(f"[plot_data]   - energy_high: {screening_energy_high} keV")
            logger.info(f"[plot_data]   - min_bad_channels: {screening_min_bad_channels}")
        except (ValueError, TypeError) as e:
            logger.error(f"[plot_data] ERROR parsing screening params: {e}")
            logger.info("[plot_data] Using default screening values")
    else:
        logger.info("[plot_data] *** SCREENING IS DISABLED ***")
    
    logger.info("=" * 80)

    if search_type == 'source' and source:
        obs_items = Item.objects.filter(
            source__icontains=source,
            type=Item.item_type[1][0],
        ).values('path', 'source').distinct()


        obs_ids = []
        for item in obs_items:
            path_parts = item['path'].split('/')
            if len(path_parts) > 0:
                obs_ids.append({'obs_id': path_parts[0], 'source': item['source']})


        if len(obs_ids) > 1:
            return JsonResponse({
                'multiple_observations': True,
                'obs_ids': obs_ids,
                'source': source
            })


        obs_id = obs_ids[0]['obs_id'] if obs_ids else None


    if obs_id:
        files = Item.objects.filter(
            name__contains=quality,
            path__startswith=os.path.join(obs_id, 'jspipe/'),
            type=Item.item_type[1][0],
        ).order_by('name')
        print(f"Found {files.count()} files for obs_id {obs_id}")


    if not obs_id or not files.exists():
        return JsonResponse({
            'error': f'No observable data found for '
            f"{f'source: {source}' if search_type == 'source' else f'observation ID: {obs_id}'}"
        })

    item = files.first()
    obs_info = {
        'ra': item.ra,
        'dec': item.dec,
        'tstart_tt': item.tstart_tt,
        'tstop_tt': item.tstop_tt,
        'obs_id': obs_id,
        'source': source or item.source,
        'ndets_used': item.ndets_used,
        'ushoot_net_rate': item.ushoot_net_rate,
        'oshoot_net_rate': item.oshoot_net_rate,
        'goodx_5_12_rate': item.changegoodx_5_12_rate,
    }

    dir_path = os.path.join(settings.DATA_DIR, obs_id, 'jspipe/')
    screening_summaries = {}

    # Try to get data for specified plots
    try:
        # Get summary files for each GTI
        file_names_summary = np.array(
            files.filter(name__contains='BGDATA.summary').values_list('name', flat=True)
        )

        if file_names_summary.size == 0:
            return JsonResponse({'error': 'No summary files found for the given source name'})

        indices = np.argsort(
            [int(re.search(r'GTI(\d+)', file_name).group(1)) for file_name in file_names_summary]
        )

        found_source = None
        available_gti = set()
        for file_name in file_names_summary[indices]:
            gti_number = int(re.search(r'GTI(\d+)', file_name).group(1))
            available_gti.add(gti_number)

        if not available_gti:
            return JsonResponse({'error': 'No GTI data available'})

        for gti in range(max(available_gti) + 1):
            if gti not in available_gti:
                break
            file_name = re.sub(r'js_\d+_', f'js_{obs_id}_', file_names_summary[indices][gti])
            info = np.char.replace(np.loadtxt(
                os.path.join(dir_path, file_name),
                dtype=str,
                unpack=True,
            ), "'", '')
            info_dict = dict(zip(*info))
            infos.append(info_dict | {'GTI': f'GTI{gti}'})

            if 'OBJECT' in info_dict and not found_source:
                found_source = info_dict['OBJECT']

        # Reset exists flags for this request (global PLOTS dict is reused across requests)
        for _pt in PLOTS:
            PLOTS[_pt]['exists'] = False

        # Plot depending on the data type
        for plot_type, plot_info in PLOTS.items():
            # Check if this plot type is requested in the POST data
            if plot_type.replace('_', '-') in request.POST:
               logger.info("=" * 80)
               logger.info(f"[plot_data] *** PROCESSING PLOT TYPE: {plot_type} ***")
               plot_info['exists'] = True
               file_names = files.filter(name__contains=plot_info['file_type'])
               file_names = file_names.exclude(name__regex=r'_BAND\d+')
               
               if file_names:
                   max_gti.append(len(file_names))
                   
                   # Calculate default binning from first file
                   first_file = file_names.first()
                   first_file_path = dir_path + first_file.name
                   calculated_default = calculate_default_binning(first_file_path, plot_type)
                   default_binnings[plot_type] = calculated_default
                   default_binnings[plot_type.replace('_', '-')] = calculated_default
                   
                   if plot_type == 'hardness_intensity_diagram':
                       default_binnings['time'] = calculated_default

                   logger.info(f"[plot_data] Default binning for {plot_type}: {calculated_default}")
                   
                   # Prepare lists of files and GTIs
                   all_files = []
                   all_gtis = []
                   for file_item in file_names.order_by('name'):
                       all_files.append(dir_path + file_item.name)
                       gti_match = re.search(r'GTI(\d+)', file_item.name)
                       all_gtis.append(int(gti_match.group(1)) if gti_match else 0)

                   logger.info(f"[plot_data] Total files found: {len(all_files)}")
                   logger.info(f"[plot_data] GTI numbers: {all_gtis}")
                   logger.info(f"[plot_data] Sample file paths: {all_files[:3]}")

                   # Apply screening if requested
                   final_files = all_files
                   final_gtis = all_gtis

                   # CRITICAL DECISION POINT
                   logger.info("=" * 80)
                   logger.info(f"[plot_data] *** SCREENING DECISION POINT ***")
                   logger.info(f"[plot_data] Plot type: {plot_type}")
                   logger.info(f"[plot_data] Apply screening flag: {apply_screening}")
                   logger.info(f"[plot_data] Is spectrum type: {plot_type in ['spectrum', 'summed_spectrum']}")
                   logger.info(f"[plot_data] Will apply screening: {apply_screening and plot_type in ['spectrum', 'summed_spectrum']}")
                   
                   if apply_screening and plot_type in ['spectrum', 'summed_spectrum']:
                       logger.info("=" * 80)
                       logger.info(f"[plot_data] *** APPLYING BACKGROUND SCREENING ***")
                       logger.info(f"[plot_data] Energy range: {screening_energy_low}-{screening_energy_high} keV")
                       logger.info(f"[plot_data] Min bad channels: {screening_min_bad_channels}")
                       logger.info(f"[plot_data] Files to screen: {len(all_files)}")
                       logger.info(f"[plot_data] GTIs to screen: {all_gtis}")
                       
                       # Log each file path
                       for i, (fpath, gti) in enumerate(zip(all_files, all_gtis)):
                           logger.info(f"[plot_data]   File {i+1}: GTI {gti} - {fpath}")
                           logger.info(f"[plot_data]           Exists: {os.path.exists(fpath)}")
                       
                       passed_files, passed_gtis, results = screen_gti_files(
                            all_files, all_gtis, 
                            energy_low=screening_energy_low,
                            energy_high=screening_energy_high,
                            min_bad_channels=screening_min_bad_channels
                       )
                       
                       logger.info("=" * 80)
                       logger.info(f"[plot_data] *** SCREENING RESULTS ***")
                       logger.info(f"[plot_data] Passed files: {len(passed_files)}/{len(all_files)}")
                       logger.info(f"[plot_data] Passed GTIs: {passed_gtis}")
                       
                       # Log each screening result
                       for i, result in enumerate(results):
                           logger.info(f"[plot_data] Result {i+1}:")
                           logger.info(f"[plot_data]   GTI: {result.get('gti_number', 'unknown')}")
                           logger.info(f"[plot_data]   Passed: {result.get('passes', False)}")
                           logger.info(f"[plot_data]   Reason: {result.get('reason', 'unknown')}")
                           logger.info(f"[plot_data]   Bad channels: {result.get('bad_channel_count', 0)}/{result.get('total_channels_in_range', 0)}")
                           logger.info(f"[plot_data]   BG file found: {result.get('bg_file_found', False)}")
                       
                       summary = get_screening_summary(results)
                       screening_summaries[plot_type] = summary
                       logger.info(f"[plot_data] Summary: {summary}")
                       
                       if passed_files:
                           logger.info(f"[plot_data] *** USING SCREENED FILES ***")
                           logger.info(f"[plot_data] Original: {len(all_files)} files")
                           logger.info(f"[plot_data] After screening: {len(passed_files)} files")
                           final_files = passed_files
                           final_gtis = passed_gtis
                       else:
                           logger.warning("[plot_data] *** ALL GTIs FAILED SCREENING - USING ORIGINAL ***")
                           summary['all_failed'] = True
                   else:
                       logger.info(f"[plot_data] *** SCREENING NOT APPLIED ***")
                       if not apply_screening:
                           logger.info(f"[plot_data] Reason: Screening disabled")
                       elif plot_type not in ['spectrum', 'summed_spectrum']:
                           logger.info(f"[plot_data] Reason: Plot type '{plot_type}' doesn't support screening")

                   # Determine whether screening deemed the background
                   # unreliable (all GTIs failed).  If so, we still plot the
                   # unscreened data but show the background line dashed.
                   bg_dash = 'solid'
                   if (plot_type in screening_summaries
                           and screening_summaries[plot_type].get('all_failed')):
                       bg_dash = 'dash'
                       logger.info(f"[plot_data] Background line will be dashed (all GTIs failed screening)")

                   logger.info("=" * 80)
                   logger.info(f"[plot_data] *** CALLING PLOT FUNCTION ***")
                   logger.info(f"[plot_data] Final files to plot: {len(final_files)}")
                   logger.info(f"[plot_data] Final GTIs to plot: {final_gtis}")
                   
                   plot_function_start = time.time()
                   
                   # Special handling for summed spectrum - include all valid GTI files
                   if plot_type == 'summed_spectrum':
                       logger.info(f"[plot_data] Calling summed_spectrum with {len(final_files)} files")
                       plot_div = plot_info['function'](
                           calculated_default,
                           obs_id,
                           final_files,
                           final_gtis,
                           bg_dash=bg_dash,
                       )
                   elif plot_type == 'spectrum':
                       # Spectrum: use first valid file only, pass bg_dash
                       if final_files:
                            file_name_to_plot = final_files[0]
                            gti_to_plot = final_gtis[0]
                            logger.info(f"[plot_data] Calling spectrum with 1 file: {file_name_to_plot}")
                            plot_div = plot_info['function'](
                                calculated_default,
                                obs_id,
                                [file_name_to_plot],
                                [gti_to_plot],
                                bg_dash=bg_dash,
                            )
                       else:
                            logger.error(f"[plot_data] ERROR: No files available for spectrum")
                            continue
                   else:
                       # Regular handling for other plot types - use first valid file only
                       if final_files:
                            file_name_to_plot = final_files[0]
                            gti_to_plot = final_gtis[0]
                            logger.info(f"[plot_data] Calling {plot_type} with 1 file: {file_name_to_plot}")
                            plot_div = plot_info['function'](
                                calculated_default,
                                obs_id,
                                [file_name_to_plot],
                                [gti_to_plot],
                            )
                       else:
                            logger.error(f"[plot_data] ERROR: No files available for {plot_type}")
                            continue

                   plot_function_time = time.time() - plot_function_start
                   logger.info(f"[plot_data] Plot function completed in {plot_function_time:.3f}s")
                   logger.info("=" * 80)

                   plot_divs.append(plot_div)
               else:
                   logger.warning(f"[plot_data] No files found for plot type: {plot_type}")
                   max_gti.append(0)

    except AttributeError as error:
        logger.error(f'{error}\nNo valid data in {dir_path}')
        return JsonResponse({'error': f'Error processing data: {str(error)}'})

    logger.info("=" * 80)
    logger.info(f"[plot_data] *** FINAL RESPONSE ***")
    logger.info(f"[plot_data] Plots generated: {len(plot_divs)}")
    logger.info(f"[plot_data] Screening summaries: {screening_summaries}")
    logger.info(f"[plot_data] Default binnings: {default_binnings}")
    logger.info("=" * 80)

    return JsonResponse({
        'plotDivs': plot_divs,
        'obsID': obs_id,
        'quality': quality,
        'spectrum': PLOTS['spectrum']['exists'],
        'summedSpectrum': PLOTS['summed_spectrum']['exists'],
        'lightCurve': PLOTS['light_curve']['exists'],
        'powerSpectrum': PLOTS['power_density_spectrum']['exists'],
        'hardnessIntensity': PLOTS['hardness_intensity_diagram']['exists'],
        'maxGTI': max_gti,
        'info': infos,
        'source': found_source or source,
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
       Request containing the variable 'obs_id' or 'source' for search.
   count : int, default = 5
       Number of items to return.


   Returns
   -------
   JsonResponse
       JSON response containing a dictionary with matching items.
   """
   root: str = Item._meta.get_field('path').get_default()
   obs_id: str = request.GET.get('obs_id')
   source: str = request.GET.get('source')
   suggested_obs: QuerySet


   if obs_id:
       # Query the database for the first 5 observation IDs that match the query
       suggested_obs = Item.objects.filter(
           name__startswith=obs_id,
           path=root,
           type=Item.item_type[0][0],
       ).order_by('name')[:count]
   elif source:
       # Query the database for the first 5 source names that contain the query
       suggested_obs = Item.objects.filter(
           source__icontains=source,
           type=Item.item_type[1][0],
       ).values('source').distinct().order_by('source')[:count]
   else:
       return JsonResponse({'error': 'No observation ID or source name provided'})


   # Check if any results were found and return them
   if not suggested_obs.exists():
       return JsonResponse({'error': 'Observational data not found'})


   # Return the relevant data based on whether obs_id or source was searched
   if obs_id:
       return JsonResponse({'dir_suggestions': list(suggested_obs.values_list('name', flat=True))})
   else:
       return JsonResponse({'dir_suggestions': list(suggested_obs.values_list('source', flat=True))})




def fetch_sources(request: HttpRequest, count: int = 5) -> JsonResponse:
   """
   Queries the data base for source names that contain the provided string
   """
   source_query = request.GET.get('source')
   suggested_sources = Item.objects.filter(
       source__icontains=source_query
   ).values('source').distinct().order_by('source')[:count]


   return JsonResponse({'source_suggestions': list(suggested_sources)})




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


def create_gti_archive(obs_id, gti_list, base_path):
   """Create a zip archive of GTI files"""
   logger.info(f"Creating GTI archive for OBS_ID {obs_id}, GTIs: {gti_list}")


   jspipe_dir = base_path / obs_id / 'jspipe'


   if not jspipe_dir.exists():
       return HttpResponse(f'Directory not found: {jspipe_dir}', status=404)


   with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
       with zipfile.ZipFile(tmp.name, 'w') as archive:
           files_added = False


           if not gti_list:
               for file in jspipe_dir.glob(f'js_ni{obs_id}*_GTI*'):
                   logger.info(f"Adding file to archive: {file}")
                   archive.write(str(file), file.name)
                   files_added = True
           else:
               for gti_num in gti_list:
                   for file in jspipe_dir.glob(f'js_ni{obs_id}*_GTI{gti_num}'):
                       if f'_GTI{gti_num}' in str(file):
                           logger.info(f"Adding file to archive: {file}")
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


   logger.info(f"Download request - Type: {data_type}, OBS_ID: {obs_id}, GTI: {gti_numbers_str}, Quality: {quality}")


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
                                   logger.warning(f"No files found for GTI{gti_num} with quality {quality}")


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
       logger.exception("Error in download_data")
       return HttpResponse(f'Error: {str(e)}', status=500)


   return HttpResponse('Invalid request', status=400)


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



