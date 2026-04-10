"""
Utilities to process and plot summed spectra across multiple GTIs
"""
import re
import os
import time
import logging
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd
from numpy import ndarray
from astropy.io import fits

from src.apps.plots.plots import data_plot
from src.apps.plots.spectrum_preprocessing import channel_kev

# Set up logging
logger = logging.getLogger(__name__)


def summed_spectrum_data(
    data_paths: List[str],
    gti_numbers: List[int],
    cut_off: Tuple[float, float] = (0.3, 12)
) -> Tuple[ndarray, ndarray, ndarray, ndarray, ndarray]:
    """
    Sum spectral data across multiple GTIs and compute net rate and background.

    This function normalizes the spectral data to counts per channel to account for
    varying bin sizes in the grouped spectrum. The energy bins contain different
    numbers of original detector channels, with more channels per bin at higher
    energies. By dividing by the number of channels per bin, we get a proper
    count rate per channel that accurately represents the spectral shape.

    Parameters
    ----------
    data_paths : List[str]
        List of file paths to the spectrum files (.jsgrp format)
    gti_numbers : List[int]
        List of GTI numbers to process
    cut_off : Tuple[float, float], optional
        Energy range to include (default: 0.3 to 12 keV)

    Returns
    -------
    Tuple[ndarray, ndarray, ndarray, ndarray, ndarray]
        x_bin (energy), net_rate (counts/s/det/channel), net_rate_error,
        net_background (counts/s/det/channel), x_error
    """
    if not data_paths or not gti_numbers:
        raise ValueError("No data paths or GTI numbers provided")

    # Initialize accumulation arrays
    summed_spec = None
    summed_background = None
    summed_time = 0.0
    summed_52time = 0.0
    channels = None
    groupings = None

    # Process each GTI
    for i, (data_path, gti_number) in enumerate(zip(data_paths, gti_numbers)):
        if not os.path.exists(data_path):
            logger.warning(f"Spectrum file not found: {data_path}")
            continue

        # Read spectrum file
        with fits.open(data_path) as spec_file:
            spectrum_info = spec_file[1].header
            spectrum_data = spec_file[1].data

            # Get detector count from response file
            response = spectrum_info['RESPFILE']
            nfpm = int(re.search(r'_d(\d+)', response).group(1))

            # Get exposure time
            gti_time = float(spectrum_info['EXPOSURE'])

        # Read background files
        bg_path = data_path.replace('.jsgrp', '.bg')
        ronbg_path = data_path.replace('.jsgrp', '.ronbg')

        # Initialize arrays on first iteration
        if summed_spec is None:
            channels = spectrum_data['CHANNEL']
            groupings = spectrum_data['GROUPING']
            summed_spec = np.zeros_like(spectrum_data['COUNTS'], dtype=float)
            summed_background = np.zeros_like(spectrum_data['COUNTS'], dtype=float)

        # Sum spectral counts: summed_spec[i] = summed_spec[i] + gti_spec[i,j]
        summed_spec += spectrum_data['COUNTS'].astype(float)

        # Handle background files
        if os.path.exists(bg_path):
            with fits.open(bg_path) as bg_file:
                bg_info = bg_file[1].header
                bg_data = bg_file[1].data

                # Convert to pandas DataFrame for easier column access
                bg_df = pd.DataFrame(bg_data)

                if 'RATE' in bg_df.columns:
                    # Convert rate to counts if needed
                    bg_counts = bg_df['RATE'] * bg_info['EXPOSURE']
                else:
                    bg_counts = bg_df['COUNTS']
                summed_background += bg_counts.astype(float)
        else:
            logger.warning(f"Background file not found: {bg_path}")

        # Handle .ronbg files for readout noise background
        if os.path.exists(ronbg_path):
            with fits.open(ronbg_path) as ronbg_file:
                ronbg_data = ronbg_file[1].data

                # Convert to pandas DataFrame for easier column access
                ronbg_df = pd.DataFrame(ronbg_data)

                if 'RATE' in ronbg_df.columns:
                    ronbg_counts = ronbg_df['RATE'] * gti_time
                else:
                    ronbg_counts = ronbg_df['COUNTS']

                # Add readout noise background to total background
                summed_background += ronbg_counts.astype(float)
        else:
            logger.debug(f"Readout noise background file not found: {ronbg_path}")

        # Track exposure times
        summed_time += gti_time
        summed_52time += gti_time * nfpm / 52.0

    if summed_spec is None:
        raise ValueError("No valid spectrum files found")

    # Calculate error bars: summed_error_cts[i] = sqrt(summed_spec[i] > 1)
    summed_error_cts = np.sqrt(np.maximum(summed_spec, 1))

    # Convert channels to energy
    x_data = channel_kev(channels)
    energy_bin_width = float(x_data[1] - x_data[0])

    # Apply grouping to bin the data
    bins = np.argwhere(groupings == 1).flatten()
    bins = np.append(bins, len(groupings))

    # Bin the data
    x_bin = []
    net_rate = []
    net_rate_error = []
    net_background = []

    for i in range(len(bins) - 1):
        start_idx = bins[i]
        end_idx = bins[i + 1]

        # Energy bin center
        energy_center = np.mean(x_data[start_idx:end_idx])
        x_bin.append(energy_center)

        # Sum counts in this energy bin
        spec_counts = np.sum(summed_spec[start_idx:end_idx])
        bg_counts = np.sum(summed_background[start_idx:end_idx])
        error_counts = np.sqrt(np.sum(summed_error_cts[start_idx:end_idx]**2))

        # Number of channels in this bin (key fix: normalize by channels per bin)
        channels_per_bin = end_idx - start_idx

        # Calculate net rate per channel:
        net_rate_val = (spec_counts - bg_counts) / (summed_52time * channels_per_bin)
        net_rate.append(net_rate_val)

        # Error bars per channel: similarly normalized by channels per bin
        net_rate_error_val = error_counts / (summed_52time * channels_per_bin)
        net_rate_error.append(net_rate_error_val)

        # Background overlay per channel: also normalized by channels per bin
        net_bg_val = bg_counts / (summed_52time * channels_per_bin)
        net_background.append(net_bg_val)

    # Convert to numpy arrays
    x_bin = np.array(x_bin)
    net_rate = np.array(net_rate)
    net_rate_error = np.array(net_rate_error)
    net_background = np.array(net_background)

    # Calculate bin-by-bin raw counts for display
    bin_spec_counts = []
    bin_bg_counts = []
    bin_net_counts = []
    bin_channels = []

    for i in range(len(bins) - 1):
        start_idx = bins[i]
        end_idx = bins[i + 1]
        channels_in_bin = end_idx - start_idx
        spec_counts = np.sum(summed_spec[start_idx:end_idx])
        bg_counts = np.sum(summed_background[start_idx:end_idx])
        net_counts = spec_counts - bg_counts
        bin_spec_counts.append(spec_counts)
        bin_bg_counts.append(bg_counts)
        bin_net_counts.append(net_counts)
        bin_channels.append(channels_in_bin)

    # Validate energy cut-off bounds
    if cut_off[0] >= cut_off[1]:
        raise ValueError(f"Invalid energy cut-off range: {cut_off[0]} >= {cut_off[1]}")

    energy_mask = (x_bin >= cut_off[0]) & (x_bin <= cut_off[1])

    # Check if any data remains after cut-off
    if not np.any(energy_mask):
        logger.warning(f"Energy cut-off {cut_off} excludes all data. Data range: "
                       f"{x_bin.min():.3f}-{x_bin.max():.3f} keV")
        # Apply a more lenient cut-off to retain some data
        energy_mask = np.ones_like(x_bin, dtype=bool)

    # Apply energy mask to all arrays
    x_bin = x_bin[energy_mask]
    net_rate = net_rate[energy_mask]
    net_rate_error = net_rate_error[energy_mask]
    net_background = net_background[energy_mask]

    # Check for any problematic values
    neg_rate_count = np.sum(net_rate < 0)
    zero_error_count = np.sum(net_rate_error <= 0)
    inf_count = np.sum(~np.isfinite(net_rate))

    if neg_rate_count > 0:
        print(f"WARNING: {neg_rate_count} bins have negative net rates (background > source)")
    if zero_error_count > 0:
        print(f"WARNING: {zero_error_count} bins have zero/negative error bars")
    if inf_count > 0:
        print(f"ERROR: {inf_count} bins have non-finite values")

    # Handle edge case where no data remains
    if len(x_bin) == 0:
        raise ValueError("No data remaining after energy cut-off and quality checks")

    # Calculate x_error using actual bin widths for better accuracy
    if len(x_bin) > 1:
        # Calculate individual bin widths
        x_widths = np.diff(x_bin)
        # For the last bin, use the same width as the previous bin
        x_widths = np.append(x_widths, x_widths[-1])
        x_error = x_widths / 2
    else:
        # Fallback to energy_bin_width for single bin
        x_error = np.array([energy_bin_width / 2])
    return x_bin, net_rate, net_rate_error, net_background, x_error


