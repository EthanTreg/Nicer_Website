"""
Utilities to normalise and bin spectra
"""
import re

import numpy as np
from numpy import ndarray
from astropy.io import fits

from src.utils.utils import min_bin
from src.utils.plots import data_plot


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


def create_bin(
        x_data: ndarray,
        y_data: ndarray,
        clow: float,
        chi: float,
        nchan: int) -> tuple[ndarray, ndarray]:
    """
    Bins x & y data

    Removes data of bad quality defined as 1 [Not yet implemented]

    Parameters
    ----------
    x_data : ndarray
        x data that will be averaged per bin
    y_data : ndarray
        y data that will be summed per bin
    clow : float
        Lower limit of data that will be binned
    chi : float
        Upper limit of datat that will be binned
    nchan : integer
        Number of channels per bin

    Returns
    -------
    (ndarray, ndarray)
        Binned (x, y) data
    """
    x_data = x_data[clow:chi]
    y_data = y_data[clow:chi]

    x_data = np.mean(x_data.reshape(-1, int(nchan)), axis=1)
    y_data = np.sum(y_data.reshape(-1, int(nchan)), axis=1)

    return x_data, y_data


def binning(x_data: ndarray, y_data: ndarray, bins: ndarray) -> tuple[ndarray, ndarray, ndarray]:
    """
    Bins data to match binning performed in Xspec

    Parameters
    ----------
    x_data : ndarray
        x data to be binned
    y_data : ndarray
        y data to be binned
    bins : ndarray
        Array of bin change index & bin size

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        Binned x & y data & bin energy per data point
    """
    # Initialize variables
    x_bin = np.array(())
    y_bin = np.array(())
    energy_bin = np.array(())

    # Bin data
    for i in range(bins.shape[1] - 1):
        x_new, y_new = create_bin(x_data, y_data, bins[0, i], bins[0, i + 1], bins[1, i])
        x_bin = np.append(x_bin, x_new)
        y_bin = np.append(y_bin, y_new)
        energy_bin = np.append(energy_bin, [bins[1, i] * 1e-2] * y_new.size)

    return x_bin, y_bin, energy_bin


# def spectrum_data(
#         data_path: str,
#         cut_off: list = None) -> tuple[ndarray, ndarray, ndarray, int]:
#     """
#     Fetches binned data from spectrum

#     Returns the binned x, y spectrum data as a 2D array

#     Parameters
#     ----------
#     data_path : string
#         File path to the spectrum
#     cut_off : list, default = [0.3, 10]
#         Range of accepted data in keV

#     Returns
#     -------
#     (ndarray, ndarray, ndarray, integer)
#         Binned energies, binned spectrum data, binned uncertainties & number of detectors
#     """
#     bins = np.array([[0, 20, 248, 600, 1200, 1494, 1500], [2, 3, 4, 5, 6, 2, 1]], dtype=int)

#     if not cut_off:
#         cut_off = [0.3, 10]

#     # Fetch spectrum & background fits files
#     with fits.open(data_path) as file:
#         spectrum_info = file[1].header
#         spectrum = file[1].data
#         response = spectrum_info['RESPFILE']
#         detectors = int(re.search(r'_d(\d+)', response).group(1))

#     with fits.open(data_path.replace('.jsgrp', '.bg')) as file:
#         background_info = file[1].header
#         background = file[1].data


#     # Pre binned data
#     x_data = channel_kev(spectrum['CHANNEL'])
#     y_data = (
#         spectrum['COUNTS'] /
#         spectrum_info['EXPOSURE'] - background['COUNTS'] /
#         background_info['EXPOSURE']
#     ) / detectors

#     counts_bin = binning(x_data, spectrum['COUNTS'], bins)[1]

#     # Bin data
#     x_bin, (y_bin, background_bin), uncertainty = min_bin(
#         10,
#         x_data,
#         np.stack((spectrum['COUNTS'], background['COUNTS'])),
#     )

#     y_bin = (y_bin / spectrum_info['EXPOSURE'] - background_bin / background_info['EXPOSURE']) / detectors
#     x_bin, y_bin, energy_bin = binning(x_data, y_data, bins)
#     uncertainty = np.sqrt(np.maximum(counts_bin, 1)) / (spectrum_info['EXPOSURE'] * detectors)

#     # Energy normalization
#     y_bin /= energy_bin
#     uncertainty /= energy_bin

#     # Energy range cut-off
#     cut_indices = np.argwhere((x_bin < cut_off[0]) | (x_bin > cut_off[1]))
#     x_bin = np.delete(x_bin, cut_indices)
#     y_bin = np.delete(y_bin, cut_indices)
#     uncertainty = np.delete(uncertainty, cut_indices)
#     print(x_bin.shape)

#     return x_bin, y_bin, uncertainty, detectors


def spectrum_data(
        min_value: int,
        data_path: str,
        cut_off: list = None) -> tuple[ndarray, ndarray, ndarray, int]:
    """
    Fetches binned data from spectrum

    Returns the binned x, y spectrum data as a 2D array

    Parameters
    ----------
    data_path : string
        File path to the spectrum
    cut_off : list, default = [0.3, 10]
        Range of accepted data in keV

    Returns
    -------
    tuple[ndarray, ndarray, ndarray, integer]
        Binned energies, binned spectrum data, binned uncertainties & number of detectors
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
        background_info = file[1].header
        background = file[1].data


    # Pre binned data
    x_data = channel_kev(spectrum['CHANNEL'])
    energy = x_data[1] - x_data[0]

    # Bin data
    x_bin, (y_bin, background_bin), uncertainty = min_bin(
        min_value,
        x_data,
        np.stack((spectrum['COUNTS'], background['COUNTS'])),
    )

    # Normalization
    y_bin = (
        y_bin / spectrum_info['EXPOSURE'] - background_bin / background_info['EXPOSURE']
    ) / (detectors * energy)
    uncertainty /= spectrum_info['EXPOSURE'] * detectors * energy

    # Energy range cut-off
    cut_indices = np.argwhere((x_bin < cut_off[0]) | (x_bin > cut_off[1]))
    x_bin = np.delete(x_bin, cut_indices)
    y_bin = np.delete(y_bin, cut_indices)
    uncertainty = np.delete(uncertainty, cut_indices)

    return x_bin, y_bin, uncertainty, detectors


def spectrum_plot(
        min_value: int,
        data_paths: list[str],
        gti_numbers: list[int],
        cut_off: list = None) -> str:
    """
    Gets and plots the binned and corrected spectra

    Parameters
    ----------
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
    y_uncertainties = []

    # Get spectrum data
    for data_path in data_paths:
        data = spectrum_data(min_value, data_path, cut_off=cut_off)

        x_data.append(data[0])
        y_data.append(data[1])
        y_uncertainties.append(data[2])

    # Plot spectrum
    return data_plot(
        'Spectrum',
        r'$\text{Energy}\ (keV)$',
        r'$\text{Photons}\ (keV^{-1} s^{-1} det^{-1})$',
        gti_numbers,
        x_data,
        y_data,
        y_uncertainties,
    )

