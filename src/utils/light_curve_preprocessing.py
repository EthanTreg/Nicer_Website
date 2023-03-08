"""
Utility to correct light curve data
"""
import numpy as np

from src.utils.plots import data_plot


def light_curve_data(data_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fetches and corrects light curve data

    Parameters
    ----------
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

    y_data = (counts - background) / detectors

    return time, y_data, uncertainty


def light_curve_plot(name: str, data_path: str) -> str:
    """
    Gets and plots the corrected light curve data

    Parameters
    ----------
    name : string
        Light curve name
    data_path : string
        File path to the light curve

    Returns
    -------
    string
        Light curve plot as HTML
    """
    # Get light curve data
    x_data, y_data, *_ = light_curve_data(data_path)

    # Plot light curve
    return data_plot(
        f'{name} Light Curve',
        r'$\text{Relative Time}\ (s)$',
        r'$\text{Photons}\ (s^{-1} det^{-1})$',
        x_data,
        y_data,
    )