def summed_spectrum_plot(
    min_value: int,
    obs_id: int,
    data_paths: List[str],
    gti_numbers: List[int],
    cut_off: Optional[Tuple[float, float]] = None,
    gti_labels: Optional[List[str]] = None,
    bg_dash: str = 'solid') -> str:
    # pylint: disable=line-too-long
    """
    Create a summed spectrum plot across multiple GTIs.

    This function implements the summed spectrum algorithm as specified:
    - Sums spectral counts across GTIs: summed_spec[i] = summed_spec[i] + gti_spec[i,j]
    - Tracks exposure time: summed_time = summed_time + gti_time[j]
    - Tracks 52-FPM normalized exposure: summed_52time = summed_52time + gti_time[j]*gti_nfpm[i]/52
    - Handles different background file types:
      * .bg files (counts): summed as counts
      * .ronbg files (count rate): summed_ronbg[i] = summed_ronbg[i] + gti_ronbg_rate[i,j] * gti_time[j]
    - Calculates net rate per channel: net_rate[i] = (summed_spec[i] - summed_background[i]) / (summed_52time * channels_per_bin[i])
    - Calculates error bars per channel: net_rate_error[i] = sqrt(summed_spec[i] > 1) / (summed_52time * channels_per_bin[i])
    - Provides background overlay per channel: net_background[i] = summed_background[i] / (summed_52time * channels_per_bin[i])

    Note: The per-channel normalization corrects for varying bin sizes in the grouped spectrum,
    where higher energy bins contain more detector channels than lower energy bins.

    Parameters
    ----------
    min_value : int
        Minimum value for each bin (currently not used for summed spectrum)
    obs_id : int
        Observation ID
    data_paths : List[str]
        File paths to the spectra (.jsgrp files)
    gti_numbers : List[int]
        List of GTI numbers
    cut_off : Optional[Tuple[float, float]]
        Range of accepted data in keV (default: 0.3 to 12 keV)
    gti_labels : Optional[List[str]]
        List of GTI labels (not used for summed spectrum)

    Returns
    -------
    str
        Summed spectrum plot as HTML
    """
    # pylint: enable=line-too-long
    if cut_off is None:
        cut_off = (0.3, 12)

    logger.info(f"Input: {len(data_paths)} data paths, {len(gti_numbers)} GTI numbers")
    logger.info(f"Energy cut-off: {cut_off} keV")

    # Validate inputs
    if not data_paths:
        logger.error("No data paths provided for summed spectrum")
        return "Error: No data paths provided for summed spectrum"

    if not gti_numbers:
        logger.error("No GTI numbers provided for summed spectrum")
        return "Error: No GTI numbers provided for summed spectrum"

    if len(data_paths) != len(gti_numbers):
        logger.error(f"Mismatch: {len(data_paths)} data paths vs {len(gti_numbers)} GTI numbers")
        return "Error: Number of data paths must match number of GTI numbers"

    # Check for existing files
    valid_paths = []
    valid_gtis = []
    missing_files = []

    for path, gti in zip(data_paths, gti_numbers):
        if os.path.exists(path):
            valid_paths.append(path)
            valid_gtis.append(gti)
            logger.debug(f"Found file for GTI {gti}: {path}")
        else:
            missing_files.append(f"GTI{gti}: {path}")
            logger.warning(f"Missing file for GTI {gti}: {path}")

    if not valid_paths:
        error_msg = (f"Error: No valid spectrum files found. Missing files: "
                     f"{'; '.join(missing_files)}")
        logger.error(error_msg)
        return error_msg

    if missing_files:
        warning_msg = f"Warning: Some files missing for summed spectrum: {'; '.join(missing_files)}"
        logger.warning(warning_msg)
        print(warning_msg)

    # Get summed spectrum data
    plot_start_time = time.time()
    x_bin, net_rate, net_rate_error, net_background, x_error = summed_spectrum_data(
        valid_paths, valid_gtis, cut_off
    )
    data_time = time.time() - plot_start_time
    logger.info(f"Data processing completed in {data_time:.3f}s")

    # Calculate total exposure times from already processed data by re-reading headers efficiently
    total_exposure = 0.0
    total_52time = 0.0

    # More efficient: read only headers, not full data
    for path in valid_paths:
        try:
            with fits.open(path) as spec_file:
                spectrum_info = spec_file[1].header
                response = spectrum_info['RESPFILE']
                nfpm = int(re.search(r'_d(\d+)', response).group(1))
                gti_time = float(spectrum_info['EXPOSURE'])
                total_exposure += gti_time
                total_52time += gti_time * nfpm / 52.0
        except Exception as e:
            logger.warning(f"Could not read exposure from {path}: {e}")
            continue

    # Validate data before plotting
    if len(x_bin) == 0 or len(net_rate) == 0:
        raise ValueError("No data available for plotting after processing")

    if not np.all(np.isfinite(x_bin)) or not np.all(np.isfinite(net_rate)):
        logger.warning("Non-finite values detected in plot data - replacing with zeros")
        x_bin = np.nan_to_num(x_bin)
        net_rate = np.nan_to_num(net_rate)
        net_rate_error = np.nan_to_num(net_rate_error)
        net_background = np.nan_to_num(net_background)

    return data_plot(
        gti_numbers=[0],  # Single trace for summed data
        x_data_list=[x_bin],
        y_data_list=[net_rate],
        x_background_list=[x_bin],
        background_list=[net_background],
        x_errors=[x_error],
        y_uncertainties=[net_rate_error],
        plot_kwargs={'mode': 'markers', 'bg_dash': bg_dash},
        layout_kwargs={
            'title': f'Summed Spectrum {obs_id}',
            'xaxis_title': r'$\text{Energy}\ (keV)$',
            'yaxis_title': r'$\text{Net Rate}\ (counts\ s^{-1}\ det^{-1})$',
            'xaxis_type': 'log',
            'yaxis_type': 'log',
            'showlegend': True,
        },
        gti_labels=[f'Spectrum']
    )


def create_exportable_summed_spectrum(
    data_paths: List[str],
    gti_numbers: List[int],
    output_path: str,
    obs_id: Optional[str] = None
) -> str:
    """
    Create exportable FITS files for summed spectrum in standard 1501-channel format.

    This function creates properly formatted FITS files that can be used with spectral
    fitting tools like XSPEC. It maintains the original 1501-channel structure and
    properly tracks exposure times and observation metadata.

    Parameters
    ----------
    data_paths : List[str]
        List of file paths to the spectrum files (.jsgrp format)
    gti_numbers : List[int]
        List of GTI numbers to process
    output_path : str
        Base path for output files (without extension)
    obs_id : Optional[str]
        Observation ID for file naming

    Returns
    -------
    str
        Status message describing created files
    """
    start_time = time.time()
    logger.info(f"Creating exportable summed spectrum for {len(data_paths)} files")
    logger.info(f"GTI numbers: {gti_numbers}")
    logger.info(f"Output path: {output_path}")

    if not data_paths or not gti_numbers:
        raise ValueError("No data paths or GTI numbers provided")

    # Initialize accumulation arrays for 1501 channels
    summed_spec = None
    summed_background = None
    summed_total_bg = None  # For separate background file
    summed_time = 0.0
    summed_52time = 0.0

    # Track timing information for headers
    first_start_time = None
    last_stop_time = None
    all_start_times = []
    all_stop_times = []

    # Store header information from first file
    master_header = None
    response_file = None

    # Process each GTI file
    for i, (data_path, gti_number) in enumerate(zip(data_paths, gti_numbers)):
        logger.info(f"Processing GTI {gti_number} ({i+1}/{len(data_paths)}): {data_path}")

        if not os.path.exists(data_path):
            logger.warning(f"Spectrum file not found: {data_path}")
            continue

        # Read spectrum file
        with fits.open(data_path) as spec_file:
            spectrum_info = spec_file[1].header
            spectrum_data = spec_file[1].data

            # Store master header from first file
            if master_header is None:
                master_header = spectrum_info.copy()
                response_file = spectrum_info.get('RESPFILE', '')

            # Get exposure time and timing info
            gti_time = float(spectrum_info['EXPOSURE'])
            gti_start = spectrum_info.get('TSTART', 0.0)
            gti_stop = spectrum_info.get('TSTOP', 0.0)

            # Track timing for combined header
            all_start_times.append(gti_start)
            all_stop_times.append(gti_stop)

            if first_start_time is None or gti_start < first_start_time:
                first_start_time = gti_start
            if last_stop_time is None or gti_stop > last_stop_time:
                last_stop_time = gti_stop

            # Get detector count from response file
            nfpm = int(re.search(r'_d(\d+)', spectrum_info['RESPFILE']).group(1))

            # Initialize arrays on first iteration (maintain 1501 channels)
            if summed_spec is None:
                logger.info("Initializing summed spectrum arrays for 1501 channels")
                channels = spectrum_data['CHANNEL']
                if len(channels) != 1501:
                    logger.warning(f"Expected 1501 channels, found {len(channels)}")

                summed_spec = np.zeros(1501, dtype=float)
                summed_background = np.zeros(1501, dtype=float)
                summed_total_bg = np.zeros(1501, dtype=float)

                # Store grouping and quality flags from parent spectrum
                if 'GROUPING' in spectrum_data.dtype.names:
                    parent_grouping = spectrum_data['GROUPING']
                else:
                    parent_grouping = np.ones(1501, dtype=np.int16)

                if 'QUALITY' in spectrum_data.dtype.names:
                    parent_quality = spectrum_data['QUALITY']
                else:
                    parent_quality = np.zeros(1501, dtype=np.int16)

            # Sum spectral counts (maintain full 1501-channel resolution)
            spec_counts = spectrum_data['COUNTS'].astype(float)
            if len(spec_counts) == 1501:
                summed_spec += spec_counts
            else:
                logger.warning(f"Spectrum has {len(spec_counts)} channels, expected 1501")
                # Pad or truncate to 1501 channels
                if len(spec_counts) < 1501:
                    padded_spec = np.zeros(1501)
                    padded_spec[:len(spec_counts)] = spec_counts
                    summed_spec += padded_spec
                else:
                    summed_spec += spec_counts[:1501]

        # Read background files
        bg_path = data_path.replace('.jsgrp', '.bg')
        ronbg_path = data_path.replace('.jsgrp', '.ronbg')

        # Handle .bg files
        if os.path.exists(bg_path):
            logger.debug(f"Reading background file: {bg_path}")
            with fits.open(bg_path) as bg_file:
                bg_info = bg_file[1].header
                bg_data = bg_file[1].data

                if 'RATE' in bg_data.dtype.names:
                    # Convert rate to counts
                    bg_counts = bg_data['RATE'] * bg_info['EXPOSURE']
                else:
                    bg_counts = bg_data['COUNTS']

                # Ensure 1501 channels
                if len(bg_counts) == 1501:
                    summed_background += bg_counts.astype(float)
                    summed_total_bg += bg_counts.astype(float)
                else:
                    logger.warning(f"Background has {len(bg_counts)} channels, expected 1501")
                    if len(bg_counts) < 1501:
                        padded_bg = np.zeros(1501)
                        padded_bg[:len(bg_counts)] = bg_counts
                        summed_background += padded_bg
                        summed_total_bg += padded_bg
                    else:
                        summed_background += bg_counts[:1501].astype(float)
                        summed_total_bg += bg_counts[:1501].astype(float)

        # Handle .ronbg files (readout noise background)
        if os.path.exists(ronbg_path):
            logger.debug(f"Reading readout noise background file: {ronbg_path}")
            with fits.open(ronbg_path) as ronbg_file:
                ronbg_info = ronbg_file[1].header
                ronbg_data = ronbg_file[1].data

                if 'RATE' in ronbg_data.dtype.names:
                    # For .ronbg files, convert rate to counts
                    ronbg_counts = ronbg_data['RATE'] * gti_time
                else:
                    ronbg_counts = ronbg_data['COUNTS']

                # Ensure 1501 channels
                if len(ronbg_counts) == 1501:
                    summed_background += ronbg_counts.astype(float)
                    summed_total_bg += ronbg_counts.astype(float)
                else:
                    logger.warning(
                        f"RON background has {len(ronbg_counts)} channels, expected 1501",
                    )
                    if len(ronbg_counts) < 1501:
                        padded_ronbg = np.zeros(1501)
                        padded_ronbg[:len(ronbg_counts)] = ronbg_counts
                        summed_background += padded_ronbg
                        summed_total_bg += padded_ronbg
                    else:
                        summed_background += ronbg_counts[:1501].astype(float)
                        summed_total_bg += ronbg_counts[:1501].astype(float)

        # Track exposure times
        summed_time += gti_time
        summed_52time += gti_time * nfpm / 52.0

        logger.info(f"GTI {gti_number} processed: {gti_time:.2f}s exposure, {nfpm} FPMs")

    if summed_spec is None:
        raise ValueError("No valid spectrum files found")

    # Create output files
    output_files = []

    # 1. Create summed spectrum file (.pha or .fits)
    spectrum_filename = f"{output_path}_summed_spectrum.pha"
    create_spectrum_fits_file(
        spectrum_filename,
        summed_spec,
        master_header,
        summed_time,
        summed_52time,
        first_start_time,
        last_stop_time,
        gti_numbers,
        obs_id,
        parent_grouping,
        parent_quality
    )
    output_files.append(spectrum_filename)

    # 2. Create summed background file (.bg)
    background_filename = f"{output_path}_summed_background.bg"
    create_background_fits_file(
        background_filename,
        summed_total_bg,
        master_header,
        summed_time,
        first_start_time,
        last_stop_time,
        gti_numbers,
        obs_id
    )
    output_files.append(background_filename)

    # 3. Create response matrix link/copy if needed
    if response_file and os.path.exists(response_file):
        response_filename = f"{output_path}_response.rmf"
        # Copy or link the response file
        import shutil
        try:
            shutil.copy2(response_file, response_filename)
            output_files.append(response_filename)
            logger.info(f"Response file copied to {response_filename}")
        except Exception as e:
            logger.warning(f"Could not copy response file: {e}")

    # Summary file creation removed per user request

    processing_time = time.time() - start_time
    logger.info(f"Exportable summed spectrum created in {processing_time:.3f}s")
    logger.info(f"Created files: {output_files}")

    # Create status message
    status_msg = f"Successfully created exportable summed spectrum:\n"
    status_msg += f"- Total GTIs: {len(gti_numbers)}\n"
    status_msg += f"- Total exposure: {summed_time:.2f} s\n"
    status_msg += f"- 52-FPM normalized exposure: {summed_52time:.2f} s\n"
    status_msg += f"- Channel format: 1501 channels (exportable)\n"
    status_msg += f"- Output files: {len(output_files)}\n"
    for file in output_files:
        status_msg += f"  • {os.path.basename(file)}\n"

    return status_msg


def create_spectrum_fits_file(filename, counts, master_header, exposure_time,
                             exposure_52fpm, start_time, stop_time, gti_numbers,
                             obs_id, parent_grouping, parent_quality):
    """Create a properly formatted spectrum FITS file."""
    logger.info(f"Creating spectrum FITS file: {filename}")

    # Create channel array (0-1500) - XSPEC expects 0-based indexing
    channels = np.arange(0, 1501, dtype=np.int16)

    # Create data table
    col1 = fits.Column(name='CHANNEL', format='I', array=channels)
    col2 = fits.Column(name='COUNTS', format='J', array=counts.astype(np.int32))

    # Use grouping and quality flags from parent spectrum
    col3 = fits.Column(name='GROUPING', format='I', array=parent_grouping)
    col4 = fits.Column(name='QUALITY', format='I', array=parent_quality)

    # Create table
    cols = fits.ColDefs([col1, col2, col3, col4])
    tbhdu = fits.BinTableHDU.from_columns(cols)

    # Update header with summed information
    tbhdu.header['EXTNAME'] = 'SPECTRUM'
    tbhdu.header['TELESCOP'] = master_header.get('TELESCOP', 'NICER')
    tbhdu.header['INSTRUME'] = master_header.get('INSTRUME', 'XTI')
    tbhdu.header['EXPOSURE'] = exposure_time
    tbhdu.header['LIVETIME'] = exposure_time  # Assume same as exposure
    tbhdu.header['DEADC'] = 1.0  # Assume no deadtime correction needed
    tbhdu.header['TSTART'] = start_time
    tbhdu.header['TSTOP'] = stop_time
    tbhdu.header['DATE-OBS'] = master_header.get('DATE-OBS', '')
    tbhdu.header['TIME-OBS'] = master_header.get('TIME-OBS', '')

    # Add OGIP compliance keywords
    tbhdu.header['HDUCLASS'] = 'OGIP'
    tbhdu.header['HDUCLAS1'] = 'SPECTRUM'
    tbhdu.header['HDUCLAS2'] = 'TOTAL'
    tbhdu.header['HDUCLAS3'] = 'COUNT'
    tbhdu.header['HDUVERS'] = '1.2.0'

    # Column-specific keywords
    tbhdu.header['TUNIT2'] = 'count'
    tbhdu.header['TLMIN1'] = 0
    tbhdu.header['TLMAX1'] = 1500

    # Detector and channel keywords
    tbhdu.header['DETCHANS'] = 1501
    tbhdu.header['CHANTYPE'] = 'PI'

    # Error and scaling keywords
    tbhdu.header['POISSERR'] = True
    tbhdu.header['STAT_ERR'] = 0
    tbhdu.header['SYS_ERR'] = 0
    tbhdu.header['BACKSCAL'] = 1.0
    tbhdu.header['AREASCAL'] = 1.0

    # Add observation metadata
    if obs_id:
        tbhdu.header['OBS_ID'] = obs_id
    tbhdu.header['OBJECT'] = master_header.get('OBJECT', '')
    tbhdu.header['RA_OBJ'] = master_header.get('RA_OBJ', 0.0)
    tbhdu.header['DEC_OBJ'] = master_header.get('DEC_OBJ', 0.0)

    # Add summing metadata
    tbhdu.header['SUMMED'] = True
    tbhdu.header['N_GTIS'] = len(gti_numbers)
    tbhdu.header['GTI_LIST'] = ','.join(map(str, gti_numbers))
    tbhdu.header['EXP_52FPM'] = exposure_52fpm
    tbhdu.header['CREATOR'] = 'NICER Website Summed Spectrum Tool'
    tbhdu.header['HISTORY'] = f'Summed spectrum from {len(gti_numbers)} GTIs: {gti_numbers}'

    # Response file reference
    respfile = master_header.get('RESPFILE', '')
    if respfile:
        tbhdu.header['RESPFILE'] = respfile
        tbhdu.header['ANCRFILE'] = master_header.get('ANCRFILE', '')
        # Add BACKFILE reference with just the filename (no path)
        bg_filename = f"{os.path.splitext(os.path.basename(filename))[0].replace('_summed_spectrum', '_summed')}_background.bg"
        tbhdu.header['BACKFILE'] = bg_filename

    # Create primary HDU and write file
    primary_hdu = fits.PrimaryHDU()
    hdul = fits.HDUList([primary_hdu, tbhdu])
    hdul.writeto(filename, overwrite=True)
    logger.info(f"Created spectrum FITS file: {filename}")


