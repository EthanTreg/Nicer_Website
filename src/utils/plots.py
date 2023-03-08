"""
Functions to plot graphs
"""
import plotly.graph_objs as go
from numpy import ndarray
from plotly.offline import plot


def data_plot(
        title: str,
        x_axis: str,
        y_axis: str,
        x_data: ndarray,
        y_data: ndarray,
        y_uncertainties: ndarray = None) -> str:
    """
    Plots data with uncertainties if provided

    Parameters
    ----------
    title : string
        Title of the plot
    x_axis : string
        x-axis label
    y_axis : string
        y-axis label
    x_data : ndarray
        x-axis data
    y_data : ndarray
        y-axis data
    y_uncertainties : ndarray
        y-axis uncertainty

    Returns
    -------
    string
        Plot as HTML
    """
    if y_uncertainties is None:
        y_uncertainties = None
    else:
        y_uncertainties = {
            'type': 'data',
            'array': y_uncertainties,
            'visible': True,
        }

    # Plot data
    plot_data = go.Scatter(
        x=x_data,
        y=y_data,
        error_y=y_uncertainties,
        mode='markers',
        name='spectrum',
        opacity=0.8,
        marker_color='blue',
    )

    return plot(
        {'data': [plot_data], 'layout': go.Layout(
            title=title,
            xaxis_title=x_axis,
            yaxis_title=y_axis,
        )},
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )
