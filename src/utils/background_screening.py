"""
Utilities for screening GTIs based on background domination.

Implements quality filtering to exclude GTIs where background dominates the source signal.
If between 2-5 keV, any two or more channels are background-dominated, exclude the GTI.
"""
import os
import re
import logging
import glob

import numpy as np
from numpy import ndarray

logger = logging.getLogger(__name__)

# Default screening parameters
DEFAULT_ENERGY_RANGE_LOW = 2.0  # keV
DEFAULT_ENERGY_RANGE_HIGH = 5.0  # keV
DEFAULT_MIN_BAD_CHANNELS = 2  # Number of background-dominated channels to trigger exclusion


def channel_to_kev(channel: ndarray) -> ndarray:
    """
    Convert NICER channel numbers to keV.
    NICER channels are 10 eV wide, starting at 0.

    Parameters
    ----------
    channel : ndarray
        Detector channel numbers

    Returns
    -------
    ndarray
        Energy in keV (channel center)
    """
    # NICER: 1 channel = 10 eV = 0.01 keV
    # Channel 0 = 0-10 eV, center = 5 eV = 0.005 keV
    return (channel * 0.01) + 0.005


def find_background_file(spectrum_path: str) -> str | None:
    """
    Find the corresponding background file for a spectrum file.

    NICER background files can have various naming conventions:
    - .bg (simple)
    - .bg.pha
    - _bkg.pha
    - .bkg

    Parameters
    ----------
    spectrum_path : str
        Path to the spectrum file

    Returns
    -------
    str | None
        Path to background file if found, None otherwise
    """
    base_path = spectrum_path.rsplit('.', 1)[0]  # Remove extension

    # Try various background file patterns
    bg_patterns = [
        f"{base_path}.bg",
        f"{base_path}.bg.pha",
        f"{base_path}_bkg.pha",
        f"{base_path}.bkg",
        spectrum_path.replace('.jsgrp', '.bg'),
        spectrum_path.replace('.jsgrp', '.bg.pha'),
        spectrum_path.replace('.pha', '.bg'),
    ]

    # Also try looking for any .bg file in the same directory with same GTI
    dir_path = os.path.dirname(spectrum_path)
    filename = os.path.basename(spectrum_path)

    # Extract GTI number from filename
    gti_match = re.search(r'GTI(\d+)', filename)
    if gti_match:
        gti_num = gti_match.group(0)
        # Look for any background file with this GTI
        bg_glob_patterns = [
            os.path.join(dir_path, f"*{gti_num}*.bg"),
            os.path.join(dir_path, f"*{gti_num}*.bg.pha"),
            os.path.join(dir_path, f"*{gti_num}*_bkg*"),
        ]
        for pattern in bg_glob_patterns:
            matches = glob.glob(pattern)
            if matches:
                bg_patterns.extend(matches)

    for bg_path in bg_patterns:
        if os.path.exists(bg_path):
            logger.debug(f"Found background file: {bg_path}")
            return bg_path

    return None


def check_background_domination(
        spectrum_path: str,
        energy_low: float = DEFAULT_ENERGY_RANGE_LOW,
        energy_high: float = DEFAULT_ENERGY_RANGE_HIGH,
        min_bad_channels: int = DEFAULT_MIN_BAD_CHANNELS
) -> tuple[bool, dict]:
    """
    Check if a GTI is background-dominated in the specified energy range.

    A GTI is considered background-dominated if the background exceeds the source
    in `min_bad_channels` or more channels within the energy range.

    Parameters
    ----------
    spectrum_path : str
        Path to the spectrum file (.jsgrp or .pha)
    energy_low : float, default = 2.0
        Lower bound of energy range in keV
    energy_high : float, default = 5.0
        Upper bound of energy range in keV
    min_bad_channels : int, default = 2
        Minimum number of background-dominated channels to fail screening

    Returns
    -------
    Tuple[bool, dict]
        - passes_screening: True if GTI passes (is NOT background-dominated)
        - info: Dictionary with screening details
    """
    from astropy.io import fits

    info = {
        'spectrum_path': spectrum_path,
        'energy_range': (energy_low, energy_high),
        'min_bad_channels': min_bad_channels,
        'bad_channel_count': 0,
        'total_channels_in_range': 0,
        'reason': None,
        'passes': True,
        'bg_file_found': False,
    }

    try:
        # Check if spectrum file exists
        if not os.path.exists(spectrum_path):
            info['reason'] = f"Spectrum file not found: {spectrum_path}"
            info['passes'] = True  # Can't screen, so pass by default
            logger.warning(info['reason'])
            return True, info

        # Load spectrum file
        logger.info(f"[Screening] Loading spectrum: {spectrum_path}")
        with fits.open(spectrum_path) as hdul:
            # Try to find the spectrum extension
            spectrum_ext = None
            for ext_name in ['SPECTRUM', 'SPEC', 1]:
                try:
                    if isinstance(ext_name, int):
                        spectrum_ext = hdul[ext_name]
                    elif ext_name in hdul:
                        spectrum_ext = hdul[ext_name]
                    if spectrum_ext is not None and hasattr(spectrum_ext, 'data'):
                        break
                except (KeyError, IndexError):
                    continue

            if spectrum_ext is None or spectrum_ext.data is None:
                info['reason'] = "Could not find spectrum data in file"
                info['passes'] = True
                logger.warning(info['reason'])
                return True, info

            spectrum_data = spectrum_ext.data
            spectrum_header = spectrum_ext.header

            # Get channel and counts
            if 'CHANNEL' in spectrum_data.names:
                channels = spectrum_data['CHANNEL']
            else:
                # Generate channel numbers
                channels = np.arange(len(spectrum_data))

            if 'COUNTS' in spectrum_data.names:
                source_counts = spectrum_data['COUNTS'].astype(float)
            elif 'RATE' in spectrum_data.names:
                exposure = spectrum_header.get('EXPOSURE', 1.0)
                source_counts = spectrum_data['RATE'].astype(float) * exposure
            else:
                info['reason'] = "Could not find COUNTS or RATE in spectrum"
                info['passes'] = True
                logger.warning(info['reason'])
                return True, info

            exposure = spectrum_header.get('EXPOSURE', 1.0)

        # Find background file
        bg_path = find_background_file(spectrum_path)

        if bg_path is None:
            info['reason'] = f"No background file found for {os.path.basename(spectrum_path)}"
            info['passes'] = True  # Can't determine, so pass
            logger.info(f"[Screening] {info['reason']} - GTI passes by default")
            return True, info

        info['bg_file_found'] = True
        info['bg_path'] = bg_path
        logger.info(f"[Screening] Found background file: {bg_path}")

        # Load background file
        with fits.open(bg_path) as hdul:
            bg_ext = None
            for ext_name in ['SPECTRUM', 'SPEC', 1]:
                try:
                    if isinstance(ext_name, int):
                        bg_ext = hdul[ext_name]
                    elif ext_name in hdul:
                        bg_ext = hdul[ext_name]
                    if bg_ext is not None and hasattr(bg_ext, 'data'):
                        break
                except (KeyError, IndexError):
                    continue

            if bg_ext is None or bg_ext.data is None:
                info['reason'] = "Could not find background data in file"
                info['passes'] = True
                logger.warning(info['reason'])
                return True, info

            bg_data = bg_ext.data
            bg_header = bg_ext.header

            if 'COUNTS' in bg_data.names:
                bg_counts = bg_data['COUNTS'].astype(float)
            elif 'RATE' in bg_data.names:
                bg_exposure = bg_header.get('EXPOSURE', 1.0)
                bg_counts = bg_data['RATE'].astype(float) * bg_exposure
            else:
                info['reason'] = "Could not find COUNTS or RATE in background file"
                info['passes'] = True
                logger.warning(info['reason'])
                return True, info

            bg_exposure = bg_header.get('EXPOSURE', exposure)

        # Ensure arrays are same length
        min_len = min(len(source_counts), len(bg_counts), len(channels))
        source_counts = source_counts[:min_len]
        bg_counts = bg_counts[:min_len]
        channels = channels[:min_len]

        # Convert channels to energy
        energies = channel_to_kev(channels)

        # Find channels in the specified energy range
        energy_mask = (energies >= energy_low) & (energies <= energy_high)
        n_channels_in_range = np.sum(energy_mask)

        if n_channels_in_range == 0:
            info['reason'] = f"No channels in energy range {energy_low}-{energy_high} keV"
            info['passes'] = True
            logger.warning(info['reason'])
            return True, info

        info['total_channels_in_range'] = int(n_channels_in_range)

        # Normalize to count rates
        source_rate = source_counts[energy_mask] / exposure
        bg_rate = bg_counts[energy_mask] / bg_exposure

        # Check for background domination (background >= source)
        # Net source = source - background, so if bg >= source, net <= 0
        bg_dominated = bg_rate >= source_rate
        bad_channel_count = np.sum(bg_dominated)

        info['bad_channel_count'] = int(bad_channel_count)
        info['bg_dominated_fraction'] = float(bad_channel_count / n_channels_in_range)

        # Log detailed info
        logger.info(f"[Screening] {os.path.basename(spectrum_path)}: "
                   f"{bad_channel_count}/{n_channels_in_range} channels background-dominated "
                   f"in {energy_low}-{energy_high} keV range")

        if bad_channel_count >= min_bad_channels:
            info['passes'] = False
            info['reason'] = f"Background dominates in {bad_channel_count} channels (threshold: {min_bad_channels})"
            logger.info(f"[Screening] GTI FAILS: {info['reason']}")
            return False, info

        info['passes'] = True
        info['reason'] = f"Passed: only {bad_channel_count} bad channels (threshold: {min_bad_channels})"
        logger.info(f"[Screening] GTI PASSES: {info['reason']}")
        return True, info

    except Exception as e:
        info['reason'] = f"Error during screening: {str(e)}"
        info['passes'] = True  # On error, default to including
        logger.exception(f"[Screening] Error screening {spectrum_path}: {e}")
        return True, info


def screen_gti_files(
        file_paths: list[str],
        gti_numbers: list[int],
        energy_low: float = DEFAULT_ENERGY_RANGE_LOW,
        energy_high: float = DEFAULT_ENERGY_RANGE_HIGH,
        min_bad_channels: int = DEFAULT_MIN_BAD_CHANNELS
) -> tuple[list[str], list[int], list[dict]]:
    """
    Screen multiple GTI files and return only those that pass.

    Parameters
    ----------
    file_paths : list[str]
        List of spectrum file paths
    gti_numbers : list[int]
        List of corresponding GTI numbers
    energy_low : float, default = 2.0
        Lower bound of energy range in keV
    energy_high : float, default = 5.0
        Upper bound of energy range in keV
    min_bad_channels : int, default = 2
        Minimum number of background-dominated channels to fail screening

    Returns
    -------
    Tuple[list[str], list[int], list[dict]]
        - passed_files: List of file paths that passed screening
        - passed_gtis: List of GTI numbers that passed
        - screening_results: List of screening info dicts for all files
    """
    logger.info(f"[Screening] Starting background screening for {len(file_paths)} GTI files")
    logger.info(f"[Screening] Parameters: energy_range={energy_low}-{energy_high} keV, min_bad_channels={min_bad_channels}")

    passed_files = []
    passed_gtis = []
    screening_results = []

    for file_path, gti_num in zip(file_paths, gti_numbers):
        logger.info(f"[Screening] Checking GTI {gti_num}: {os.path.basename(file_path)}")

        passes, info = check_background_domination(
            file_path,
            energy_low=energy_low,
            energy_high=energy_high,
            min_bad_channels=min_bad_channels
        )
        info['gti_number'] = gti_num
        screening_results.append(info)

        if passes:
            passed_files.append(file_path)
            passed_gtis.append(gti_num)

    logger.info(f"[Screening] RESULT: {len(passed_files)}/{len(file_paths)} GTIs passed screening")

    if len(passed_files) < len(file_paths):
        failed_gtis = [r['gti_number'] for r in screening_results if not r['passes']]
        logger.info(f"[Screening] Failed GTIs: {failed_gtis}")

    return passed_files, passed_gtis, screening_results


def get_screening_summary(screening_results: list[dict]) -> dict:
    """
    Generate a summary of screening results.

    Parameters
    ----------
    screening_results : list[dict]
        List of screening info dicts from screen_gti_files

    Returns
    -------
    dict
        Summary statistics
    """
    total = len(screening_results)
    passed = sum(1 for r in screening_results if r['passes'])
    failed = total - passed

    failed_gtis = [r['gti_number'] for r in screening_results if not r['passes']]
    bg_files_found = sum(1 for r in screening_results if r.get('bg_file_found', False))

    return {
        'total_gtis': total,
        'passed_gtis': passed,
        'failed_gtis': failed,
        'failed_gti_numbers': failed_gtis,
        'pass_rate': passed / total if total > 0 else 1.0,
        'bg_files_found': bg_files_found,
        'screening_applied': bg_files_found > 0,
    }
