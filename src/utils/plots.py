"""
Functions to plot graphs
"""
from typing import Any

import plotly.graph_objs as go
from numpy import ndarray
from plotly.offline import plot
from plotly.colors import qualitative
import logging

logger = logging.getLogger(__name__)


def data_plot(
        gti_numbers: list[int],
        x_data_list: list[ndarray],
        y_data_list: list[ndarray],
        plot_type: str = 'markers',
        x_background_list: list[ndarray] | None = None,
        background_list: list[ndarray] | None = None,
        x_errors: list[ndarray] | None = None,
        y_uncertainties: list[ndarray] | None = None,
        **kwargs: Any) -> str:
    """
    Plots data with uncertainties if provided

    Parameters
    ----------
    gti_numbers : list[int]
        List of GTI numbers
    x_data_list : list[ndarray]
        List of x-axis data
    y_data_list : list[ndarray]
        List of y-axis data
    plot_type : str, default = markers
        Plot marker type, can be markers, lines, or lines+markers
    x_background_list : list[ndarray], default = None
        List of corresponding background energies, if none, x_data_list will be used
    background_list : list[ndarray], default = None
        List of background data
    x_errors : list[ndarray], default = None
        List of x error bars
    y_uncertainties : list[ndarray]
        List of y-axis uncertainties

    **kwargs
        Parameters to pass to Plotly layout

    Returns
    -------
    str
        Plot as HTML
    """
    try:
        if not all(
                len(lst) == len(gti_numbers) for lst in [x_data_list, y_data_list, y_uncertainties] if lst is not None):
            raise ValueError("All input lists must have the same length as gti_numbers")

        # Handle None values
        if x_errors is None:
            x_errors = [None] * len(gti_numbers)
        if x_background_list is None:
            x_background_list = x_data_list
        if background_list is None:
            background_list = [None] * len(gti_numbers)
        if y_uncertainties is None:
            y_uncertainties = [None] * len(gti_numbers)
        number: int
        color: str
        x_error: dict[str, bool | str | ndarray] | ndarray
        y_uncertainty: dict[str, bool | str | ndarray] | ndarray
        x_data: ndarray
        y_data: ndarray
        x_background: ndarray
        fig: go.Figure = go.Figure()

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
            x_errors,
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
    except Exception as e:
        logger.error(f"Error in data_plot: {str(e)}")
        logger.error(f"gti_numbers: {gti_numbers}")
        logger.error(f"x_data_list: {type(x_data_list)}, length: {len(x_data_list)}")
        logger.error(f"y_data_list: {type(y_data_list)}, length: {len(y_data_list)}")
        logger.error(f"y_uncertainties: {type(y_uncertainties)}, length: {len(y_uncertainties)}")
        return f"Error in data_plot: {str(e)}"