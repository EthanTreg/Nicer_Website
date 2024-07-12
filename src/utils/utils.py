"""
Misc functions used elsewhere
"""
import numpy as np
from numpy import ndarray


def min_bin(min_value: int, data: ndarray) -> ndarray:
    """
    Calculates the bin indices to ensure each bin has the minimum number of counts.

    Parameters
    ----------
    min_value : integer
        Minimum value for each bin
    data : ndarray
        Data to measure the bin counts

    Returns
    -------
    ndarray
        Bin indices
    """
    i: int
    bin_counts: int
    count: int = 0
    bins: ndarray = np.array([0])

    for i, bin_counts in enumerate(data[:-1]):
        count += bin_counts

        if count >= min_value:
            bins = np.append(bins, i + 1)
            count = 0

    if data[-1] < min_value:
        bins[-1] = data.size
    else:
        bins = np.append(bins, data.size)

    return bins


def binning(
        bins: ndarray,
        data: ndarray,
        weights: ndarray | None = None) -> tuple[ndarray, ndarray, ndarray]:
    """
    Bin data into bins.

    Parameters
    ----------
    bins : ndarray
        Array of bin edges
    data : ndarray
        Data to bin, can be 2D where the rows correspond to different datasets
        and the first row is used to determine binning
    weights : ndarray, default = None
        Widths of the bins in x-units

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        Binned data, bin widths and Poisson uncertainty
    """
    bin_width: float
    bin_counts: float
    data_bin: ndarray
    uncertainty: ndarray
    bin_widths: ndarray = np.array(())

    # Swaps axes for easier indexing and ensures data is 2D
    if len(data.shape) > 1:
        data = data.swapaxes(0, 1)
    else:
        data = data[:, np.newaxis]

    data_bin = np.empty((0, data.shape[1]))
    uncertainty = np.empty((0, data.shape[1]))

    if weights is None:
        weights = np.ones(data.shape[0])

    data = data * weights[:, np.newaxis]

    # Loop through array except for the last bin, and bins data
    for i, idx in enumerate(bins[:-1]):
        bin_width = np.sum(weights[idx:bins[i + 1]])
        bin_counts = np.sum(data[idx:bins[i + 1]], axis=0)

        bin_widths = np.append(bin_widths, bin_width)
        data_bin = np.vstack((data_bin, bin_counts / bin_width))
        uncertainty = np.vstack((uncertainty, np.sqrt(np.maximum(bin_counts, 1)) / bin_width))

    # Revert shape to input
    if data_bin.shape[1] != 1:
        data_bin = data_bin.swapaxes(0, 1)
        uncertainty = uncertainty.swapaxes(0, 1)
    else:
        data_bin = data_bin[:, 0]
        uncertainty = uncertainty[:, 0]

    return data_bin, bin_widths, uncertainty
