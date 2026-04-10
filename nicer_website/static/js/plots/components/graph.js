/* global Plotly */

import { displayInfo, handleMultipleObservations } from './observationInfo.js';
import { GTISelection } from './gtiComponents.js';
import {
  updateAllSelections,
  initSynchronizedSelection,
} from './syncSelection.js';
import { initInteractiveLinking } from './interactiveLinking.js';
import { fetchGTIPlot, flagScreenedGTIs } from './gtiPlots.js';
import {
  startOperation,
  completeOperation,
  errorOperation,
} from './statusBar.js';
import { titleCase } from "../utils/utils.js";

/**
 *  CSS styles for the popup to the document head
 */
function addPopupStyles() {
  if (document.getElementById('popup-styles')) return;

  const styles = `
        .popup-container {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            animation: fadeIn 0.3s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideIn {
            from { transform: translateY(-50px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .popup-content {
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            width: 90%;
            max-width: 500px;
            padding: 0;
            position: relative;
            animation: slideIn 0.3s ease-out;
        }
        
        .popup-title {
            background-color: #505050;
            color: white;
            padding: 15px 20px;
            font-size: 18px;
            font-weight: bold;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .popup-close {
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            padding: 0;
            margin: 0;
            line-height: 1;
            transition: transform 0.2s;
        }
        
        .popup-close:hover {
            transform: scale(1.2);
        }
        
        .plot-type-form {
            padding: 20px;
            background-color: #f5f5f5;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        }
        
        .plot-option {
            margin-bottom: 15px;
            display: flex;
            align-items: center;
        }
        
        .plot-option input[type="checkbox"] {
            margin-right: 10px;
            width: 18px;
            height: 18px;
        }
        
        .plot-option label {
            font-size: 16px;
            cursor: pointer;
            color: #333;
        }
        
        .plot-submit-btn {
            background-color: #666666;
            color: black;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 10px;
            transition: background-color 0.2s, color 0.2s;
            width: 100%;
        }
        
        .plot-submit-btn:hover {
            background-color: #555555;
            color: white;
        }
        
        /* Background Screening Styles */
        .screening-section {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
        }
        
        .screening-toggle-container {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .screening-toggle-container input[type="checkbox"] {
            margin-right: 10px;
            width: 18px;
            height: 18px;
        }
        
        .screening-toggle-container label {
            font-size: 14px;
            cursor: pointer;
            color: #333;
            font-weight: bold;
        }
        
        .screening-options {
            display: none;
            padding: 10px;
            background: #e9e9e9;
            border-radius: 4px;
            margin-top: 10px;
        }
        
        .screening-options.visible {
            display: block;
        }
        
        .screening-option-row {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .screening-option-row label {
            font-size: 12px;
            min-width: 120px;
        }
        
        .screening-option-row input {
            width: 70px;
            padding: 4px 6px;
            border: 1px solid #ccc;
            border-radius: 3px;
        }
        
        .screening-info {
            font-size: 11px;
            color: #666;
            margin-top: 8px;
            font-style: italic;
        }
    `;

  const styleElement = document.createElement('style');
  styleElement.id = 'popup-styles';
  styleElement.textContent = styles;
  document.head.appendChild(styleElement);
}

/**
 * Displays a popup for selecting which plot types to generate for an observation ID
 * @param {string} obsID The observation ID to create plots for
 */