def create_background_fits_file(filename, bg_counts, master_header, exposure_time,
                               start_time, stop_time, gti_numbers, obs_id):
    """Create a properly formatted background FITS file."""
    logger.info(f"Creating background FITS file: {filename}")

    # Create channel array (0-1500) - consistent with spectrum file
    channels = np.arange(0, 1501, dtype=np.int16)

    # Calculate statistical errors: 50% of background counts with floor of 1 count
    stat_err = np.maximum(bg_counts * 0.5, 1.0).astype(np.float32)

    # Create data table with STAT_ERR column
    col1 = fits.Column(name='CHANNEL', format='I', array=channels)
    col2 = fits.Column(name='COUNTS', format='J', array=bg_counts.astype(np.int32))
    col3 = fits.Column(name='STAT_ERR', format='E', unit='count', array=stat_err)

    # Create table
    cols = fits.ColDefs([col1, col2, col3])
    tbhdu = fits.BinTableHDU.from_columns(cols)

    # Update header
    tbhdu.header['EXTNAME'] = 'SPECTRUM'  # Background files use SPECTRUM extension too
    tbhdu.header['TELESCOP'] = master_header.get('TELESCOP', 'NICER')
    tbhdu.header['INSTRUME'] = master_header.get('INSTRUME', 'XTI')
    tbhdu.header['EXPOSURE'] = exposure_time
    tbhdu.header['LIVETIME'] = exposure_time
    tbhdu.header['TSTART'] = start_time
    tbhdu.header['TSTOP'] = stop_time
    tbhdu.header['DATE-OBS'] = master_header.get('DATE-OBS', '')
    tbhdu.header['TIME-OBS'] = master_header.get('TIME-OBS', '')

    # Add OGIP compliance keywords
    tbhdu.header['HDUCLASS'] = 'OGIP'
    tbhdu.header['HDUCLAS1'] = 'SPECTRUM'
    tbhdu.header['HDUVERS'] = '1.2.0'

    # Background-specific scaling keywords
    tbhdu.header['CORRSCAL'] = 1.0
    tbhdu.header['AREASCAL'] = 1.0
    tbhdu.header['BACKSCAL'] = 1.0

    # Detector and channel keywords
    tbhdu.header['DETCHANS'] = 1501
    tbhdu.header['CHANTYPE'] = 'PI'

    # Error handling keyword
    tbhdu.header['POISSERR'] = False  # We provide explicit STAT_ERR column

    # Table structure keyword
    tbhdu.header['TFIELDS'] = 3

    # Add metadata
    if obs_id:
        tbhdu.header['OBS_ID'] = obs_id
    tbhdu.header['OBJECT'] = master_header.get('OBJECT', '')
    tbhdu.header['SUMMED'] = True
    tbhdu.header['N_GTIS'] = len(gti_numbers)
    tbhdu.header['GTI_LIST'] = ','.join(map(str, gti_numbers))
    tbhdu.header['CREATOR'] = 'NICER Website Summed Spectrum Tool'
    tbhdu.header['HISTORY'] = f'Summed background from {len(gti_numbers)} GTIs: {gti_numbers}'

    # Create primary HDU and write file
    primary_hdu = fits.PrimaryHDU()
    hdul = fits.HDUList([primary_hdu, tbhdu])
    hdul.writeto(filename, overwrite=True)
    logger.info(f"Created background FITS file: {filename}")


