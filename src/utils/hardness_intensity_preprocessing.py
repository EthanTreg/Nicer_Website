"""
Utilities to correct HID (Hardness-Intensity Diagram)
"""
import os
from typing import List, Tuple, Any

import numpy as np
from numpy import ndarray

from src.utils.plots import data_plot

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

def process_lc_file(filename: str) -> Tuple[ndarray, ndarray, ndarray]:
    """
    Process a lightcurve file and return time, hardness, and intensity.

    Parameters
    ----------
    filename : str
        Path to the lightcurve file.

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        A tuple containing:
        - time: Array of time values in seconds.
        - hardness: Array of hardness ratios (hard_band / soft_band).
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

    return time, hardness, intensity

def get_hid_data_and_plot(
    _: Any,
    data_paths: List[str],
    gti_numbers: List[int]
) -> str:
    """
    Process multiple lightcurve files and create a Hardness-Intensity Diagram (HID) plot.

    Parameters
    ----------
    _ : Any
        Unused parameter.
    data_paths : list[str]
        List of file paths to the lightcurve data files.
    gti_numbers : list[int]
        List of GTI numbers to process.

    Returns
    -------
    str
        HTML string of the generated HID plot.
    """
    all_hardness: List[float] = []
    all_intensity: List[float] = []
    all_time: List[float] = []

    for gti_number in gti_numbers:
        lc_path: str = data_paths[0].replace("GTI0", f"GTI{gti_number}")

        time, hardness, intensity = process_lc_file(lc_path)

        mask: ndarray = (hardness > 0) & (intensity > 0) & ~np.isnan(hardness) & ~np.isnan(intensity)
        all_time.extend(time[mask].tolist())
        all_hardness.extend(hardness[mask].tolist())
        all_intensity.extend(intensity[mask].tolist())

    if not all_hardness:
        return "No valid data to plot"

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

    norm_time: ndarray = (np.array(all_time) - np.min(all_time)) / (np.max(all_time) - np.min(all_time))

    return data_plot(
        x_data_list=[all_hardness],
        y_data_list=[all_intensity],
        color_data=norm_time.tolist(),
        plot_kwargs={'mode': 'markers'},
        layout_kwargs={
            'title': 'Hardness-Intensity Diagram',
            'xaxis_title': r'$\text{Hardness}\ (4-12\ keV / 2-4\ keV)$',
            'yaxis_title': r'$\text{Intensity}\ (counts/s)$',
            'xaxis_type': 'log',
            'yaxis_type': 'log',
            'xaxis_range': xaxis_range,
            'yaxis_range': yaxis_range,
            'showlegend': False,
        }
    )