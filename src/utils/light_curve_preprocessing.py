"""
Utility to correct light curve data
"""
import numpy as np

from src.utils.utils import min_bin
from src.utils.plots import data_plot


def light_curve_data(min_value: int, data_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fetches and corrects light curve data

    Parameters
    ----------
    min_value : integer
        Minimum value used for binning
    data_path : string
        Path to the light curve

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        Relative time, light curve and uncertainties
    """
    time, counts, detectors = np.loadtxt(data_path, usecols=[0, 2, 3], unpack=True)
    background = np.loadtxt(data_path.replace('.lc.gz', '.bg-lc.gz'), usecols=2)

    uncertainty = np.sqrt(np.maximum(counts, 1))
    min_value /= (time[1] - time[0])

    (x_bin, detectors), (y_bin, background_bin), uncertainty = min_bin(
        min_value,
        np.stack((time, detectors)),
        np.stack((counts, background)),
    )

    y_bin = (y_bin - background_bin) / detectors
    uncertainty /= detectors

    return x_bin, y_bin, uncertainty


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
    y_uncertainties = []

    # Get light curve data
    for data_path in data_paths:
        data = light_curve_data(min_value, data_path)

        x_data.append(data[0])
        y_data.append(data[1])
        y_uncertainties.append(data[2])

    # Plot light curve
    return data_plot(
        'Light Curve',
        r'$\text{Relative Time}\ (s)$',
        r'$\text{Photons}\ (s^{-1} det^{-1})$',
        gti_numbers,
        x_data,
        y_data,
        y_uncertainties,
    )