export function showPlotSelectionPopup(obsID) {
  // Add CSS styles
  addPopupStyles();

  // Create popup container if it doesn't exist
  let $popup = $('#plot-selection-popup');
  if ($popup.length === 0) {
    $popup = $('<div>', {
      id: 'plot-selection-popup',
      class: 'popup-container',
    });

    const $content = $('<div>', {
      class: 'popup-content',
    });

    const $title = $('<div>', {
      class: 'popup-title',
      text: 'Select Plot Types',
    });

    const $closeBtn = $('<button>', {
      class: 'popup-close',
      text: '×',
    });

    $title.append($closeBtn);
    $content.append($title);
    $popup.append($content);
    $('body').append($popup);

    // Setup close button and backdrop click to close popup
    $popup.on('click', function (e) {
      if (e.target === this) {
        $popup.fadeOut(200);
      }
    });

    $popup.on('click', '.popup-close', function () {
      $popup.fadeOut(200);
    });
  }

  // Update popup content
  const $content = $popup.find('.popup-content');
  $content
    .find('.popup-title')
    .text(`Select Plot Types for Observation ID: ${obsID}`)
    .append(
      $('<button>', {
        class: 'popup-close',
        text: '×',
      }),
    );

  // Remove any existing form
  $content.find('form').remove();

  // Create form for plot type selection
  const $form = $('<form>', {
    id: 'plot-type-form',
    class: 'plot-type-form',
  });

  // Add plot type options
  const plotTypes = [
    { id: 'spectrum', name: 'Spectrum' },
    { id: 'summed-spectrum', name: 'Summed Spectrum' },
    { id: 'light-curve', name: 'Light Curve' },
    { id: 'power-density-spectrum', name: 'Power Density Spectrum' },
    { id: 'hardness-intensity-diagram', name: 'Hardness Intensity Diagram' },
  ];

  plotTypes.forEach((type) => {
    const $option = $('<div>', {
      class: 'plot-option',
    });

    const $checkbox = $('<input>', {
      type: 'checkbox',
      id: `${type.id}-checkbox`,
      name: type.id,
      value: 'on',
    });

    const $label = $('<label>', {
      for: `${type.id}-checkbox`,
      text: type.name,
    });

    $option.append($checkbox);
    $option.append($label);
    $form.append($option);
  });

  // Add hidden field for observation ID
  $form.append(
    $('<input>', {
      type: 'hidden',
      name: 'obs_id',
      value: obsID,
    }),
  );

  // Add Background Screening Section
  const $screeningSection = $('<div>', {
    class: 'screening-section',
  });

  const $screeningToggleContainer = $('<div>', {
    class: 'screening-toggle-container',
  });

  // Use a hidden input that we'll control with JS
  const $screeningHidden = $('<input>', {
    type: 'hidden',
    name: 'apply_screening',
    id: 'apply-screening-value',
    value: 'false',
  });

  const $screeningCheckbox = $('<input>', {
    type: 'checkbox',
    id: 'apply-screening-checkbox',
  });

  const $screeningLabel = $('<label>', {
    for: 'apply-screening-checkbox',
    text: 'Enable Background Screening',
    title: 'Filter out GTIs where background dominates the source signal',
  });

  $screeningToggleContainer.append($screeningCheckbox, $screeningLabel);
  $screeningSection.append($screeningToggleContainer);

  // Screening options (hidden by default)
  const $screeningOptions = $('<div>', {
    class: 'screening-options',
    id: 'screening-options',
  });

  // Energy Low
  const $energyLowRow = $('<div>', { class: 'screening-option-row' });
  $energyLowRow.append(
    $('<label>', { text: 'Energy Low (keV):' }),
    $('<input>', {
      type: 'number',
      name: 'screening_energy_low',
      id: 'screening-energy-low',
      value: 2.0,
      step: 0.1,
      min: 0.3,
      max: 10,
    }),
  );
  $screeningOptions.append($energyLowRow);

  // Energy High
  const $energyHighRow = $('<div>', { class: 'screening-option-row' });
  $energyHighRow.append(
    $('<label>', { text: 'Energy High (keV):' }),
    $('<input>', {
      type: 'number',
      name: 'screening_energy_high',
      id: 'screening-energy-high',
      value: 5.0,
      step: 0.1,
      min: 0.3,
      max: 12,
    }),
  );
  $screeningOptions.append($energyHighRow);

  // Min Bad Channels
  const $minBadRow = $('<div>', { class: 'screening-option-row' });
  $minBadRow.append(
    $('<label>', { text: 'Min Bad Channels:' }),
    $('<input>', {
      type: 'number',
      name: 'screening_min_bad_channels',
      id: 'screening-min-bad-channels',
      value: 2,
      min: 1,
      max: 100,
    }),
  );
  $screeningOptions.append($minBadRow);

  // Info text
  const $screeningInfo = $('<div>', {
    class: 'screening-info',
    text: 'Excludes GTIs where background > source in 2+ channels within the energy range. Only applies to spectrum plots.',
  });
  $screeningOptions.append($screeningInfo);

  $screeningSection.append($screeningOptions);
  $form.append($screeningHidden);
  $form.append($screeningSection);

  // Toggle screening options visibility and update hidden value
  $screeningCheckbox.on('change', function () {
    const isChecked = $(this).is(':checked');
    $screeningHidden.val(isChecked ? 'true' : 'false');

    if (isChecked) {
      $screeningOptions.addClass('visible');
      console.log('[Screening] Background screening ENABLED');
    } else {
      $screeningOptions.removeClass('visible');
      console.log('[Screening] Background screening DISABLED');
    }
  });

  // Add submit button
  const $submitBtn = $('<button>', {
    type: 'submit',
    class: 'plot-submit-btn',
    text: 'Generate Plots',
  });

  $form.append($submitBtn);

  // Handle form submission
  $form.on('submit', function (event) {
    event.preventDefault();

    // Log screening state for debugging
    const screeningEnabled = $('#apply-screening-value').val() === 'true';
    console.log('[Graph.js] Form submitted with screening:', screeningEnabled);
    if (screeningEnabled) {
      console.log('[Graph.js] Screening params:', {
        energy_low: $('#screening-energy-low').val(),
        energy_high: $('#screening-energy-high').val(),
        min_bad_channels: $('#screening-min-bad-channels').val(),
      });
    }

    $popup.fadeOut(200);

    // Check if a specific GTI was selected from GTI plot button
    if (window.selectedGTI && window.selectedGTIObsId === obsID) {
      // Handle GTI-specific plotting
      const selectedPlotTypes = [];
      $(this).find('input[type="checkbox"]:checked')
          .not('#apply-screening-checkbox').each(function() {
              selectedPlotTypes.push($(this).attr('name'));
          });

      if (selectedPlotTypes.length === 0) {
        alert('Please select at least one plot type.');
        return;
      }

      // Get screening parameters
      const applyScreening = $('#apply-screening-value').val() === 'true';
      const screeningEnergyLow = $('#screening-energy-low').val();
      const screeningEnergyHigh = $('#screening-energy-high').val();
      const screeningMinBadChannels = $('#screening-min-bad-channels').val();

      // Create forms for each selected plot type and submit to GTI plotting endpoint
      selectedPlotTypes.forEach((plotType) => {
        console.log(
          `[DEBUG graph.js] Creating GTI form for plot type: ${plotType}, GTI: ${window.selectedGTI}, ObsID: ${obsID}, Screening: ${applyScreening}`,
        );
        const $gtiForm = $('<form>');
        $gtiForm.append($('<input>', {
          name: 'gti-search',
          type: 'hidden',
          value: window.selectedGTI,
        }));
        $gtiForm.append($('<input>', {
          name: 'plot_type',
          type: 'hidden',
          value: plotType.replace(/-/g, '_'), // Convert dashes to underscores for backend
        }));
        $gtiForm.append($('<input>', {
          name: 'obs_id',
          type: 'hidden',
          value: obsID,
        }));
        $gtiForm.append($('<input>', {
          name: 'min_value',
          type: 'hidden',
          value: '1',
        }));

        // Always add screening parameters
        $gtiForm.append(
          $('<input>', {
            name: 'apply_screening',
            type: 'hidden',
            value: applyScreening ? 'true' : 'false',
          }),
        );
        $gtiForm.append(
          $('<input>', {
            name: 'screening_energy_low',
            type: 'hidden',
            value: screeningEnergyLow,
          }),
        );
        $gtiForm.append(
          $('<input>', {
            name: 'screening_energy_high',
            type: 'hidden',
            value: screeningEnergyHigh,
          }),
        );
        $gtiForm.append(
          $('<input>', {
            name: 'screening_min_bad_channels',
            type: 'hidden',
            value: screeningMinBadChannels,
          }),
        );

        console.log(
          `[DEBUG graph.js] Form data for ${plotType}:`,
          $gtiForm.serialize(),
        );

        // Create mock event for fetchGTIPlot
        const mockEvent = {
          preventDefault: () => {},
          target: $gtiForm[0],
        };

        // Call fetchGTIPlot directly
        console.log(`[DEBUG graph.js] Calling fetchGTIPlot for ${plotType}`);
        fetchGTIPlot(mockEvent);
      });

      // Clear the stored GTI values
      delete window.selectedGTI;
      delete window.selectedGTIObsId;
    } else {
      // Call fetchGraphPlots for regular observation plotting
      fetchGraphPlots(false, event);
    }
  });

  $content.append($form);

  // Show the popup with animation
  $popup.css('display', 'flex').hide().fadeIn(300);
}

/**
 * Creates or updates a Plotly plot for the given observation ID and plot configuration
 *
 * @param obsID {string} Observation ID for the plot
 * @param plotDiv {Object} Plotly plot configuration object containing data, layout, and config
 * @param maxGTI {number} Maximum GTI number for the observation, used for GTI selection form
 * (optional)
 * @param prefix {string} Optional prefix for the plot title and ID
 * @param suffix {string} Optional suffix for the plot title and ID
 * @return {string} The ID of the plot div where the plot was created or updated
 */
export function creatPlot(
    obsID,
    plotDiv,
    {maxGTI = 0,
    prefix = '',
    suffix = ''} = {}) {
  plotDiv = JSON.parse(plotDiv)
  const PLOT_ID = (prefix + plotDiv.layout.title.text + suffix).toLowerCase()
      .replaceAll(' ', '-');
  const TYPE = PLOT_ID.replace(`-${obsID}`, '');
  plotDiv.config = {displaylogo: false, ...(plotDiv.config || {})};

  if (!$(`#${TYPE}-section`).length) {
    const $PLOT_SECTION = $('<div>', {
      id: `${TYPE}-section`,
      class: 'plot-type-section',
    });
    $PLOT_SECTION.append(
      $('<h3>', {
        text: titleCase(TYPE.replaceAll('-', ' ')),
      }),
    );

    const $COMBINE_FORM = $('<form>', { class: 'combine-gtis hide' });
    $COMBINE_FORM.append(
      $('<input>', { type: 'hidden', name: 'plot_type', value: TYPE }),
    );
    $COMBINE_FORM.append(
      $('<input>', {
        type: 'hidden',
        name: 'quality',
        value: $('#quality-select').val().toLowerCase(),
      }),
    );
    const $COMBINE_BUTTON = $('<button>', {
      type: 'submit',
      text: 'Combine Observations',
    });

    $COMBINE_FORM.append($COMBINE_BUTTON);
    $PLOT_SECTION.append($COMBINE_FORM);
    $('#plots').append($PLOT_SECTION);
  }

  if ($(`#${PLOT_ID}`).length === 0) {
    const $PLOT_DIV = $('<div>', {id: PLOT_ID});
    $(`#${TYPE}-section`).append($PLOT_DIV);
    Plotly.newPlot(PLOT_ID, plotDiv.data, plotDiv.layout, plotDiv.config)
        .catch(err => console.error('Plotly error:', err));

    // Add GTI selection form (but not for summed spectrum plots as they already have combined GTIs)
    if (TYPE !== 'summed-spectrum') {
      const $GTI_FORM = GTISelection(
        maxGTI,
        obsID,
        TYPE,
      );
      $PLOT_DIV.append($GTI_FORM);
    }
  } else {
    Plotly.react(PLOT_ID, plotDiv.data, plotDiv.layout, plotDiv.config)
        .catch(err => console.error('Plotly error:', err));
  }
  updateCombineButtonVisibility(TYPE);

  return PLOT_ID;
}

/**
 * Fetches and displays the table for the given observation ID or source name
 * If plots are requested, also fetches and displays plots
 *
 * @param {boolean} refresh If the page content should be refreshed
 * @param {Event} event Event generated by form submit
 */
export function fetchGraphPlots(refresh = false, event) {
  if (!event || !event.target) {
    console.error('Event or event.target is undefined in fetchGraphPlots');
    return;
  }

  let serializedData = $(event.target).serialize();
  event.preventDefault();
  serializedData += `&csrfmiddlewaretoken=${$(
    "input[name='csrfmiddlewaretoken']",
  ).val()}`;
  serializedData += `&quality=${$('#quality-select').val().toLowerCase()}`;

  // Generate unique operation ID and start status tracking
  const operationId = 'fetch-plots-' + Date.now();
  const obsId = serializedData.match(/obs_id=([^&]+)/)?.[1] || 'unknown';
  startOperation(operationId, 'Loading data for observation ' + obsId + '...');

  // Sends an asynchronous request to fetch data
  $.ajax({
    type: 'POST',
    url: PLOT_GRAPH_URL,
    data: serializedData,
    success: function (response) {
      // Clear both obs-info and plots divs if refreshing
      if (refresh) {
        $('#add-obs').show();
        $('#plots').empty();
        $('#obs-info-table').empty();
        $('#remove-obs').empty();
      }

      if (response.error) {
        console.error('Error received:', response.error);
        errorOperation(operationId, 'Error: ' + response.error);
        alert(`${response.error}`);
        return;
      }

      if (response.multiple_observations) {
        completeOperation(operationId, 'Found multiple observations');
        handleMultipleObservations(response.obs_ids, response.source);
        return;
      }

      if (!response.info) {
        console.error('Unexpected response format:', response);
        errorOperation(operationId, 'Unexpected response from server');
        alert('Unexpected response from server.');
        return;
      }

      // Update info section - always show the table
      displayInfo(response.info);

      // Update form values if observation info is provided
      if (response.obs_info) {
        Object.entries(response.obs_info).forEach(([key, value]) => {
          $(`#${key}`).val(value);
        });
      }

      // Handle screening summaries if present
      if (response.screeningSummaries) {
        const summaries = response.screeningSummaries;
        let totalExcluded = 0;
        let summaryText = [];
        let allFailed = false;

        Object.entries(summaries).forEach(([type, summary]) => {
            // Check if ALL GTIs failed
            if (summary.passed_gtis === 0 && summary.total_gtis > 0) {
              allFailed = true;
              summaryText.push(`${type}: All ${summary.total_gtis} GTIs failed screening - showing unscreened data`);
            } else if (summary.failed_gtis > 0) {
                totalExcluded += summary.failed_gtis;
                summaryText.push(`${type}: ${summary.failed_gtis} GTIs excluded`);
            }
        });

        // Show notification for both partial and complete failures
        if (totalExcluded > 0 || allFailed) {
              // Create or update screening notification
              let $notification = $('#screening-notification');
              if ($notification.length === 0) {
                $notification = $('<div>', {
                  id: 'screening-notification',
                  class: 'screening-notification',
                  css: {
                    position: 'fixed',
                    bottom: '20px',
                    right: '20px',
                    padding: '15px 20px',
                    background: allFailed ? '#d9534f' : '#f0ad4e',  // Red if all failed, orange otherwise
                    color: '#fff',
                    borderRadius: '5px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
                    zIndex: 9999,
                    maxWidth: '400px',
                    fontSize: '14px',
                  }
                });
                $('body').append($notification);
              } else {
                // Update background color for existing notification
                $notification.css('background', allFailed ? '#d9534f' : '#f0ad4e');
              }

              const title = allFailed
                ? '<strong>⚠️ Background Screening: All GTIs Failed</strong>'
                : '<strong>Background Screening Applied</strong>';

              const message = allFailed
                ? 'Source is very faint - background dominates in all GTIs.<br>Showing unscreened data for analysis.'
                : summaryText.join('<br>');

              $notification.html(`
                ${title}<br>
                ${message}<br>
                <small>See console for details</small>
              `).fadeIn(300);

              // Auto-hide after longer duration if all failed (users need to read the warning)
              setTimeout(() => {
                $notification.fadeOut(500);
              }, allFailed ? 8000 : 5000);
        }

        // Flag failed GTIs in the observation info table
        Object.entries(summaries).forEach(([, summary]) => {
          if (summary.failed_gti_numbers && summary.failed_gti_numbers.length > 0) {
            flagScreenedGTIs(response.obsID, summary.failed_gti_numbers);
          }
        });
      }

      // Process plots only if plot types were requested
      const hasPlotTypes =
        serializedData.includes('spectrum=') ||
        serializedData.includes('summed-spectrum=') ||
        serializedData.includes('light-curve=') ||
        serializedData.includes('power-density-spectrum=') ||
        serializedData.includes('hardness-intensity-diagram=');

      if (hasPlotTypes && response.plotDivs && response.plotDivs.length > 0) {
        response.plotDivs.forEach((plotDiv, i) => {
          creatPlot(response.obsID, plotDiv, {maxGTI: response.maxGTI[i]});
        });

        // Typeset any math expressions
        MathJax.typeset();

        // Update plot selections after plots are added
        // Add a larger delay to ensure Plotly has fully rendered
        setTimeout(() => {
          console.log('Running updateAllSelections from fetchGraphPlots');
          // First reinitialize the synchronized selection for new plots
          initSynchronizedSelection();
          // Then update any existing selections
          updateAllSelections();
          // Initialize interactive linking between spectrum and light curve
          initInteractiveLinking();
        }, 800);

        completeOperation(
          operationId,
          'Successfully loaded ' +
            response.plotDivs.length +
            ' plot(s) for observation ' +
            response.obsID,
        );
      } else {
        completeOperation(
          operationId,
          'Successfully loaded observation data for ' +
            (response.obsID || obsId),
        );
      }

      // Add observation removal functionality
      if (!$(`#remove-${response.obsID}`).length && hasPlotTypes) {
        const REMOVE_BUTTON = $('<button>', {
          id: `remove-${response.obsID}`,
          class: 'remove-observation-btn',
          text: `Remove Observation ${response.obsID}`,
        });

        REMOVE_BUTTON.click(function () {
          removePlots(response, REMOVE_BUTTON);
        });

        $('#remove-obs').append(REMOVE_BUTTON);
      }
    },
    error: function (_, textStatus, errorThrown) {
      console.error('AJAX error:', textStatus, errorThrown);
      errorOperation(operationId, 'Network error occurred');
      alert('An error occurred while fetching data. Please try again.');
    },
    complete: function () {
      // Operation completion is handled in success/error callbacks
    },
  });
}

export function removePlots(response, removeButton) {
  // Remove plots for this observation
  $('.plot-type-section').each(function () {
    const TYPE = this.id.replace('-section', '');
    $(this).find(`#${TYPE}-${response.obsID}`).remove();

    if ($(this).children('div').length == 0) {
      $(this).remove();
    }

    updateCombineButtonVisibility(TYPE);
  });

  // Remove the info section for this observation
  $(`[data-obs-id="${response.obsID}"]`).remove();

  // Hide the table and add observation button
  if ($('#obs-info-table').find('tr').length <= 1) {
    $('#obs-info').hide();
    $('#add-obs').hide();
  }

  // Remove the remove button itself
  $(removeButton).remove();

  // If we're removing a plot, update the synchronized selections
  setTimeout(() => {
    console.log('Running updateAllSelections after removing plots');
    updateAllSelections();
  }, 500);
}

export function updateCombineButtonVisibility(plotType) {
  let obsIDs = new Set();

  $(`#${plotType}-section`)
    .children('div')
    .each(function () {
      obsIDs.add(this.id.replace(`${plotType}-`, ''));
    });

  $(`.combine-gtis:has(input[name="plot_type"][value="${plotType}"])`).toggle(
    obsIDs.size >= 2,
  );
}
