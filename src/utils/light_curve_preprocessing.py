"""
Utility to correct light curve data
"""
from typing import Any

import numpy as np
from numpy import ndarray
from plotly.colors import qualitative
from plotly.subplots import make_subplots

from src.utils.utils import min_bin, binning
from src.utils.plots import data_plot


def light_curve_data(
        min_value: int,
        data_path: str) -> tuple[
            ndarray[tuple[int], np.dtype[np.float_]],
            ndarray[tuple[int], np.dtype[np.float_]],
            ndarray[tuple[int], np.dtype[np.float_]],
            ndarray[tuple[int], np.dtype[np.float_]],
            ndarray[tuple[int], np.dtype[np.float_]],
            ndarray[tuple[int], np.dtype[np.float_]]]:
    """
    Fetches and corrects binned light curve data

    Parameters
    ----------
    min_value : int
        Minimum value used for binning
    data_path : str
        Path to the light curve

    Returns
    -------
    tuple[ndarray, ndarray, ndarray, ndarray, ndarray, ndarray]
        Binned relative time, light curve, background time, background, x width, and uncertainty
    """
    detectors: int | ndarray
    time_diff: float
    min_bins: ndarray[tuple[int], np.dtype[np.int_]]
    x_bin: ndarray[tuple[int], np.dtype[np.float_]]
    y_bin: ndarray[tuple[int], np.dtype[np.float_]]
    bg_bin: ndarray[tuple[int], np.dtype[np.float_]]
    counts: ndarray[tuple[int], np.dtype[np.float_]]
    x_width: ndarray[tuple[int], np.dtype[np.float_]]
    x_error: ndarray[tuple[int], np.dtype[np.float_]]
    bg_x_bin: ndarray[tuple[int], np.dtype[np.float_]]
    background: ndarray[tuple[int], np.dtype[np.float_]]
    data: ndarray[tuple[int, int], np.dtype[np.float_]]
    uncertainty: ndarray[tuple[int, int], np.dtype[np.float_]]

    time, counts, detectors = np.loadtxt(data_path, usecols=[0, 2, 3], unpack=True)
    background = np.loadtxt(data_path.replace('.lc.gz', '.bg-lc.gz'), usecols=2)

    # Constants
    detectors = detectors[0]
    time_diff = float(time[1] - time[0])
    counts *= time_diff

    # Bin data
    # Treat min_value as binning factor (combine N bins)
    bin_factor = int(min_value) if min_value > 0 else 1
    min_bins = np.arange(0, len(counts), bin_factor)
    if min_bins[-1] != len(counts):
        min_bins = np.append(min_bins, len(counts))
    min_bins = np.unique(min_bins)

    (y_bin, bg_bin, x_bin), x_width, uncertainty = binning(
        min_bins,
        np.stack((counts[:len(background)], background[:len(time)], time[:len(background)])),
    )

    # Normalise data
    y_bin = (y_bin - bg_bin) / (detectors * time_diff)
    bg_bin /= detectors
    bg_bin = np.insert(bg_bin, [0, -1], [bg_bin[0], bg_bin[-1]])
    x_error = x_width * time_diff / 2
    uncertainty /= detectors * time_diff
    bg_x_bin = x_bin.copy()
    bg_x_bin = np.insert(
        bg_x_bin,
        [0, bg_x_bin.size],
        [x_bin[0] - x_error[0], x_bin[-1] + x_error[-1]],
    )

    return x_bin, y_bin, bg_x_bin, bg_bin, x_error, uncertainty[0]

def align_light_curves(
        min_value: int,
        data_paths: list[str],
        gti_numbers: list[int],
) -> tuple[
    list[ndarray[tuple[int], np.dtype[np.float_]]],
    list[ndarray[tuple[int], np.dtype[np.float_]]],
    list[ndarray[tuple[int], np.dtype[np.float_]]],
    list[ndarray[tuple[int], np.dtype[np.float_]]],
    list[ndarray[tuple[int], np.dtype[np.float_]]],
    list[ndarray[tuple[int], np.dtype[np.float_]]]]:
    """
    Aligns multiple light curves by ensuring correct GTI interval separation and grouping by GTI
    number

    Parameters
    ----------
    min_value : int
        Minimum value used for binning
    data_paths : list[str]
        List of paths to light curve data files
    gti_numbers : list[int]
        List of GTI numbers

    Returns
    -------
    Tuple of aligned data lists, grouped by GTI number
    """
    i: int
    gti_num: int
    max_duration: float
    data_path: str
    group: list[dict[str, ndarray[tuple[int], np.dtype[np.float_]]]]
    aligned_group: list[dict[str, ndarray[tuple[int], np.dtype[np.float_]]]]
    x_data: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    y_data: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    x_errors: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    background: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    x_background: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    uncertainties: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    data: tuple[ndarray[tuple[int], np.dtype[np.float_]], ...]
    gti_groups: dict[int, list[dict[str, ndarray[tuple[int], np.dtype[np.float_]]]]] = {}
    aligned_gti_groups: dict[int, list[dict[str, ndarray[tuple[int], np.dtype[np.float_]]]]] = {}
    group_data: dict[str, ndarray[tuple[int], np.dtype[np.float_]]]
    aligned_group_data: dict[str, ndarray[tuple[int], np.dtype[np.float_]]]

    for data_path, gti_num in zip(data_paths, gti_numbers):
        data = light_curve_data(min_value, data_path)

        if gti_num not in gti_groups:
            gti_groups[gti_num] = []

        gti_groups[gti_num].append(dict(zip(
            ['x_bin', 'y_bin', 'bg_x_bin', 'bg_bin', 'x_err', 'uncertainty'],
            data
        )))

    for gti_num, group in gti_groups.items():
        aligned_group = []
        max_duration = max(data['x_bin'][-1] - data['x_bin'][0] for data in group)

        for i, group_data in enumerate(group):
            orig_x_bin = group_data['x_bin']
            orig_duration = orig_x_bin[-1] - orig_x_bin[0]
            scale_factor = max_duration / orig_duration
            total_offset = i * (max_duration + 5400)

            scaled_x_bin = ((orig_x_bin - orig_x_bin[0]) * scale_factor) + total_offset
            scaled_bg_x_bin = (
                (group_data['bg_x_bin'] - group_data['bg_x_bin'][0]) * scale_factor
            ) + total_offset

            aligned_group.append({
                'x_bin': scaled_x_bin,
                'y_bin': group_data['y_bin'],
                'bg_x_bin': scaled_bg_x_bin,
                'bg_bin': group_data['bg_bin'],
                'x_err': group_data['x_err'] * scale_factor,
                'uncertainty': group_data['uncertainty']
            })

        aligned_gti_groups[gti_num] = aligned_group

    for gti_num in sorted(aligned_gti_groups.keys()):
        for aligned_group_data in aligned_gti_groups[gti_num]:
            x_data.append(aligned_group_data['x_bin'])
            y_data.append(aligned_group_data['y_bin'])
            x_background.append(aligned_group_data['bg_x_bin'])
            background.append(aligned_group_data['bg_bin'])
            x_errors.append(aligned_group_data['x_err'])
            uncertainties.append(aligned_group_data['uncertainty'])

    return x_data, y_data, x_background, background, x_errors, uncertainties

def light_curve_plot(
    min_value: int,
    obs_id: int,
    data_paths: list[str],
    gti_numbers: list[int],
    gti_labels: list[str] | None = None,
    is_combined_obs: bool = False) -> str:
    """
    Gets and plots the corrected light curve data

    Parameters
    ----------
    min_value : int
        Minimum value used for binning
    obs_id : int
        Observation ID
    data_paths : list[str]
        File path to the light curve
    gti_numbers : list[int]
        List of GTI numbers
    gti_labels : list[str] | None, default = None
        List of GTI labels
    is_combined_obs : bool
        Flag indicating if this is a combined observation plot

    Returns
    -------
    str
        Light curve plot as HTML
    """
    plot: str = ''
    subplot_kwargs: list[dict[str, Any]] = [{'row': 1, 'col': 1}]
    x_data: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    y_data: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    x_error: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    background: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    x_background: list[ndarray[tuple[int], np.dtype[np.float_]]] = []
    y_uncertainties: list[ndarray[tuple[int], np.dtype[np.float_]]] = []

    if gti_labels is None:
        gti_labels = [f'GTI{gti}' for gti in gti_numbers]

    if is_combined_obs:
        x_data, y_data, x_background, background, x_error, y_uncertainties = align_light_curves(
            min_value,
            data_paths,
            gti_numbers,
        )
    else:
        for data_path in data_paths:
            x_bin, y_bin, bg_x_bin, bg_bin, x_err, uncertainty = light_curve_data(
                min_value,
                data_path,
            )
            x_data.append(x_bin)
            y_data.append(y_bin)
            x_background.append(bg_x_bin)
            background.append(bg_bin)
            x_error.append(x_err)
            y_uncertainties.append(uncertainty)

    idxs = np.argsort([min(datum) for datum in x_data])
    x_data = [x_data[idx] for idx in idxs]
    y_data = [y_data[idx] for idx in idxs]
    x_background = [x_background[idx] for idx in idxs]
    background = [background[idx] for idx in idxs]
    x_error = [x_error[idx] for idx in idxs]
    y_uncertainties = [y_uncertainties[idx] for idx in idxs]

    x_background = [(datum - x_data[0][0]) / 3600 / 24 for datum in x_background]
    x_data = [(datum - x_data[0][0]) / 3600 / 24 for datum in x_data]
    x_error = [datum / 3600 / 24 for datum in x_error]

    for i, x_datum in enumerate(x_data[1:]):
        # x_datum is x_data[i+1]
        
        # Robust bin width detection using x_error (half-width)
        current_x_errors = x_error[i + 1]
        if len(current_x_errors) > 0:
            max_bin_width = 2 * np.max(current_x_errors)
        else:
            # Fallback if errors are empty (unlikely)
            max_bin_width = 0

        if max_bin_width > 0 and x_datum[0] - x_data[i][-1] > 10 * max_bin_width:
            subplot_kwargs.append({'row': 1, 'col': subplot_kwargs[-1]['col'] + 1})
        else:
            subplot_kwargs.append({'row': 1, 'col': subplot_kwargs[-1]['col']})

    fig = make_subplots(
        rows=1,
        cols=subplot_kwargs[-1]['col'],
        shared_yaxes=True,
        horizontal_spacing=0.01,
    )
    fig.add_annotation(
        text=r'$\rm Relative\ Time\ (day)$',
        xref='paper',
        yref='paper',
        x=0.5,
        y=-0.15,
        showarrow=False,
        xanchor='center',
        yanchor='top',
        font=dict(size=14),
    )

    for i, (
        gti_number,
        gti_label,
        color,
        x_datum,
        y_datum,
        x_err,
        y_uncertainty,
        bg_x_datum,
        bg_datum,
        subplot_kw,
    ) in enumerate(zip(
        gti_numbers,
        gti_labels,
        qualitative.Plotly * (len(gti_numbers) // len(qualitative.Plotly) + 1),
        x_data,
        y_data,
        x_error,
        y_uncertainties,
        x_background,
        background,
        subplot_kwargs,
    )):
        plot = data_plot(
            plot_type='lines+markers',
            gti_numbers=[gti_number],
            colors=[color],
            gti_labels=[gti_label],
            x_errors=[x_err],
            x_data_list=[x_datum],
            y_data_list=[y_datum],
            y_uncertainties=[y_uncertainty],
            background_list=[bg_datum],
            x_background_list=[bg_x_datum],
            plot_kwargs={'mode': 'markers'},
            layout_kwargs={
                'title': f'Light Curve {obs_id}',
                'yaxis_title': r'$\text{Photons}\ (s^{-1} {\rm det}^{-1})$',
                'showlegend': i == len(gti_numbers) - 1,
            },
            subplot_kwargs=subplot_kw,
            fig=fig,
        )
    return plot