def create_exportable_summed_spectrum_files(
    min_value: int,
    obs_id: int,
    data_paths: List[str],
    gti_numbers: List[int],
    output_dir: str = "/tmp"
) -> str:
    """
    Create exportable FITS files for summed spectrum that can be used with spectral fitting tools.

    This function generates properly formatted FITS files in the standard 1501-channel format
    that can be imported into XSPEC, ISIS, and other spectral analysis software.

    Parameters
    ----------
    min_value : int
        Minimum value for each bin (not used but kept for compatibility)
    obs_id : int
        Observation ID
    data_paths : List[str]
        File paths to the spectra (.jsgrp files)
    gti_numbers : List[int]
        List of GTI numbers
    output_dir : str
        Directory to save the output files

    Returns
    -------
    str
        Status message with information about created files
    """
    logger.info(f"Creating exportable files for observation {obs_id}")
    logger.info(f"Input: {len(data_paths)} data paths, {len(gti_numbers)} GTI numbers")

    # Validate inputs
    if not data_paths:
        return "Error: No data paths provided for summed spectrum"

    if not gti_numbers:
        return "Error: No GTI numbers provided for summed spectrum"

    if len(data_paths) != len(gti_numbers):
        return "Error: Number of data paths must match number of GTI numbers"

    # Check for existing files
    valid_paths = []
    valid_gtis = []

    for path, gti in zip(data_paths, gti_numbers):
        if os.path.exists(path):
            valid_paths.append(path)
            valid_gtis.append(gti)
        else:
            logger.warning(f"Missing file for GTI {gti}: {path}")

    if not valid_paths:
        return "Error: No valid spectrum files found"

    try:
        # Create output path
        if len(valid_gtis) > 1:
            gti_range = f"GTI{min(valid_gtis)}-{max(valid_gtis)}"
        else:
            gti_range = f"GTI{valid_gtis[0]}"

        output_base = os.path.join(output_dir, f"obs_{obs_id}_{gti_range}")

        # Create the exportable files
        result_message = create_exportable_summed_spectrum(
            valid_paths,
            valid_gtis,
            output_base,
            str(obs_id)
        )

        return result_message

    except Exception as e:
        error_msg = f"Error creating exportable files: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg
