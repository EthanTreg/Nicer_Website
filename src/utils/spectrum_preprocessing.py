"""
Utilities to normalise and bin spectra
"""
import numpy as np
from numpy import ndarray
from astropy.io import fits
import plotly.graph_objs as go
from plotly.offline import plot


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
    nchan : int
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


def spectrum_data(
        data_path: str,
        background_dir: str = '',
        cut_off: list = None) -> tuple[ndarray, ndarray, ndarray, int]:
    """
    Fetches binned data from spectrum

    Returns the binned x, y spectrum data as a 2D array

    Parameters
    ----------
    data_path : string
        File path to the spectrum
    background_dir : string, default = ''
        Path to the root directory where the background is located
    cut_off : list, default = [0.3, 10]
        Range of accepted data in keV

    Returns
    -------
    (ndarray, ndarray, ndarray, integer)
        Binned energies, binned spectrum data, binned uncertainties & number of detectors
    """
    bins = np.array([[0, 20, 248, 600, 1200, 1494, 1500], [2, 3, 4, 5, 6, 2, 1]], dtype=int)

    if not cut_off:
        cut_off = [0.3, 10]

    # Fetch spectrum & background fits files
    with fits.open(data_path) as file:
        spectrum_info = file[1].header
        spectrum = file[1].data

        if 'FKRSP001' in spectrum_info:
            response = spectrum_info['FKRSP001']
        else:
            response = spectrum_info['RESPFILE']

        detectors = int(response[response.find('_d') + 2:response.find('_d') + 4])

    try:
        with fits.open(background_dir + spectrum_info['BACKFILE']) as file:
            background_info = file[1].header
            background = file[1].data
    except FileNotFoundError:
        spectrum_info['BACKFILE'] = spectrum_info['BACKFILE'].replace(
            'spectra/synth_',
            'spectra/synth_0'
        )

        with fits.open(background_dir + spectrum_info['BACKFILE']) as file:
            background_info = file[1].header
            background = file[1].data


    # Pre binned data
    x_data = channel_kev(spectrum['CHANNEL'])
    if 'COUNTS' in spectrum.dtype.names and 'COUNTS' in background.dtype.names:
        y_data = (
                 spectrum['COUNTS'] /
                 spectrum_info['EXPOSURE'] - background['COUNTS'] /
                 background_info['EXPOSURE']
                 ) / detectors

        counts_bin = binning(x_data, spectrum['COUNTS'], bins)[1]
    elif 'COUNTS' in spectrum.dtype.names:
        y_data = (
                 spectrum['COUNTS'] /
                 spectrum_info['EXPOSURE'] - background['RATE']
         ) / detectors

        counts_bin = binning(x_data, spectrum['COUNTS'], bins)[1]
    else:
        y_data = (spectrum['RATE'] - background['RATE']) / detectors

        counts_bin = binning(
            x_data,
            (spectrum['RATE'] * spectrum_info['EXPOSURE']),
            bins
        )[1]

    # Bin data
    x_bin, y_bin, energy_bin = binning(x_data, y_data, bins)
    uncertainty = np.sqrt(np.maximum(counts_bin, 1)) / (spectrum_info['EXPOSURE'] * detectors)

    # Energy normalization
    y_bin /= energy_bin
    uncertainty /= energy_bin

    # Energy range cut-off
    cut_indices = np.argwhere((x_bin < cut_off[0]) | (x_bin > cut_off[1]))
    x_bin = np.delete(x_bin, cut_indices)
    y_bin = np.delete(y_bin, cut_indices)
    uncertainty = np.delete(uncertainty, cut_indices)

    return x_bin, y_bin, uncertainty, detectors


def spectrum_plot(
        name: str,
        data_path: str,
        background_dir: str = '',
        cut_off: list = None) -> str:
    """
    Gets and plots the binned and corrected spectrum data

    Parameters
    ----------
    name : string
        Spectrum name
    data_path : string
        File path to the spectrum
    background_dir : string, default = ''
        Path to the root directory where the background is located
    cut_off : list, default = [0.3, 10]
        Range of accepted data in keV

    Returns
    -------
    string
        Spectrum plot as HTML
    """
    # Get spectrum data
    x_data, y_data, y_uncertainties, *_ = spectrum_data(
        data_path,
        background_dir=background_dir,
        cut_off=cut_off,
    )
    
    # Plot spectrum
    spectrum = go.Scatter(
        x=x_data,
        y=y_data,
        error_y={
        'type': 'data',
        'array': y_uncertainties,
        'visible': True,
        },
        mode='markers',
        name='spectrum',
        opacity=0.8,
        marker_color='blue',
    )

    # Plot information
    return plot(
        {'data': [spectrum], 'layout': go.Layout(
            title=f'{name} Spectrum',
            xaxis_title=r'$\text{Energy}\ (keV)$',
            yaxis_title=r'$\text{Photons}\ (keV^{-1} s^{-1} det^{-1})$',
        )},
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )
