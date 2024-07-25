"""
Functions to plot graphs
"""
import logging
from typing import Any, Optional, List

import plotly.graph_objs as go
from numpy import ndarray
from plotly.offline import plot
from plotly.colors import qualitative


def data_plot(
        gti_numbers: Optional[List[int]] = None,
        x_data_list: Optional[List[ndarray]] = None,
        y_data_list: Optional[List[ndarray]] = None,
        plot_type: str = 'markers',
        x_background_list: Optional[List[ndarray]] = None,
        background_list: Optional[List[ndarray]] = None,
        x_errors: Optional[List[ndarray]] = None,
        y_uncertainties: Optional[List[ndarray]] = None,
        x_data: Optional[ndarray] = None,
        y_data: Optional[ndarray] = None,
        color_data: Optional[ndarray] = None,
        **kwargs: Any) -> str:
    """
    Plots data with uncertainties if provided.

    Parameters
    ----------
    gti_numbers : Optional[List[int]]
        List of GTI numbers
    x_data_list : Optional[List[ndarray]]
        List of x-axis data
    y_data_list : Optional[List[ndarray]]
        List of y-axis data (for PDS)
    plot_type : str, default = markers
        Plot marker type, can be markers, lines, or lines+markers
    x_background_list : Optional[List[ndarray]]
        List of corresponding background energies
    background_list : Optional[List[ndarray]]
        List of background data
    x_errors : Optional[List[ndarray]]
        List of x error bars
    y_uncertainties : Optional[List[ndarray]]
        List of y-axis uncertainties
    x_data : Optional[ndarray]
        Single array of x-axis data
    y_data : Optional[ndarray]
        Single array of y-axis data
    color_data : Optional[ndarray]
        Single array of color data

    **kwargs
        Parameters to pass to Plotly layout

    Returns
    -------
    str
        Plot as HTML
    """
    # number: int
    # color: str
    # x_error: dict[str, bool | str | ndarray] | ndarray
    # y_uncertainty: dict[str, bool | str | ndarray] | ndarray
    logger: logging.Logger = logging.getLogger(__name__)
    # x_data: ndarray
    # y_data: ndarray
    # x_background: ndarray
    fig: go.Figure = go.Figure()

    # HID plot
    if x_data is not None and y_data is not None and color_data is not None:
        fig.add_trace(go.Scatter(
            x=x_data,
            y=y_data,
            mode='markers',
            marker=dict(
                size=5,
                color=color_data,
                colorscale='Viridis',
                colorbar=dict(title=kwargs.get('colorbar_title', 'Time')),
                showscale=True
            ),
            name='HID'
        ))

    #rest of the plots
    elif gti_numbers and x_data_list and y_data_list:
        for name, lst in zip(
                ['x data', 'y data', 'y uncertainties'],
                [x_data_list, y_data_list, y_uncertainties],
        ):
            if lst is not None and len(lst) != len(gti_numbers):
                logger.error(f'{name} has {len(lst)} entry(-ies) for {len(gti_numbers)} GTI(s)')
                return ''

        if not x_errors:
            x_errors = [None] * len(x_data_list)

        if not y_uncertainties:
            y_uncertainties = [None] * len(x_data_list)

        if not x_background_list:
            x_background_list = x_data_list

        if not background_list:
            background_list = [None] * len(x_data_list)

        for number, x_data, y_data, x_background, background, x_error, y_uncertainty, color in zip(
                gti_numbers,
                x_data_list,
                y_data_list,
                x_background_list,
                background_list,
                x_errors,
                y_uncertainties,
                qualitative.Plotly,
        ):
            error_x = {'type': 'data', 'array': x_error, 'visible': True} if x_error is not None else None
            error_y = {'type': 'data', 'array': y_uncertainty, 'visible': True} if y_uncertainty is not None else None

            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                error_x=error_x,
                error_y=error_y,
                mode=plot_type,
                name=f'GTI{number}',
                opacity=0.8,
                line={'color': color},
                legendgroup=number,
            ))

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

    else:
        return 'incorrect data passed'

    fig.update_layout(**kwargs)

    return plot(
        fig,
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )