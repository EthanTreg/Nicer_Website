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
        gti_numbers: list[int],
        x_data_list: list[ndarray],
        y_data_list: list[ndarray],
        y_uncertainties: list[ndarray] = None) -> str:
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
    gti_numbers : list[integer]
        List of GTI numbers
    x_data_list : list[ndarray]
        List of x-axis data
    y_data_list : list[ndarray]
        List of y-axis data
    y_uncertainties : list[ndarray]
        List of y-axis uncertainty

    Returns
    -------
    string
        Plot as HTML
    """
    plot_data = []

    if not y_uncertainties:
        y_uncertainties = [None] * len(x_data_list)

    # Plot data
    for number, x_data, y_data, y_uncertainty in zip(
        gti_numbers,
        x_data_list,
        y_data_list,
        y_uncertainties
    ):
        if y_uncertainty is not None:
            y_uncertainty = {
                'type': 'data',
                'array': y_uncertainty,
                'visible': True,
            }

        test = go.Scatter(
            x=x_data,
            y=y_data,
            error_y=y_uncertainty,
            mode='markers',
            name=f'GTI{number}',
            opacity=0.8,
        )

        plot_data.append(test)

    return plot(
        {'data': plot_data, 'layout': go.Layout(
            title=title,
            xaxis_title=x_axis,
            yaxis_title=y_axis,
        )},
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )
