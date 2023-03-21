"""
Utilities to normalise and bin spectra
"""
import re

import numpy as np
from numpy import ndarray
from astropy.io import fits

from src.utils.plots import data_plot
from src.utils.utils import min_bin, binning


def channel_kev(channel: ndarray) -> ndarray:
    """
    Convert units of channel to keV

    Parameters
    ----------
    channel : ndarray
        Detector channels

    Returns
    -------
    ndarray
        Channels in units of keV
    """
    return (channel * 10 + 5) / 1e3


def spectrum_data(
        min_value: int,
        data_path: str,
        cut_off: list = None) -> tuple[ndarray, ndarray, ndarray, ndarray, ndarray]:
    """
    Fetches binned data from spectrum

    Returns the binned x, y spectrum data as a 2D array

    Parameters
    ----------
    min_value : integer
        Minimum value for each bin, if None, groupings will be used
    data_path : string
        File path to the spectrum
    cut_off : list, default = [0.3, 10]
        Range of accepted data in keV

    Returns
    -------
    tuple[ndarray, ndarray, ndarray, ndarray, ndarray]
        Binned energies, binned spectrum data, binned background, x error, & binned uncertainties
    """
    if not cut_off:
        cut_off = [0.3, 10]

    # Fetch spectrum & background fits files
    with fits.open(data_path) as file:
        spectrum_info = file[1].header
        spectrum = file[1].data
        response = spectrum_info['RESPFILE']
        detectors = int(re.search(r'_d(\d+)', response).group(1))

    with fits.open(data_path.replace('.jsgrp', '.bg')) as file:
        bg_info = file[1].header
        background = file[1].data


    # Pre binned data
    x_data = channel_kev(spectrum['CHANNEL'])
    energy = x_data[1] - x_data[0]
    groupings = spectrum['GROUPING']
    bins = np.argwhere(groupings == 1)[:, 0]

    # Bin data either by groupings or by minimum value
    if min_value:
        (y_bin, bg_bin, x_bin), x_width, uncertainty = min_bin(
            min_value,
            np.stack((spectrum['COUNTS'], background['COUNTS'], x_data)),
        )
    else:
        (y_bin, bg_bin, x_bin), uncertainty = binning(
            bins,
            np.stack((spectrum['COUNTS'], background['COUNTS'], x_data)),
        )
        bins = np.append(bins, len(groupings))
        x_width = np.diff(bins)

    # Normalization
    y_bin = (
        y_bin / spectrum_info['EXPOSURE'] - bg_bin / bg_info['EXPOSURE']
    ) / (detectors * energy)
    bg_bin /= bg_info['EXPOSURE'] * detectors * energy
    x_error = x_width * energy / 2
    uncertainty /= spectrum_info['EXPOSURE'] * detectors * energy

    # Energy range cut-off
    cut_indices = np.argwhere((x_bin < cut_off[0]) | (x_bin > cut_off[1]))
    x_bin = np.delete(x_bin, cut_indices)
    y_bin = np.delete(y_bin, cut_indices)
    bg_bin = np.delete(bg_bin, cut_indices)
    x_error = np.delete(x_error, cut_indices)
    uncertainty = np.delete(uncertainty, cut_indices, axis=1)

    return x_bin, y_bin, bg_bin, x_error, uncertainty[0]


def spectrum_plot(
        min_value: int,
        data_paths: list[str],
        gti_numbers: list[int],
        cut_off: list = None) -> str:
    """
    Gets and plots the binned and corrected spectra

    Parameters
    ----------
    min_value : integer
        Minimum value for each bin, if None, groupings will be used
    data_paths : list[string]
        File paths to the spectra
    gti_numbers: list[integer]
        List of GTI numbers
    cut_off : list, default = [0.3, 10]
        Range of accepted data in keV

    Returns
    -------
    string
        Spectrum plot as HTML
    """
    # Constants
    x_data = []
    y_data = []
    background = []
    x_error = []
    y_uncertainties = []

    # Get spectrum data
    for data_path in data_paths:
        data = spectrum_data(min_value, data_path, cut_off=cut_off)

        x_data.append(data[0])
        y_data.append(data[1])
        background.append(data[2])
        x_error.append(data[3])
        y_uncertainties.append(data[4])

    kwargs = {
        'title' : 'Spectrum',
        'xaxis_title' : r'$\text{Energy}\ (keV)$',
        'xaxis_type' : 'log',
        'yaxis_title' : r'$\text{Photons}\ (keV^{-1} s^{-1} det^{-1})$',
        'yaxis_type' : 'log',
        'showlegend': True,
    }

    # Plot spectrum
    return data_plot(
        gti_numbers,
        x_data,
        y_data,
        kwargs,
        background=background,
        x_error=x_error,
        y_uncertainties=y_uncertainties,
    )
