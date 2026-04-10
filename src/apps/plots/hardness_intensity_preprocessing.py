"""
Utilities to correct HID (Hardness-Intensity Diagram)
"""
import os
from typing import List, Tuple

import numpy as np
from numpy import ndarray

from src.apps.plots.plots import data_plot

def normalize_path(path: str) -> str:
    """
    Normalize a file path by removing double slashes and resolving relative paths.

    Parameters
    ----------
    path : str
        The file path to normalize.

    Returns
    -------
    str
        The normalized file path.
    """
    return os.path.normpath(path)

def read_lc_file(filename: str) -> ndarray:
    """
    Read a gzipped lightcurve file and return the data as a numpy array.

    Parameters
    ----------
    filename : str
        Path to the gzipped lightcurve file.

    Returns
    -------
    ndarray
        A 2D numpy array containing the lightcurve data.
        Columns are [time, band1, band2, band3, band4].

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    """
    normalized_path: str = normalize_path(filename)
    if not os.path.exists(normalized_path):
        raise FileNotFoundError(f"File not found: {normalized_path}")

    data: ndarray = np.loadtxt(normalized_path, usecols=[0, 5, 6, 7, 8])
    return data

def process_lc_file(filename: str) -> Tuple[ndarray, ndarray, ndarray, ndarray]:
    """
    Process a lightcurve file and return time, hardness, and intensity.

    Parameters
    ----------
    filename : str
        Path to the lightcurve file.

    Returns
    -------
    tuple[ndarray, ndarray, ndarray, ndarray]
        A tuple containing:
        - time: Array of time values in seconds.
        - soft_band: soft band.
        - hard_band: hard band.
        - intensity: Array of total intensity across all bands.
    """
    lc_data: ndarray = read_lc_file(filename)

    time: ndarray = lc_data[:, 0] / 8  # to seconds
    band1: ndarray = lc_data[:, 1]  # 0.3-2 keV
    band2: ndarray = lc_data[:, 2]  # 2-4 keV
    band3: ndarray = lc_data[:, 3]  # 4-6 keV
    band4: ndarray = lc_data[:, 4]  # 6-12 keV

    soft_band: ndarray = band2
    hard_band: ndarray = band3 + band4

    with np.errstate(divide='ignore', invalid='ignore'):
        hardness: ndarray = hard_band / soft_band

    # Replace infinities and NaNs with NaN
    hardness = np.where(np.isfinite(hardness), hardness, np.nan)

    intensity: ndarray = band1 + band2 + band3 + band4  # sum of all bands, keeping as rate

    return time, soft_band, hard_band, intensity


def get_hid_data_and_plot(
    min_value: int,
    obs_id: int,
    data_paths: list[str],
    gti_numbers: list[int],
    gti_labels: list[str] | None) -> str:
    """
    Process multiple lightcurve files and create a Hardness-Intensity Diagram (HID) plot.

    Parameters
    ----------
    min_value : int
        Binning factor (number of time bins to combine)
    obs_id : int
        Observation ID
    data_paths : list[str]
        List of file paths to the lightcurve data files
    gti_numbers : list[int]
        List of GTI numbers to process
    gti_labels : list[str] | None, default = None
        List of labels for each GTI, if None GTI numbers will be used as labels

    Returns
    -------
    str
        JSON string of the generated HID plot.
    """
    # Treat min_value as a binning factor (combine N bins)
    binning_factor = int(min_value) if min_value and min_value > 0 else 1

    all_hardness: List[float] = []
    all_intensity: List[float] = []
    all_time: List[float] = []

    #atual coutns for binning
    all_soft_counts: List[float] = []
    all_hard_counts: List[float] = []
    all_intensity_counts: List[float] = []

    time_bin_width = None

    for gti_number in gti_numbers:
        lc_path: str = data_paths[0].replace("GTI0", f"GTI{gti_number}")
        time, soft_band, hard_band, intensity = process_lc_file(lc_path)
        hardness = hard_band / soft_band

        if time_bin_width is None:
            if len(time) > 1:
                dt = np.diff(time)
                detected_width = float(np.nanmedian(dt))
                if detected_width > 0:
                    time_bin_width = detected_width

            if time_bin_width is None:
                time_bin_width = 1.0 # / 8.0  # TODO: already being divided by 8 when getting time

        mask: ndarray = (hardness > 0) & (intensity > 0) & ~np.isnan(hardness) & \
                        ~np.isnan(intensity)
        all_time.extend(time[mask].tolist())
        all_hardness.extend(hardness[mask].tolist())
        all_intensity.extend(intensity[mask].tolist())

        current_soft_counts = soft_band[mask] * time_bin_width
        current_hard_counts = hard_band[mask] * time_bin_width
        current_intensity_counts = intensity[mask] * time_bin_width

        all_soft_counts.extend(current_soft_counts.tolist())
        all_hard_counts.extend(current_hard_counts.tolist())
        all_intensity_counts.extend(current_intensity_counts.tolist())

    if not all_hardness:
        return "No valid data to plot"

    all_hardness = np.array(all_hardness)
    all_intensity = np.array(all_intensity)
    all_time = np.array(all_time)
    all_hard_counts = np.array(all_hard_counts)
    all_intensity_counts = np.array(all_intensity_counts)
    all_soft_counts = np.array(all_soft_counts)

    if binning_factor > 1:
        sort_indices = np.argsort(all_time)
        all_time = all_time[sort_indices]
        all_intensity_counts = all_intensity_counts[sort_indices]
        all_hard_counts = all_hard_counts[sort_indices]
        all_soft_counts = all_soft_counts[sort_indices]
        n_points = len(all_time)
        n_bins = n_points // binning_factor
        limit = n_bins * binning_factor

        if n_bins > 0:
            #summing counts to bin
            binned_hard = all_hard_counts[:limit].reshape(n_bins, binning_factor).sum(axis=1)
            binned_soft = all_soft_counts[:limit].reshape(n_bins, binning_factor).sum(axis=1)
            binned_total = all_intensity_counts[:limit].reshape(n_bins, binning_factor).sum(axis=1)
            binned_time = all_time[:limit].reshape(n_bins, binning_factor).mean(axis=1)

            with np.errstate(divide='ignore', invalid='ignore'):
                new_hardness = binned_hard / binned_soft

            new_intensity = binned_total / (binning_factor * time_bin_width)
            all_hardness = new_hardness
            all_intensity = new_intensity
            all_time = binned_time

    final_mask = (all_hardness > 0) & (all_intensity > 0) & np.isfinite(all_hardness) & \
                 np.isfinite(all_intensity)
    all_hardness = all_hardness[final_mask]
    all_intensity = all_intensity[final_mask]
    all_time = all_time[final_mask]

    if len(all_hardness) == 0:
        return "No valid data to plot after binning"

    # logarithmic ranges with margin
    margin_factor: float = 0.1  # 10% margin
    x_min: float = np.log10(min(all_hardness))
    x_max: float = np.log10(max(all_hardness))
    y_min: float = np.log10(min(all_intensity))
    y_max: float = np.log10(max(all_intensity))

    x_margin: float = (x_max - x_min) * margin_factor
    y_margin: float = (y_max - y_min) * margin_factor

    xaxis_range: List[float] = [x_min - x_margin, x_max + x_margin]
    yaxis_range: List[float] = [y_min - y_margin, y_max + y_margin]

    norm_time: ndarray = (all_time - np.min(all_time)) / (np.max(all_time) - np.min(all_time))

    return data_plot(
        x_data_list=[all_hardness],
        y_data_list=[all_intensity],
        color_data=norm_time.tolist(),
        plot_kwargs={'mode': 'markers'},
        layout_kwargs={
            'title': f'Hardness-Intensity Diagram {obs_id}',
            'xaxis_title': r'$\text{Hardness}\ (4-12\ keV / 2-4\ keV)$',
            'yaxis_title': r'$\text{Intensity}\ (counts/s)$',
            'xaxis_type': 'log',
            'yaxis_type': 'log',
            'xaxis_range': xaxis_range,
            'yaxis_range': yaxis_range,
            'showlegend': False,
        },
        gti_labels=gti_labels,
    )
