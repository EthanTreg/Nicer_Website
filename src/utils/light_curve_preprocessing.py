"""
Utility to correct light curve data
"""
import numpy as np
import plotly.graph_objs as go
from plotly.offline import plot


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
    # Get spectrum data
    x_data, y_data, y_uncertainties = light_curve_data(data_path)
    
    # Plot spectrum
    light_curve = go.Scatter(
        x=x_data,
        y=y_data,
        error_y={
        'type': 'data',
        'array': y_uncertainties,
        'visible': False,
        },
        mode='markers',
        name='light_curve',
        opacity=0.8,
        marker_color='blue',
    )

    # Plot information
    return plot(
        {'data': [light_curve], 'layout': go.Layout(
            title=f'{name} Light Curve',
            xaxis_title=r'$\text{Relative Time}\ (s)$',
            yaxis_title=r'$\text{Photons}\ (s^{-1} det^{-1})$',
        )},
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )
