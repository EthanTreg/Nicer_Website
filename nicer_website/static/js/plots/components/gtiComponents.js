import { columnLayout } from '../utils/utils.js';
import {
  startOperation,
  completeOperation,
  errorOperation,
  updateOperationMessage,
  clearOperationsByPattern,
  completeOperationsByPattern,
} from './statusBar.js';
import { setGTICrossLinking, clearGTIHighlighting } from './gtiCrossLinking.js';

/**
 * Generates a GTI selection field for a specific plot
 * for the user to select which GTIs to plot.
 * @param {number} maxGTI Maximum GTI number for the plot type
 * and observation ID
 * @param {number} obsID Observation ID for the plot
 * @param {String} plotType Which plot is the GTI selection field being added to
 * @param {number} defaultBinning Default binning value (1% of max counts)
 * @returns {JQuery<HTMLFormElement>} HTML form element containing
 * the GTI selection field and submit button
 */
export function GTISelection(maxGTI, obsID, plotType, defaultBinning = 1) {
  // Constants
  console.log(
    `[DEBUG gtiComponents.js] GTISelection called. plotType: ${plotType}, obsID: ${obsID}, defaultBinning: ${defaultBinning}`,
  );

  const $FORM = $('<form>', { class: 'fetch-gti' });
  let cleanPlotType = plotType.replace(`-${obsID}`, '');

  // Calculate slider max as 10x the default binning or 200, whichever is larger
  let sliderMax = Math.max(200, defaultBinning * 10);

  // find label based on plot type
  let binningLabel = 'Binning';
  let binningUnit = 'counts';
  let binningDescription = 'Higher = fewer points, faster loading';
  let displayMultiplier = 1;

  if (cleanPlotType === 'light_curve' || cleanPlotType === 'light-curve') {
    binningLabel = 'Time Binning';
    binningUnit = 's';
    binningDescription = 'Combines time bins (1 bin = 0.125s)';
    displayMultiplier = 0.125;
  } else if (
    cleanPlotType === 'power_density_spectrum' ||
    cleanPlotType === 'power-density-spectrum'
  ) {
    binningLabel = 'Significance Threshold';
    binningUnit = 'sigma';
    binningDescription = 'Higher = more aggressive binning';
  } else if (
    cleanPlotType === 'hardness_intensity_diagram' ||
    cleanPlotType === 'hardness-intensity-diagram' ||
    cleanPlotType === 'time'
  ) {
    if (cleanPlotType === 'hardness_intensity_diagram') {
      cleanPlotType = 'hardness-intensity-diagram';
    }
    binningLabel = 'Time Binning';
    binningUnit = 's';
    binningDescription = 'Combines time bins (1 bin = 0.125s)';
    sliderMax = 400; // 50 seconds / 0.125s
    displayMultiplier = 0.125;
  } else if (
    cleanPlotType === 'spectrum' ||
    cleanPlotType === 'summed_spectrum' ||
    cleanPlotType === 'summed-spectrum'
  ) {
    binningLabel = 'Energy Grouping';
    binningUnit = 'counts';
    binningDescription = 'Combines energy bins (higher = fewer points)';
  }

  console.log(
    `[DEBUG gtiComponents.js GTISelection] Final cleanPlotType: ${cleanPlotType}`,
  );

  const $TYPE = $('<input>', {
    name: 'plot_type',
    type: 'hidden',
    value: cleanPlotType,
  });
  const $OBS_ID = $('<input>', {
    name: 'obs_id',
    type: 'hidden',
    value: obsID,
  });
  const $SEARCH = $('<input>', {
    name: 'gti-search',
    type: 'text',
    placeholder: `GTI numbers (,) and/or range (-) between 0 and ${Math.max(0, maxGTI - 1)}`,
  });

  const $HIDDEN_MIN_VALUE = $('<input>', {
    name: 'min_value',
    type: 'hidden',
    value: defaultBinning,
  });

  const $MIN_SLIDER = $(`<input>`, {
    id: `${cleanPlotType}-min-slider`,
    type: 'range',
    min: 1,
    max: sliderMax,
    value: defaultBinning,
    title: binningDescription,
  });

  let initialDisplayValue = defaultBinning;
  if (displayMultiplier !== 1) {
    initialDisplayValue = parseFloat(
      (defaultBinning * displayMultiplier).toFixed(3),
    );
  }

  const $CONTROLS_CONTAINER = $('<div>', {
    style:
      'display: flex; align-items: center; justify-content: center; margin-top: 5px; gap: 5px;',
  });

  const $BINNING_LABEL = $('<label>', {
    for: `${cleanPlotType}-min-input`,
    text: `${binningLabel}:`,
    title: binningDescription,
    style: 'margin-bottom: 0;',
  });

  const $MIN_INPUT = $('<input>', {
    id: `${cleanPlotType}-min-input`,
    type: 'number',
    min: displayMultiplier,
    step: displayMultiplier,
    value: initialDisplayValue,
    title: binningDescription,
    style: 'width: 80px; padding: 2px 5px;',
  });

  const $UNIT_LABEL = $('<span>', {
    text: binningUnit,
  });

  $CONTROLS_CONTAINER.append($BINNING_LABEL, $MIN_INPUT, $UNIT_LABEL);

  const $SUBMIT = $('<button>', { type: 'submit', text: 'Submit' });

  // GTI cross-linking toggle for HID plots
  let $crossLinkToggle = null;
  if (
    cleanPlotType === 'hardness_intensity_diagram' ||
    cleanPlotType === 'hardness-intensity-diagram'
  ) {
    $crossLinkToggle = $('<button>', {
      type: 'button',
      class: 'gti-cross-link-toggle',
      text: 'Enable GTI Cross-Linking',
      title:
        'Click points in HID to highlight corresponding GTIs in other plots',
    });

    let crossLinkEnabled = false;
    $crossLinkToggle.on('click', function () {
      crossLinkEnabled = !crossLinkEnabled;
      setGTICrossLinking(crossLinkEnabled);

      if (crossLinkEnabled) {
        $(this).addClass('active').text('GTI Cross-Linking Active');
      } else {
        $(this).removeClass('active').text('Enable GTI Cross-Linking');
      }
    });
  }

  // Adds elements to the form
  $FORM.append($TYPE);
  $FORM.append($OBS_ID);
  $FORM.append($HIDDEN_MIN_VALUE);
  $FORM.append(columnLayout([$SEARCH, $SUBMIT]));
  $FORM.append(columnLayout([$MIN_SLIDER, $CONTROLS_CONTAINER]));

  // Add cross-link toggle for HID
  if ($crossLinkToggle) {
    $FORM.append($crossLinkToggle);
  }

  console.log(
    `[DEBUG gtiComponents.js GTISelection] Form inputs:`,
    $FORM
      .find('input')
      .map(function () {
        return {
          name: $(this).attr('name'),
          value: $(this).val(),
          type: $(this).attr('type'),
        };
      })
      .get(),
  );

  // Update slider value on change and trigger form submission
  let sliderTimeout;
  let currentBinningOperationId = null;
  let lastSliderValue = defaultBinning;

  function handleBinningChange() {
    // Clear previous timeout
    if (sliderTimeout) {
      clearTimeout(sliderTimeout);
    }

    // Debounce the form submission
    sliderTimeout = setTimeout(() => {
      // Complete any existing binning operations for this plot type before creating a new one
      const binningPattern = 'gti-change-' + cleanPlotType + '-' + obsID;
      completeOperationsByPattern(binningPattern);

      // Start a new operation
      currentBinningOperationId = 'gti-change-' + cleanPlotType + '-' + obsID;
      startOperation(
        currentBinningOperationId,
        'Updating ' + cleanPlotType.replace(/_/g, ' ') + ' plot...',
      );

      // Use jQuery trigger which bubbles and hits jQuery handlers
      $FORM.trigger('submit');

      console.log(`[DEBUG gtiComponents.js] Form submitted via binning change`);
    }, 300); // 300ms debounce
  }

  // Helper to sync binning between HID and Light Curve
  function syncOtherPlotBinning(val) {
    const currentType = cleanPlotType.replace(/_/g, '-');
    let targetType = null;

    // Handle both standard and legacy 'time' names for HID
    if (
      currentType === 'hardness-intensity-diagram' ||
      currentType === 'time'
    ) {
      targetType = 'light-curve';
    } else if (currentType === 'light-curve') {
      targetType = 'hardness-intensity-diagram';
    }

    if (!targetType) return;

    // Construct target container ID
    const targetId = `#${targetType}-${obsID}`;
    let $targetContainer = $(targetId);

    // Fallback for HID if using legacy 'time' ID
    if (
      $targetContainer.length === 0 &&
      targetType === 'hardness-intensity-diagram'
    ) {
      $targetContainer = $(`#time-${obsID}`);
    }

    if ($targetContainer.length) {
      const $targetForm = $targetContainer.find('form.fetch-gti');
      if ($targetForm.length) {
        console.log(
          `[Sync] Syncing ${currentType} -> ${targetType} with value ${val}`,
        );
        const $targetSlider = $targetForm.find('input[type="range"]');

        if ($targetSlider.length) {
          // Update max if needed
          const currentMax = parseInt($targetSlider.attr('max'));
          if (val > currentMax) {
            $targetSlider.attr('max', val);
          }

          // Update value and trigger input event with sync flag
          $targetSlider.val(val);
          // Pass the sync flag as an object in the extraParameters array
          $targetSlider.trigger('input', [{ fromSync: true }]);
        }
      }
    }
  }

  $MIN_SLIDER.on('input', function (e, data) {
    const isSync = data && data.fromSync;
    const newValue = parseInt($(this).val());
    console.log(
      `[DEBUG gtiComponents.js] Slider input changed for ${cleanPlotType}. New value: ${newValue}`,
    );

    // Update hidden input
    $HIDDEN_MIN_VALUE.val(newValue);

    // Calculate display value
    let displayValue = newValue;
    if (displayMultiplier !== 1) {
      displayValue = parseFloat((newValue * displayMultiplier).toFixed(3));
    }

    // Update number input
    $MIN_INPUT.val(displayValue);

    lastSliderValue = newValue;
    handleBinningChange();

    if (!isSync) {
      syncOtherPlotBinning(newValue);
    }
  });

  $MIN_INPUT.on('input', function (e, data) {
    const isSync = data && data.fromSync;
    const val = parseFloat($(this).val());
    if (isNaN(val)) return;

    let intValue = Math.round(val / displayMultiplier);
    if (intValue < 1) intValue = 1;

    console.log(
      `[DEBUG gtiComponents.js] Number input changed for ${cleanPlotType}. New value: ${val} -> int: ${intValue}`,
    );

    // Update slider max if needed
    const currentMax = parseInt($MIN_SLIDER.attr('max'));
    if (intValue > currentMax) {
      $MIN_SLIDER.attr('max', intValue);
    }

    // Update slider and hidden input
    $MIN_SLIDER.val(intValue);
    $HIDDEN_MIN_VALUE.val(intValue);

    lastSliderValue = intValue;
    handleBinningChange();

    if (!isSync) {
      syncOtherPlotBinning(intValue);
    }
  });

  let gtiTimeout;
  let currentGtiOperationId = null;
  let lastGtiValue = '';

  $SEARCH.on('input', function () {
    const newGTIs = $(this).val();
    console.log(
      `[DEBUG gtiComponents.js] GTI search input changed for ${cleanPlotType}. New value: ${newGTIs}`,
    );

    lastGtiValue = newGTIs;

    // Clear previous timeout
    if (gtiTimeout) {
      clearTimeout(gtiTimeout);
    }

    // Debounce the form submission
    gtiTimeout = setTimeout(() => {
      // Complete any existing GTI operations for this plot type before creating a new one
      const gtiPattern = 'gti-change-' + cleanPlotType + '-' + obsID;
      completeOperationsByPattern(gtiPattern);

      // Start a new operation
      currentGtiOperationId = 'gti-change-' + cleanPlotType + '-' + obsID;
      const gtiText = lastGtiValue ? 'GTI ' + lastGtiValue : 'selected GTIs';
      startOperation(
        currentGtiOperationId,
        'Updating ' + cleanPlotType.replace(/_/g, ' ') + ' plot...',
      );

      // Check if the form has a submit handler attached
      const events = $._data($FORM[0], 'events');
      // Automatically submit the form when the search input changes
      $FORM.submit();
    }, 500); // 500ms debounce for text input
  });

  return $FORM;
}
