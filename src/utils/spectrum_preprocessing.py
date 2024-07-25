"""
Utilities to normalise and bin spectra
"""
import re

import numpy as np
import pandas as pd
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
        cut_off: tuple[float, float] | None = None) -> tuple[
    ndarray,
    ndarray,
    ndarray,
    ndarray,
    ndarray,
    ndarray,
]:
    """
    Fetches and corrects binned data from spectrum

    Parameters
    ----------
    min_value : int
        Minimum value for each bin, if None, groupings will be used
    data_path : str
        File path to the spectrum
    cut_off : tuple[float, float], default = (0.3, 10)
        Range of accepted data in keV

    Returns
    -------
    tuple[ndarray, ndarray, ndarray, ndarray, ndarray, ndarray]
        Binned energies, spectrum data, background energies, background, x error, & uncertainties
    """
    detectors: int
    energy: float
    response: str
    bg_interp_indices: tuple[ndarray, ndarray]
    bins: ndarray
    x_bin: ndarray
    y_bin: ndarray
    bg_bin: ndarray
    x_data: ndarray
    x_width: ndarray
    x_error: ndarray
    min_bins: ndarray
    bg_x_bin: ndarray
    groupings: ndarray
    bg_bin_cut: ndarray
    uncertainty: ndarray
    cut_indices: ndarray
    background: pd.DataFrame
    bg_info: fits.Header
    spectrum_info: fits.Header
    spectrum: fits.FITS_rec

    if not cut_off:
        cut_off = (0.3, 12)

    # Fetch spectrum & background fits files
    with fits.open(data_path) as file:
        spectrum_info = file[1].header
        spectrum = file[1].data
        response = spectrum_info['RESPFILE']
        detectors = int(re.search(r'_d(\d+)', response).group(1))

    with fits.open(data_path.replace('.jsgrp', '.bg')) as file:
        bg_info = file[1].header
        background = pd.DataFrame(file[1].data)

    if 'RATE' in background:
        background['COUNTS'] = background['RATE'] * bg_info['EXPOSURE']

    # Pre binned data
    x_data = channel_kev(spectrum['CHANNEL'])
    energy = float(x_data[1] - x_data[0])
    groupings = spectrum['GROUPING']
    bins = np.argwhere(groupings == 1).flatten()
    bins = np.append(bins, len(groupings))

    # Bin data based on groupings
    (y_bin, bg_bin, x_bin), _, uncertainty = binning(
        bins,
        np.stack((spectrum['COUNTS'], background['COUNTS'], x_data)),
    )
    x_width = np.diff(bins)

    # If data should be binned to maintain minimum counts per bin
    if min_value:
        min_bins = min_bin(min_value, y_bin * x_width)
        (y_bin, bg_bin, x_bin), x_width, uncertainty = binning(
            min_bins,
            np.stack((y_bin, bg_bin, x_bin)),
            weights=x_width,
        )

    # Normalization
    y_bin = (
        y_bin / spectrum_info['EXPOSURE'] - bg_bin / bg_info['EXPOSURE']
    ) / (detectors * energy)
    bg_bin /= bg_info['EXPOSURE'] * detectors * energy
    x_error = x_width * energy / 2
    uncertainty /= spectrum_info['EXPOSURE'] * detectors * energy

    # Energy range cut-off
    cut_indices = np.argwhere((x_bin < cut_off[0]) | (x_bin > cut_off[1]))
    bg_interp_indices = (
        np.argwhere(x_bin < cut_off[0]).flatten()[-1:] + 1 or np.array([0]),
        np.argwhere(x_bin > cut_off[1]).flatten()[0:1] - 1 or np.array([-1]),
    )

    # Interpolate background data to the edge of the first and last bin within the energy range
    bg_bin_cut = np.delete(bg_bin, cut_indices)
    bg_bin = np.insert(bg_bin_cut, [0, bg_bin_cut.size], [
        np.interp(x_bin[bg_interp_indices[0]] - x_error[bg_interp_indices[0]], x_bin, bg_bin)[0],
        np.interp(x_bin[bg_interp_indices[1]] + x_error[bg_interp_indices[1]], x_bin, bg_bin)[0],
    ])

    # Remove data outside of the energy range
    x_bin = np.delete(x_bin, cut_indices)
    y_bin = np.delete(y_bin, cut_indices)
    x_error = np.delete(x_error, cut_indices)
    uncertainty = np.delete(uncertainty, cut_indices, axis=1)
    bg_x_bin = x_bin.copy()
    bg_x_bin = np.insert(
        bg_x_bin,
        [0, bg_x_bin.size],
        [x_bin[0] - x_error[0], x_bin[-1] + x_error[-1]],
    )

    return x_bin, y_bin, bg_x_bin, bg_bin, x_error, uncertainty[0]


def spectrum_plot(
        min_value: int,
        data_paths: list[str],
        gti_numbers: list[int],
        cut_off: list = None) -> str:
    """
    Gets and plots the binned and corrected spectra

    Parameters
    ----------
    min_value : int
        Minimum value for each bin, if None, groupings will be used
    data_paths : list[str]
        File paths to the spectra
    gti_numbers: list[int]
        List of GTI numbers
    cut_off : list, default = [0.3, 10]
        Range of accepted data in keV

    Returns
    -------
    str
        Spectrum plot as HTML
    """
    x_data: list[ndarray] = []
    y_data: list[ndarray] = []
    x_error: list[ndarray] = []
    background: list[ndarray] = []
    x_background: list[ndarray] = []
    y_uncertainties: list[ndarray] = []

    # Get spectrum data
    for data_path in data_paths:
        for data_list, data in zip([
            x_data,
            y_data,
            x_background,
            background,
            x_error,
            y_uncertainties
        ], spectrum_data(min_value, data_path, cut_off=cut_off)):
            data_list.append(data)

    # Plot spectrum
    return data_plot(
        gti_numbers = gti_numbers,
        x_data_list = x_data,
        y_data_list = y_data,
        x_background_list=x_background,
        background_list=background,
        x_errors=x_error,
        y_uncertainties=y_uncertainties,
        plot_kwargs={'mode': 'markers'},
        layout_kwargs={
            'title': 'Spectrum',
            'xaxis_title': r'$\text{Energy}\ (keV)$',
            'yaxis_title': r'$\text{Photons}\ (keV^{-1} s^{-1} det^{-1})$',
            'xaxis_type':'log',
            'yaxis_type':'log',
            'showlegend' : True,
        }
    )
