"""
Functions to plot graphs
"""
import logging
from typing import Any

import numpy as np
import plotly.graph_objs as go
from numpy import ndarray

from plotly.colors import qualitative


# Minimum value for log scale plotting to prevent extreme drops
LOG_SCALE_MIN_VALUE = 1e-10


def clip_for_log_scale(data: ndarray, min_value: float = LOG_SCALE_MIN_VALUE) -> ndarray:
    """
    Clips data values to a minimum threshold for safe log scale plotting.
    Prevents values like 0 or near-zero from causing extreme drops on log scale.

    Parameters
    ----------
    data : ndarray
        Array of values to clip
    min_value : float, default = 1e-10
        Minimum value threshold

    Returns
    -------
    ndarray
        Array with values clipped to minimum threshold
    """
    if data is None:
        return None
    data = np.asarray(data, dtype=float)
    # Replace zeros, negative values, and non-finite values with min_value
    clipped = np.where((data <= 0) | ~np.isfinite(data), min_value, data)
    # Also clip very small positive values
    clipped = np.maximum(clipped, min_value)
    return clipped


def handle_log_scale_uncertainties(
        y_data: ndarray,
        y_uncertainty: ndarray,
        min_value: float = LOG_SCALE_MIN_VALUE
) -> tuple[ndarray, ndarray, ndarray, ndarray, ndarray, ndarray]:
    """
    Handle uncertainties for log scale plots, classifying each point into one
    of three categories:

    1. **Upper limit** (``net_negative``):  The background-subtracted value is
       non-positive (``y ≤ 0``).  These points cannot be placed on a log axis,
       so we show a downward arrow at the 1σ upper bound ``y + σ``.

    2. **Unconstrained lower bound** (``unconstrained_low``):  The data point
       is positive, but its lower 1σ error bar reaches zero or below
       (``y − σ ≤ 0`` while ``y > 0``).  We keep the data point and its upper
       error bar, but replace the lower error bar with a short downward-arrow
       marker to indicate the lower bound is unconstrained.

    3. **Normal detection**: Both the value and its 1σ bounds are positive.
       Standard symmetric error bars are shown.

    Points whose upper bound is also non-positive (``y + σ ≤ 0``) are entirely
    invalid on a log axis and are removed.

    Parameters
    ----------
    y_data : ndarray
        Y-axis measured values (background-subtracted net rates).
    y_uncertainty : ndarray
        Y-axis 1σ uncertainties (symmetric).
    min_value : float, default = 1e-10
        Minimum value for log scale.

    Returns
    -------
    tuple of six ndarrays
        valid_mask               – True for every point that should be displayed.
        upper_limit_mask         – True for net-negative upper-limit points.
        unconstrained_low_mask   – True for positive points whose lower error
                                   bar is unconstrained.
        y_error_plus             – Upper error bars (zero for upper-limit points).
        y_error_minus            – Lower error bars (zero for ULs; clipped for
                                   unconstrained-low so bar stops at min_value).
        upper_limit_y_values     – Y-values for upper-limit arrows (y + σ).
    """
    y_data = np.asarray(y_data, dtype=float)
    y_uncertainty = np.asarray(y_uncertainty, dtype=float)

    # 1σ bounds
    y_lower = y_data - y_uncertainty
    y_upper = y_data + y_uncertainty

    # Completely invalid: even the upper bound is non-positive
    invalid_mask = (y_upper <= 0) | ~np.isfinite(y_data) | ~np.isfinite(y_uncertainty)
    valid_mask = ~invalid_mask

    # --- Category 1: Upper limit  (net value ≤ 0) --------------------------
    upper_limit_mask = (y_data <= 0) & valid_mask

    # --- Category 2: Unconstrained lower bound  (y > 0, y − σ ≤ 0) ---------
    unconstrained_low_mask = (y_data > 0) & (y_lower <= 0) & valid_mask

    # --- Error bars ---------------------------------------------------------
    y_error_plus = y_uncertainty.copy()
    y_error_minus = y_uncertainty.copy()

    # Upper-limit points: no error bars (drawn as arrows instead)
    if np.any(upper_limit_mask):
        y_error_plus[upper_limit_mask] = 0
        y_error_minus[upper_limit_mask] = 0

    # Unconstrained-low points: keep upper bar; clip lower bar so it stops
    # just above the log-scale minimum (the visual "line + arrow" marker is
    # added separately in data_plot).
    if np.any(unconstrained_low_mask):
        # Lower error bar = distance from y down to min_value (the axis floor)
        y_error_minus[unconstrained_low_mask] = np.maximum(
            y_data[unconstrained_low_mask] - min_value, 0
        )

    # Arrow placement for upper limits: 1σ upper bound
    upper_limit_y_values = np.where(upper_limit_mask, y_upper, y_data)

    return (valid_mask, upper_limit_mask, unconstrained_low_mask,
            y_error_plus, y_error_minus, upper_limit_y_values)


def data_plot(
        plot_type: str = 'markers',
        gti_numbers: list[int] | None = None,
        gti_labels: list[str] | None = None,
        colors: list[str] | None = None,
        x_errors: list[ndarray] | None = None,
        x_data_list: list[ndarray] | None = None,
        y_data_list: list[ndarray] | None = None,
        y_uncertainties: list[ndarray] | None = None,
        background_list: list[ndarray] | None = None,
        x_background_list: list[ndarray] | None = None,
        plot_kwargs: dict[str, Any] | None = None,
        layout_kwargs: dict[str, Any] | None = None,
        subplot_kwargs: dict[str, Any] | None = None,
        color_data: ndarray | None = None,
        fig: go.Figure | None = None) -> str:
    """
    Plots data with uncertainties and background if provided.

    Parameters
    ----------
    plot_type : str, default = markers
        Plot marker type, can be markers, lines, or lines+markers
    gti_numbers : list[int] | None, default = None
        List of GTI numbers
    gti_labels : list[str] | None, default = None
        List of labels for each GTI, if None GTI numbers will be used as labels
    colors : list[str] | None, default = None
        List of colours for each GTI, if None uses qualitative.Plotly
    x_errors : list[ndarray] | None, default = None
        List of x error bars
    x_data_list : list[ndarray] | None, default = None
        List of x-axis data
    y_data_list : list[ndarray] | None, default = None
        List of y-axis data
    y_uncertainties : list[ndarray] | None, default = None
        List of y-axis uncertainties
    background_list : list[ndarray] | None, default = None
        List of y-axis data for background
    x_background_list : list[ndarray] | None, default = None
        List of x-axis data for background
    plot_kwargs : dict[str, Any] | None, default = None
        Additional keyword arguments to pass to go.Scatter
    layout_kwargs : dict[str, Any] | None, default = None
        Additional keyword arguments to pass to fig.update_layout
    subplot_kwargs : dict[str, Any] | None, default = None
        Additional keyword arguments to pass to fig.add_trace
    color_data : ndarray | None, default = None
        Single array of color data for scatter plots
    fig : go.Figure | None, default = None
        Existing figure to add traces to, if None a new figure will be created

    Returns
    -------
    str
        Plot as JSON string
    """
    trace_kwargs: dict[str, Any]
    logger: logging.Logger = logging.getLogger(__name__)
    plot_kwargs = plot_kwargs or {}
    layout_kwargs = layout_kwargs or {}
    fig = fig or go.Figure()

    # Extract bg_dash early so it doesn't leak into go.Scatter kwargs
    bg_dash = plot_kwargs.pop('bg_dash', 'solid')

    if not gti_numbers:
        gti_numbers = [0]

    # Check if y-axis is using log scale
    y_axis_type = layout_kwargs.get('yaxis', {}).get('type', 'linear')
    is_log_scale = y_axis_type == 'log'

    # Also check yaxis_type directly (some code may pass it this way)
    if 'yaxis_type' in layout_kwargs and layout_kwargs['yaxis_type'] == 'log':
        is_log_scale = True

    # Ensure all data lists have the same length
    data_lists = [
        x_data_list,
        y_data_list,
        x_errors,
        y_uncertainties,
        x_background_list,
        background_list,
    ]
    data_lists = [lst if lst is not None else [None] * len(gti_numbers) for lst in data_lists]

    if gti_labels is None:
        gti_labels = [f'GTI{number}' for number in gti_numbers]

    for (
        label,
        number,
        x_data,
        y_data,
        x_error,
        y_uncertainty,
        x_background,
        background,
        color,
    ) in zip(
        gti_labels,
        gti_numbers,
        *data_lists,
        colors or qualitative.Plotly * (len(gti_numbers) // len(qualitative.Plotly) + 1),
    ):
        if x_data is None or y_data is None:
            logger.warning(f"Missing data for GTI {number}. Skipping.")
            continue

        # Convert to numpy arrays
        x_data = np.asarray(x_data)
        y_data = np.asarray(y_data)

        # Handle log scale special cases
        upper_limit_mask = None
        unconstrained_low_mask = None
        upper_limit_y_values = None
        y_error_plus = None
        y_error_minus = None

        if is_log_scale:
            if y_uncertainty is not None:
                y_uncertainty = np.asarray(y_uncertainty)
                (
                    valid_mask,
                    upper_limit_mask,
                    unconstrained_low_mask,
                    y_error_plus,
                    y_error_minus,
                    upper_limit_y_values,
                ) = handle_log_scale_uncertainties(y_data, y_uncertainty)

                # Filter out invalid points
                if not np.all(valid_mask):
                    logger.info(f"GTI {number}: Removing {np.sum(~valid_mask)} invalid points for log scale")
                    x_data = x_data[valid_mask]
                    y_data = y_data[valid_mask]
                    y_error_plus = y_error_plus[valid_mask]
                    y_error_minus = y_error_minus[valid_mask]
                    upper_limit_mask = upper_limit_mask[valid_mask]
                    unconstrained_low_mask = unconstrained_low_mask[valid_mask]
                    upper_limit_y_values = upper_limit_y_values[valid_mask]
                    if x_error is not None:
                        x_error = np.asarray(x_error)[valid_mask]

                # Log upper limits info
                if np.any(upper_limit_mask):
                    logger.info(f"GTI {number}: {np.sum(upper_limit_mask)} points are upper limits (down arrows)")
                if np.any(unconstrained_low_mask):
                    logger.info(f"GTI {number}: {np.sum(unconstrained_low_mask)} points have unconstrained lower bounds")

            # Clip y_data for log scale
            y_data = clip_for_log_scale(y_data)
            if upper_limit_y_values is not None:
                upper_limit_y_values = clip_for_log_scale(upper_limit_y_values)
            if background is not None:
                background = clip_for_log_scale(np.asarray(background))

        # ---- Separate detections, upper limits, and unconstrained-low ----
        has_upper_limits = (
            upper_limit_mask is not None and np.any(upper_limit_mask)
        )
        has_unconstrained_low = (
            unconstrained_low_mask is not None and np.any(unconstrained_low_mask)
        )

        if has_upper_limits:
            # "detection" = everything that is NOT an upper limit (includes
            # unconstrained-low points – they are still plotted as data points)
            det = ~upper_limit_mask
            ul  = upper_limit_mask

            det_x       = x_data[det]
            det_y       = y_data[det]
            det_x_err   = x_error[det] if x_error is not None else None
            det_y_err_p = y_error_plus[det]
            det_y_err_m = y_error_minus[det]

            ul_x       = x_data[ul]
            ul_y       = upper_limit_y_values[ul]
            ul_x_err   = x_error[ul] if x_error is not None else None
        else:
            det_x       = x_data
            det_y       = y_data
            det_x_err   = x_error
            det_y_err_p = y_error_plus
            det_y_err_m = y_error_minus

        # Build trace kwargs (detections + unconstrained-low; ULs are separate)
        trace_kwargs = {
            'x': det_x,
            'y': det_y,
            'mode': plot_type,
            'name': label,
            'opacity': 1.0,
            'line': {'color': color},
            'marker': {'color': color, 'opacity': 1.0},
            'legendgroup': number,
        }

        if det_x_err is not None:
            trace_kwargs['error_x'] = {'type': 'data', 'array': det_x_err, 'visible': True}

        # Handle y uncertainties for detection points
        if y_uncertainty is not None:
            if is_log_scale and det_y_err_p is not None and det_y_err_m is not None:
                trace_kwargs['error_y'] = {
                    'type': 'data',
                    'array': det_y_err_p,
                    'arrayminus': det_y_err_m,
                    'visible': True
                }
            else:
                y_uncertainty = np.asarray(y_uncertainty, dtype=float)
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
                    'showscale': True,
                    'opacity': 1.0
                }
            })

        trace_kwargs.update(plot_kwargs)
        fig.add_trace(go.Scatter(**trace_kwargs), **subplot_kwargs or {})

        # ---- Upper-limit arrows (net-negative: down arrow at y + σ) --------
        if has_upper_limits:
            ul_trace_kwargs = {
                'x': ul_x,
                'y': ul_y,
                'mode': 'markers',
                'name': f'{label} (upper limits)',
                'marker': {
                    'symbol': 'arrow-down',
                    'size': 12,
                    'color': color,
                    'line': {'width': 1, 'color': 'black'},
                    'standoff': 0,
                },
                'legendgroup': number,
                'showlegend': False,
            }
            if ul_x_err is not None:
                ul_trace_kwargs['error_x'] = {
                    'type': 'data', 'array': ul_x_err, 'visible': True
                }
            fig.add_trace(go.Scatter(**ul_trace_kwargs), **subplot_kwargs or {})

        # ---- Unconstrained-low markers (positive point, lower bar → 0) -----
        # Small downward arrow just below the data point to indicate
        # "lower bound is unconstrained".
        if has_unconstrained_low:
            # Subset: only unconstrained-low among the detection indices
            if has_upper_limits:
                # unconstrained_low_mask aligned to original arrays; need to
                # re-index after removing ULs (det mask).
                ucl_in_det = unconstrained_low_mask[~upper_limit_mask]
            else:
                ucl_in_det = unconstrained_low_mask

            ucl_x = det_x[ucl_in_det]
            ucl_y = det_y[ucl_in_det]

            fig.add_trace(go.Scatter(
                x=ucl_x,
                y=ucl_y * 0.7,          # place marker slightly below the point
                mode='markers',
                name=f'{label} (unconstrained low)',
                marker={
                    'symbol': 'arrow-down',
                    'size': 8,
                    'color': color,
                    'line': {'width': 1, 'color': color},
                    'standoff': 0,
                },
                legendgroup=number,
                showlegend=False,
                hovertext='Lower bound unconstrained',
                hoverinfo='text+x+y',
            ), **subplot_kwargs or {})

        # ---- Background trace ----------------------------------------------
        if x_background is not None and background is not None:
            fig.add_trace(go.Scatter(
                x=x_background,
                y=background,
                mode='lines',
                name=f'{label} BG',
                opacity=0.8,
                line={'color': color, 'dash': bg_dash},
                legendgroup=number,
            ), **subplot_kwargs or {})

    fig.update_layout(**layout_kwargs)
    return fig.to_dict()
