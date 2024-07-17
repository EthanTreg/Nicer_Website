import numpy as np
from astropy.io import fits
from typing import List, Tuple, Any
from numpy import ndarray
import os
import logging

# Import the data_plot function
from src.utils.plots import data_plot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        raise FileNotFoundError(f"File not found: {normalized_path}")

    with fits.open(normalized_path) as hdul:
        logger.info(f"FITS file structure: {[hdu.name for hdu in hdul]}")

        header = hdul[1].header
        all_data = hdul[1].data

        logger.info(f"Data type: {type(all_data)}")
        logger.info(f"Data shape: {all_data.shape if hasattr(all_data, 'shape') else 'N/A'}")

        gti_data = []
        if isinstance(all_data, fits.fitsrec.FITS_rec):
            # Single table for all GTIs
            for gti_number in gti_numbers:
                gti_data.append(all_data)  # Append the same data for each requested GTI
        elif isinstance(all_data, np.ndarray) and len(all_data.shape) > 1:
            # Multiple GTIs in separate rows
            for gti_number in gti_numbers:
                if gti_number < len(all_data):
                    gti_data.append(all_data[gti_number])
                else:
                    logger.warning(f"GTI number {gti_number} out of range for file {file_path}")
        else:
            logger.error(f"Unexpected data type: {type(all_data)}")
            raise ValueError(f"Unexpected data type in FITS file: {type(all_data)}")

        logger.info(f"Number of GTIs processed: {len(gti_data)}")
        for i, data in enumerate(gti_data):
            logger.info(f"GTI {gti_numbers[i]} data type: {type(data)}")
            logger.info(f"GTI {gti_numbers[i]} data shape: {data.shape if hasattr(data, 'shape') else 'N/A'}")

    return gti_data, header

def process_pds_data(pds_data: np.ndarray, rsp_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    logger.info(f"pds_data type: {type(pds_data)}, shape: {pds_data.shape}")
    logger.info(f"rsp_data type: {type(rsp_data)}, shape: {rsp_data.shape}")

    def get_column(data, column_name):
        if isinstance(data, np.ndarray) and data.dtype.names is not None:
            # Structured array
            return data[column_name]
        elif isinstance(data, np.ndarray) and len(data.shape) == 2:
            # Regular 2D numpy array
            column_index = ['E_MIN', 'E_MAX', 'RATE', 'STAT_ERR'].index(column_name)
            return data[:, column_index]
        else:
            raise ValueError(f"Unexpected data type or shape: {type(data)}, shape: {data.shape}")

    try:
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

    except Exception as e:
        logger.error(f"Error in process_pds_data: {str(e)}")
        logger.error(f"PDS data first few rows: {pds_data[:5]}")
        logger.error(f"RSP data first few rows: {rsp_data[:5]}")
        raise


def get_pds_data_and_plot(min_value: int, data_paths: List[str], gti_numbers: List[int]) -> str:
    """
    Processes and plots PDS data for multiple files.

    Parameters
    ----------
    min_value : int
        Minimum value for each bin (not implemented in this version).
    data_paths : List[str]
        List of paths to PDS files.
    gti_numbers : List[int]
        List of GTI numbers.

    Returns
    -------
    str
        Plotly figure as HTML string or error message.
    """
    x_data_list: List[np.ndarray] = []
    y_data_list: List[np.ndarray] = []
    y_uncertainties: List[np.ndarray] = []
    gti_labels: List[str] = []

    logger.info(f"data_paths - {data_paths}")
    base_path = data_paths[0]
    logger.info(f"base_path - {base_path}")
    logger.info(f"gti_numbers - {gti_numbers}")


    for gti_number in gti_numbers:
        pds_path = base_path.replace("GTI0", f"GTI{gti_number}")
        rsp_path = pds_path.replace("-bin.pds", "-fak.rsp")

        try:
            logger.info(f"Processing PDS file: {pds_path}")
            pds_data_list, _ = read_fits_file(pds_path, [gti_number])

            logger.info(f"Processing RSP file: {rsp_path}")
            rsp_data_list, _ = read_fits_file(rsp_path, [gti_number])

            if pds_data_list and rsp_data_list:
                pds_data = pds_data_list[0]
                rsp_data = rsp_data_list[0]
                try:
                    freq_center, power_density, error_density = process_pds_data(pds_data, rsp_data)
                    x_data_list.append(freq_center)
                    y_data_list.append(power_density)
                    y_uncertainties.append(error_density)
                    gti_labels.append(f"GTI{gti_number}")
                except Exception as e:
                    logger.error(f"Error processing data for GTI{gti_number}: {str(e)}")
                    logger.error(
                        f"PDS data type: {type(pds_data)}, shape: {pds_data.shape if hasattr(pds_data, 'shape') else 'N/A'}")
                    logger.error(
                        f"RSP data type: {type(rsp_data)}, shape: {rsp_data.shape if hasattr(rsp_data, 'shape') else 'N/A'}")
                    continue
        except FileNotFoundError:
            logger.warning(f"Files for GTI{gti_number} not found. Skipping.")
            continue
        except Exception as e:
            logger.error(f"Error processing files for GTI{gti_number}: {str(e)}")
            continue

    if not x_data_list:
        error_msg = "No valid data to plot"
        logger.error(error_msg)
        return error_msg

    logger.info(f"Number of processed datasets: {len(x_data_list)}")
    for i, (x, y, yerr) in enumerate(zip(x_data_list, y_data_list, y_uncertainties)):
        logger.info(f"Dataset {i} ({gti_labels[i]}):")
        logger.info(f"  x_data shape: {x.shape}")
        logger.info(f"  y_data shape: {y.shape}")
        logger.info(f"  y_uncertainty shape: {yerr.shape}")

    # # Calculate logarithmic ranges with a margin
    margin_factor = 0.1  # 10% margin
    x_min = np.log10(min(np.min(data) for data in x_data_list))
    x_max = np.log10(max(np.max(data) for data in x_data_list))
    y_min = np.log10(min(np.min(data) for data in y_data_list))
    y_max = np.log10(max(np.max(data) for data in y_data_list))

    x_margin = (x_max - x_min) * margin_factor
    y_margin = (y_max - y_min) * margin_factor

    xaxis_range = [x_min - x_margin, x_max + x_margin]
    yaxis_range = [y_min - y_margin, y_max + y_margin]

    try:
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
    except Exception as e:
        error_msg = f"Error in data_plot: {str(e)}"
        logger.error(error_msg)
        return error_msg


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