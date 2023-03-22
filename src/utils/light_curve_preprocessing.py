"""
Utility to correct light curve data
"""
import numpy as np
from numpy import ndarray

from src.utils.utils import min_bin
from src.utils.plots import data_plot


def light_curve_data(
    min_value: int,
    data_path: str) -> tuple[ndarray, ndarray, ndarray, ndarray, ndarray, ndarray]:
    """
    Fetches and corrects binned light curve data

    Parameters
    ----------
    min_value : integer
        Minimum value used for binning
    data_path : string
        Path to the light curve

    Returns
    -------
    tuple[ndarray, ndarray, ndarray, ndarray, ndarray, ndarray]
        Binned relative time, light curve, background time, background, x width, and uncertainty
    """
    time, counts, detectors = np.loadtxt(data_path, usecols=[0, 2, 3], unpack=True)
    background = np.loadtxt(data_path.replace('.lc.gz', '.bg-lc.gz'), usecols=2)

    # Constants
    detectors = detectors[0]
    time_diff = time[1] - time[0]
    counts *= time_diff

    # Bin data
    (y_bin, bg_bin, x_bin), x_width, uncertainties = min_bin(
        min_value,
        np.stack((counts, background, time)),
    )

    # Normalise data
    y_bin = (y_bin - bg_bin) / (detectors * time_diff)
    bg_bin /= detectors
    bg_bin = np.insert(bg_bin, [0, -1], [bg_bin[0], bg_bin[-1]])
    x_error = x_width * time_diff / 2
    uncertainties /= detectors * time_diff
    bg_x_bin = x_bin.copy()
    bg_x_bin = np.insert(
        bg_x_bin,
        [0, bg_x_bin.size],
        [x_bin[0] - x_error[0], x_bin[-1] + x_error[-1]],
    )

    return x_bin, y_bin, bg_x_bin, bg_bin, x_error, uncertainties[0]


def light_curve_plot(min_value: int, data_paths: str, gti_numbers: list[int]) -> str:
    """
    Gets and plots the corrected light curve data

    Parameters
    ----------
    min_value : integer
        Minimum value used for binning
    data_path : string
        File path to the light curve
    gti_numbers : list[integer]
        List of GTI numbers

    Returns
    -------
    string
        Light curve plot as HTML
    """
    # Constants
    x_data = []
    y_data = []
    x_background = []
    background = []
    x_error = []
    y_uncertainties = []

    # Get light curve data
    for data_path in data_paths:
        for data_list, data in zip([
            x_data,
            y_data,
            x_background,
            background,
            x_error,
            y_uncertainties
        ], light_curve_data(min_value, data_path)):
            data_list.append(data)

    kwargs = {
        'title': 'Light Curve',
        'xaxis_title': r'$\text{Relative Time}\ (s)$',
        'yaxis_title': r'$\text{Photons}\ (s^{-1} det^{-1})$',
        'showlegend': True,
        'meta': data_paths[0],
    }

    # Plot light curve
    return data_plot(
        gti_numbers,
        x_data,
        y_data,
        kwargs,
        plot_type='lines+markers',
        x_background_list=x_background,
        background_list=background,
        x_error=x_error,
        y_uncertainties=y_uncertainties,
    )
