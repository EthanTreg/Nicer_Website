"""
Functions to plot graphs
"""
import plotly.graph_objs as go
from numpy import ndarray
from plotly.offline import plot
from plotly.colors import qualitative


def data_plot(
        gti_numbers: list[int],
        x_data_list: list[ndarray],
        y_data_list: list[ndarray],
        kwargs: dict,
        plot_type: str = 'markers',
        x_background_list: list[ndarray] = None,
        background_list: list[ndarray] = None,
        x_error: list[ndarray] = None,
        y_uncertainties: list[ndarray] = None) -> str:
    """
    Plots data with uncertainties if provided

    Parameters
    ----------
    gti_numbers : list[integer]
        List of GTI numbers
    x_data_list : list[ndarray]
        List of x-axis data
    y_data_list : list[ndarray]
        List of y-axis data
    kwargs : dictionary
        Plot layout parameters
    plot_type : string, default = markers
        Plot marker type, can be markers, lines, or lines+markers
    x_background : list[ndarray], default = None
        List of corresponding background energies, if none, x_data_list will be used
    background : list[ndarray], default = None
        List of background data
    x_error : list[ndarray], default = None
        List of x error bars
    y_uncertainties : list[ndarray]
        List of y-axis uncertainties

    Returns
    -------
    string
        Plot as HTML
    """
    fig = go.Figure()

    if not y_uncertainties:
        y_uncertainties = [None] * len(x_data_list)

    if not x_background_list:
        x_background_list = x_data_list

    if not background_list:
        background_list = [None] * len(x_data_list)

    # Plot each GTI
    for number, x_data, y_data, x_background, background, x_error, y_uncertainty, color in zip(
        gti_numbers,
        x_data_list,
        y_data_list,
        x_background_list,
        background_list,
        x_error,
        y_uncertainties,
        qualitative.Plotly,
    ):
        if x_error is not None:
            x_error = {
                'type': 'data',
                'array': x_error,
                'visible': True,
            }

        if y_uncertainty is not None:
            y_uncertainty = {
                'type': 'data',
                'array': y_uncertainty,
                'visible': True,
            }

        # Plot GTI data
        fig.add_trace(go.Scatter(
            x=x_data,
            y=y_data,
            error_x=x_error,
            error_y=y_uncertainty,
            mode=plot_type,
            name=f'GTI{number}',
            opacity=0.8,
            line={'color': color},
            legendgroup=number,
        ))

        # Plot background if provided
        if background is not None:
            fig.add_trace(go.Scatter(
                x=x_background,
                y=background,
                mode='lines',
                name=f'GTI{number} BG',
                opacity=0.8,
                line={'color': color},
                legendgroup=number,
            ))

    # fig.update_layout(legend={'groupclick': 'toggleitem'}, **kwargs)
    fig.update_layout(**kwargs)

    return plot(
        fig,
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )
