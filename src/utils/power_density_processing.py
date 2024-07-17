"""
Utilities to correct PDS
"""
import os
from typing import List, Tuple, Any

import numpy as np
from numpy import ndarray
from astropy.io import fits

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


def get_column(data: ndarray, column_name: str) -> ndarray:
    """
    Gets the column given by a name for either an array or a structured array for the PDS

    Parameters
    ----------
    data : ndarray
        Data to index the column
    column_name : str
        Name of the column to index

    Returns
    -------
    ndarray
        Indexed array
    """
    if isinstance(data, ndarray) and data.dtype.names is not None:
        # Structured array
        return data[column_name]

    if isinstance(data, ndarray) and len(data.shape) == 2:
        # Regular 2D numpy array
        column_index = ['E_MIN', 'E_MAX', 'RATE', 'STAT_ERR'].index(column_name)
        return data[:, column_index]

    raise ValueError(f'Unexpected data type or shape: {type(data)}, shape: {data.shape}')


def read_fits_file(file_path: str, gti_numbers: List[int]) -> Tuple[List[Any], fits.Header]:
    """
    Reads a FITS file and returns the data and header.

    Parameters
    ----------
    file_path : str
        Path to the FITS file.
    gti_numbers : List[int]
        List of GTI numbers to filter the data.

    Returns
    -------
    Tuple[List[Any], fits.Header]
        Data arrays for each GTI and header from the FITS file.
    """
    normalized_path = os.path.normpath(file_path)
    if not os.path.exists(normalized_path):
        raise FileNotFoundError(f'File not found: {normalized_path}')

    with fits.open(normalized_path) as hdul:
        header = hdul[1].header
        all_data = hdul[1].data

        gti_data = []
        if isinstance(all_data, fits.fitsrec.FITS_rec):
            # Single table for all GTIs
            for _ in gti_numbers:
                gti_data.append(all_data)  # Append the same data for each requested GTI
        elif isinstance(all_data, ndarray) and len(all_data.shape) > 1:
            # Multiple GTIs in separate rows
            for gti_number in gti_numbers:
                if gti_number < len(all_data):
                    gti_data.append(all_data[gti_number])
        else:
            raise ValueError(f"Unexpected data type in FITS file: {type(all_data)}")

    return gti_data, header


def process_pds_data(
        pds_data: ndarray,
        rsp_data: ndarray) -> Tuple[ndarray, ndarray, ndarray]:
    """
    Processes the PDS data

    Parameters
    ----------
    pds_data : ndarray
        PDS data
    rsp_data : ndarray
        Response data

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        Average frequency, normalised power, and normalised error
    """
    freq_min = get_column(rsp_data, 'E_MIN')
    freq_max = get_column(rsp_data, 'E_MAX')
    freq_center = (freq_min + freq_max) / 2

    power = get_column(pds_data, 'RATE')
    error = get_column(pds_data, 'STAT_ERR')

    # Calculate frequency width
    freq_width = freq_max - freq_min

    # Divide rate and error by frequency width
    power_density = power / freq_width
    error_density = error / freq_width

    # Multiply by frequency to get f x PDS Power
    power_density = power_density * freq_center
    error_density = error_density * freq_center

    return freq_center, power_density, error_density


def get_pds_data_and_plot(_, data_paths: List[str], gti_numbers: List[int]) -> str:
    """
    Processes and plots PDS data for multiple files.

    Parameters
    ----------
    data_paths : List[str]
        List of paths to PDS files.
    gti_numbers : List[int]
        List of GTI numbers.

    Returns
    -------
    str
        Plotly figure as HTML string or error message.
    """
    x_data_list: List[ndarray] = []
    y_data_list: List[ndarray] = []
    y_uncertainties: List[ndarray] = []

    base_path = data_paths[0]

    for gti_number in gti_numbers:
        pds_path = base_path.replace('GTI0', f'GTI{gti_number}')
        rsp_path = pds_path.replace('-bin.pds', '-fak.rsp')

        pds_data_list, _ = read_fits_file(pds_path, [gti_number])
        rsp_data_list, _ = read_fits_file(rsp_path, [gti_number])

        if pds_data_list and rsp_data_list:
            pds_data = pds_data_list[0]
            rsp_data = rsp_data_list[0]
            freq_center, power_density, error_density = process_pds_data(pds_data, rsp_data)
            x_data_list.append(freq_center)
            y_data_list.append(power_density)
            y_uncertainties.append(error_density)

    if not x_data_list:
        error_msg = "No valid data to plot"
        return error_msg

    # # Calculate logarithmic ranges with a margin
    margin_factor = 0.1  # 10% margin
    x_min = np.log10(min(
        np.min(data, where=data > 0, initial=np.max(data)) for data in x_data_list
    ))
    x_max = np.log10(max(np.max(data) for data in x_data_list))
    y_min = np.log10(min(
        np.min(data, where=data > 0, initial=np.max(data)) for data in y_data_list
    ))
    y_max = np.log10(max(np.max(data) for data in y_data_list))

    x_margin = (x_max - x_min) * margin_factor
    y_margin = (y_max - y_min) * margin_factor

    xaxis_range = [x_min - x_margin, x_max + x_margin]
    yaxis_range = [y_min - y_margin, y_max + y_margin]

    return data_plot(
        gti_numbers=gti_numbers,
        x_data_list=x_data_list,
        y_data_list=y_data_list,
        plot_type='markers',
        y_uncertainties=y_uncertainties,
        x_errors=None,
        x_background_list=None,
        background_list=None,
        title='Power Density Spectrum',
        xaxis_title='Frequency (Hz)',
        yaxis_title='f x PDS Power (rms)',
        xaxis_type='log',
        yaxis_type='log',
        showlegend=True,
        xaxis_range=xaxis_range,
        yaxis_range=yaxis_range,
    )


# You might want to keep this function for compatibility or future use
def power_density_plot(
        min_value: int,
        data_paths: List[Tuple[str, str]],
        gti_numbers: List[int]) -> str:
    """
    Processes and plots PDS data for multiple files.
    This function is kept for compatibility but now uses get_pds_data_and_plot internally.

    Parameters
    ----------
    min_value : int
        Minimum value for each bin (not implemented in this version).
    data_paths : List[Tuple[str, str]]
        List of tuples containing paths to PDS and RSP files.
    gti_numbers : List[int]
        List of GTI numbers.

    Returns
    -------
    str
        Plotly figure as HTML string.
    """
    pds_paths = [pds_path for pds_path, _ in data_paths]
    return get_pds_data_and_plot(min_value, pds_paths, gti_numbers)
