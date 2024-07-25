import numpy as np
from typing import List, Tuple
import os
import logging
from src.utils.plots import data_plot


def normalize_path(path: str) -> str:
    """
       Normalize a file path by removing double slashes and resolving relative paths

       Parameters
       ----------
       path : str
           The file path to normalize

       Returns
       -------
       str
           The normalized file path
       """
    return os.path.normpath(path)


def read_lc_file(filename: str) -> np.ndarray:
    """
    Read a gzipped lightcurve file and return the data as a numpy array

    Parameters
    ----------
    filename : str
        Path to the gzipped lightcurve file

    Returns
    -------
    np.ndarray
        A 2D numpy array containing the lightcurve data
        Columns are [time, band1, band2, band3, band4]

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist
    """
    normalized_path = normalize_path(filename)
    if not os.path.exists(normalized_path):
        raise FileNotFoundError(f"File not found: {normalized_path}")

    data = np.loadtxt(normalized_path, usecols=[0, 5, 6, 7, 8])
    return data



def process_lc_file(filename: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
        Process a lightcurve file and return time, hardness, and intensity

        Parameters
        ----------
        filename : str
            Path to the lightcurve file

        Returns
        -------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            A tuple containing:
            - time: Array of time values in seconds
            - hardness: Array of hardness ratios (hard_band / soft_band)
            - intensity: Array of total intensity across all bands

        """
    lc_data = read_lc_file(filename)

    time = lc_data[:, 0] / 8  # to seconds
    band1 = lc_data[:, 1]  # 0.3-2 keV
    band2 = lc_data[:, 2]  # 2-4 keV
    band3 = lc_data[:, 3]  # 4-6 keV
    band4 = lc_data[:, 4]  # 6-12 keV

    soft_band = band2
    hard_band = band3 + band4

    with np.errstate(divide='ignore', invalid='ignore'):
        hardness = hard_band / soft_band

        # Replace infinities and NaNs with NaN
    hardness = np.where(np.isfinite(hardness), hardness, np.nan)

    intensity = band1 + band2 + band3 + band4  # sum of all bands, keeping as rate

    return time, hardness, intensity


def get_hid_data_and_plot(_, data_paths: List[str], gti_numbers: List[int]) -> str:
    """
    Process multiple lightcurve files and create a Hardness-Intensity Diagram (HID) plot

    Parameters
    ----------
    _ : Any
        Unused parameter
    data_paths : List[str]
        List of file paths to the lightcurve data files
    gti_numbers : List[int]
        List of GTI numbers to process

    Returns
    -------
    str
        HTML string of the generated HID plot
    """
    all_hardness = []
    all_intensity = []
    all_time = []

    for gti_number in gti_numbers:
        lc_path = data_paths[0].replace("GTI0", f"GTI{gti_number}")

        time, hardness, intensity = process_lc_file(lc_path)

        mask = (hardness > 0) & (intensity > 0) & ~np.isnan(hardness) & ~np.isnan(intensity)
        all_time.extend(time[mask])
        all_hardness.extend(hardness[mask])
        all_intensity.extend(intensity[mask])


    if not all_hardness:
        return "No valid data to plot"

    all_hardness = np.array(all_hardness)
    all_intensity = np.array(all_intensity)
    all_time = np.array(all_time)

    logging.warning(f"x data {all_hardness}")
    logging.warning(f"y data {all_intensity}")

    # logarithmic ranges with margin
    margin_factor = 0.1  # 10% margin
    x_min = np.log10(min(np.min(data) for data in all_hardness))
    x_max = np.log10(max(np.max(data) for data in all_hardness))
    y_min = np.log10(min(np.min(data) for data in all_intensity))
    y_max = np.log10(max(np.max(data) for data in all_intensity))

    x_margin = (x_max - x_min) * margin_factor
    y_margin = (y_max - y_min) * margin_factor

    xaxis_range = [x_min - x_margin, x_max + x_margin]
    yaxis_range = [y_min - y_margin, y_max + y_margin]

    norm_time = (all_time - np.min(all_time)) / (np.max(all_time) - np.min(all_time))

    return data_plot(
        x_data=all_hardness,
        y_data=all_intensity,
        color_data=norm_time,
        title='Hardness-Intensity Diagram',
        xaxis_title='Hardness (4-12 keV / 2-4 keV)',
        yaxis_title='Intensity (counts/s)',
        xaxis_type='log',
        yaxis_type='log',
        xaxis_range=xaxis_range,
        yaxis_range=yaxis_range,
    )
