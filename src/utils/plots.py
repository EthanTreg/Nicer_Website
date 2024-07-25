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
        x_errors: Optional[List[ndarray]] = None,
        y_uncertainties: Optional[List[ndarray]] = None,
        x_background_list: Optional[List[ndarray]] = None,
        background_list: Optional[List[ndarray]] = None,
        color_data: Optional[ndarray] = None,
        plot_kwargs: Optional[dict] = None,
        layout_kwargs: Optional[dict] = None) -> str:
    """
    Plots data with uncertainties and background if provided.

    Parameters
    ----------
    gti_numbers : Optional[List[int]]
        List of GTI numbers
    x_data_list : Optional[List[ndarray]]
        List of x-axis data
    y_data_list : Optional[List[ndarray]]
        List of y-axis data
    plot_type : str, default = markers
        Plot marker type, can be markers, lines, or lines+markers
    x_errors : Optional[List[ndarray]]
        List of x error bars
    y_uncertainties : Optional[List[ndarray]]
        List of y-axis uncertainties
    x_background_list : Optional[List[ndarray]]
        List of x-axis data for background
    background_list : Optional[List[ndarray]]
        List of y-axis data for background
    color_data : Optional[ndarray]
        Single array of color data for scatter plots
    plot_kwargs : Optional[dict]
        Additional keyword arguments to pass to go.Scatter
    layout_kwargs : Optional[dict]
        Additional keyword arguments to pass to fig.update_layout

    Returns
    -------
    str
        Plot as HTML
    """
    logger: logging.Logger = logging.getLogger(__name__)
    fig: go.Figure = go.Figure()

    plot_kwargs = plot_kwargs or {}
    layout_kwargs = layout_kwargs or {}

    if not gti_numbers:
        gti_numbers = [0]

    # Ensure all data lists have the same length
    data_lists = [x_data_list, y_data_list, x_errors, y_uncertainties, x_background_list, background_list]
    data_lists = [lst if lst is not None else [None] * len(gti_numbers) for lst in data_lists]

    for number, x_data, y_data, x_error, y_uncertainty, x_background, background, color in zip(
            gti_numbers,
            *data_lists,
            qualitative.Plotly * (len(gti_numbers) // len(qualitative.Plotly) + 1),
    ):
        if x_data is None or y_data is None:
            logger.warning(f"Missing data for GTI {number}. Skipping.")
            continue

        trace_kwargs = {
            'x': x_data,
            'y': y_data,
            'mode': plot_type,
            'name': f'GTI{number}',
            'opacity': 0.8,
            'line': {'color': color},
            'legendgroup': number,
        }

        if x_error is not None:
            trace_kwargs['error_x'] = {'type': 'data', 'array': x_error, 'visible': True}
        if y_uncertainty is not None:
            trace_kwargs['error_y'] = {'type': 'data', 'array': y_uncertainty, 'visible': True}

        # For scatter plots with color data
        if color_data is not None and len(x_data_list) == 1:
            trace_kwargs.update({
                'mode': 'markers',
                'marker': {
                    'size': 5,
                    'color': color_data,
                    'colorscale': 'Viridis',
                    'colorbar': {'title': layout_kwargs.get('colorbar_title', 'Time')},
                    'showscale': True
                }
            })

        # Update with any additional plot-specific kwargs
        trace_kwargs.update(plot_kwargs)

        fig.add_trace(go.Scatter(**trace_kwargs))

        # Add background trace if provided
        if x_background is not None and background is not None:
            fig.add_trace(go.Scatter(
                x=x_background,
                y=background,
                mode='lines',
                name=f'GTI{number} BG',
                opacity=0.8,
                line={'color': color},
                legendgroup=number,
            ))

    fig.update_layout(**layout_kwargs)

    return plot(
        fig,
        output_type='div',
        include_plotlyjs=False,
        config={'displaylogo': False},
    )