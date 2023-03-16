"""
Misc functions used elsewhere
"""
import numpy as np


def min_bin(
        min_value: int,
        merged_data: np.ndarray,
        binned_data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Ensures each bin has a minimum value.

    Parameters
    ----------
    min_value : integer
        Minimum value for each bin
    merged_data : ndarray
        Data to merge, can be 2D where the rows correspond to different datasets
    binned_data : ndarray
        y data to bin, can be 2D where the rows correspond to different datasets
        and the first row is used to determine binning

    Returns
    -------
    tuple[ndarray, ndarray, ndarray]
        Merged and binned data and uncertainty
    """
    # Constants
    i = 0
    bin_width = 1
    uncertainty = []

    if len(merged_data.shape) > 1:
        merged_data = merged_data.swapaxes(0, 1)

    if len(binned_data.shape) > 1:
        binned_data = binned_data.swapaxes(0, 1)
    else:
        binned_data = binned_data[:, np.newaxis]

    while i < merged_data.shape[0] - 1:
        if binned_data[i, 0] < min_value:
            bin_width += 1
            merged_data[i] = np.mean(merged_data[i:i + 2], axis=0)
            merged_data = np.delete(merged_data, i + 1, axis=0)

            binned_data[i] += binned_data[i + 1]
            binned_data = np.delete(binned_data, i + 1, axis=0)
        else:
            uncertainty.append(np.sqrt(binned_data[i, 0]) / bin_width)
            binned_data[i] /= bin_width
            bin_width = 1
            i += 1


    if binned_data[-1, 0] < min_value:
        bin_width += 1
        merged_data[-2] = np.mean(merged_data[-2:], axis=0)
        merged_data = np.delete(merged_data, -1, axis=0)

        binned_data[-2] += binned_data[-1]
        binned_data = np.delete(binned_data, -1, axis=0)

        uncertainty[-1] = np.sqrt(np.maximum(binned_data[-1, 0], 1)) / bin_width
    else:
        uncertainty.append(np.sqrt(binned_data[-1, 0]) / bin_width)

    binned_data[-1] /= bin_width

    if len(merged_data.shape) > 1:
        merged_data = merged_data.swapaxes(0, 1)

    if binned_data.shape[1] != 1:
        binned_data = binned_data.swapaxes(0, 1)
    else:
        binned_data = binned_data[:, 0]

    return merged_data, binned_data, np.array(uncertainty)
