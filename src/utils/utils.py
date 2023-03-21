"""
Misc functions used elsewhere
"""
import numpy as np
from numpy import ndarray


def min_bin(min_value: int, data: ndarray) -> tuple[ndarray, ndarray, ndarray]:
    """
    Ensures each bin has a minimum value.

    Parameters
    ----------
    min_value : integer
        Minimum value for each bin
    data : ndarray
        Data to bin, can be 2D where the rows correspond to different datasets
        and the first row is used to determine binning

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        Binned data, bin width, and Poisson uncertainty
    """
    # Constants
    i = 0
    bin_width = 1
    bins = np.array(())

    # Swaps axes for easier indexing and ensures data is 2D
    if len(data.shape) > 1:
        data = data.swapaxes(0, 1)
    else:
        data = data[:, np.newaxis]

    uncertainty = np.empty((0, data.shape[1]))

    # Loop through array except for the last bin and bins data
    while i < data.shape[0] - 1:
        # If the current bin is less than the minimum value, merge with next bin,
        # else normalise and move to the next bin
        if data[i, 0] < min_value:
            bin_width += 1
            data[i] += data[i + 1]
            data = np.delete(data, i + 1, axis=0)
        else:
            uncertainty = np.vstack((uncertainty, np.sqrt(np.maximum(data[i], 1)) / bin_width))
            data[i] /= bin_width
            bins = np.append(bins, bin_width)
            bin_width = 1
            i += 1

    # Deal with last bin and if it is less than the minimum value, merge with the previous bin
    if data[-1, 0] < min_value:
        data[-2] = data[-2] * bins[-1] + data[-1]
        data = np.delete(data, -1, axis=0)
        bins[-1] += bin_width
        uncertainty[-1] = np.sqrt(np.maximum(data[-1], 1)) / bins[-1]
        data[-1] /= bins[-1]
    else:
        bins = np.append(bins, bin_width)
        uncertainty = np.vstack((uncertainty, np.sqrt(np.maximum(data[-1], 1)) / bins[-1]))
        data[-1] /= bins[-1]

    # Revert shape to input
    if data.shape[1] != 1:
        data = data.swapaxes(0, 1)
        uncertainty = uncertainty.swapaxes(0, 1)
    else:
        data = data[:, 0]
        uncertainty = uncertainty[:, 0]

    return data, bins, uncertainty


def binning(bins: ndarray, data: ndarray) -> tuple[ndarray, ndarray]:
    """
    Bin data into bins.

    Parameters
    ----------
    bins : ndarray
        Array of bin edges
    data : ndarray
        Data to bin, can be 2D where the rows correspond to different datasets
        and the first row is used to determine binning

    Returns
    -------
    tuple[ndarray, ndarray]
        Binned data and Poisson uncertainty
    """
    # Swaps axes for easier indexing and ensures data is 2D
    if len(data.shape) > 1:
        data = data.swapaxes(0, 1)
    else:
        data = data[:, np.newaxis]

    # Constants
    data_bin = np.empty((0, data.shape[1]))
    uncertainty = np.empty((0, data.shape[1]))

    # Loop through array except for the last bin and bins data
    for i, idx in enumerate(bins[:-1]):
        data_bin = np.vstack((data_bin, np.mean(data[idx:bins[i + 1]], axis=0)))
        uncertainty = np.vstack((
            uncertainty,
            np.sqrt(np.sum(data[idx:bins[i + 1]], axis=0)) / (bins[i + 1] - idx),
        ))

    # Revert shape to input
    if data_bin.shape[1] != 1:
        data_bin = data_bin.swapaxes(0, 1)
        uncertainty = uncertainty.swapaxes(0, 1)
    else:
        data_bin = data_bin[:, 0]
        uncertainty = uncertainty[:, 0]

    return data_bin, uncertainty
