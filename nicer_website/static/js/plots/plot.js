import { columnLayout, dropdowns } from './utils/utils.js';
import {
  displayInfo,
  handleMultipleObservations,
} from './components/observationInfo.js';
import {
  showPlotSelectionPopup,
  fetchGraphPlots,
  removePlots,
} from './components/graph.js';
import { fetchGTIPlot, combineAndPlotGTIs } from './components/gtiPlots.js';
import { fetchOptions, addOption } from './components/dropdowns.js';
import { downloadData } from './components/download.js';
import {
  initSynchronizedSelection,
  updateAllSelections,
} from './components/syncSelection.js';
import {
  initInteractiveLinking,
  diagnosePlotlyGraphs,
} from './components/interactiveLinking.js';
import { StatusBar } from './components/statusBar.js';
import {
  initGTICrossLinking,
  clearGTIHighlighting,
  setGTICrossLinking,
} from './components/gtiCrossLinking.js';

document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const reqKeys = Array.from(urlParams.keys()).filter((key) => key.startsWith('req'));

  if (reqKeys.length > 0) {
    reqKeys.sort();

    const decodeBase64Url = (value) => {
      let normalized = value.replace(/-/g, '+').replace(/_/g, '/');
      while (normalized.length % 4) normalized += '=';
      return atob(normalized);
    };

    (async () => {
      for (let i = 0; i < reqKeys.length; i++) {
        const reqStr = urlParams.get(reqKeys[i]);
        if (!reqStr) continue;

        const pipeIndex = reqStr.indexOf('|');
        if (pipeIndex === -1) continue;

        const reqType = reqStr.substring(0, pipeIndex);
        let reqData = reqStr.substring(pipeIndex + 1);

        if (reqData.startsWith('b64:')) {
          try {
            reqData = decodeBase64Url(reqData.substring(4));
          } catch (error) {
            console.error('Failed to decode stored request data', error);
            continue;
          }
        }

        const $mockForm = $('<form>');
        const paramsData = new URLSearchParams(reqData);

        for (const [key, value] of paramsData.entries()) {
          $('<input>').attr({ type: 'hidden', name: key, value }).appendTo($mockForm);
        }

        $('<input>')
          .attr({
            type: 'hidden',
            name: 'csrfmiddlewaretoken',
            value: $("input[name='csrfmiddlewaretoken']").val(),
          })
          .appendTo($mockForm);

        const mockEvent = {
          preventDefault: () => {},
          target: $mockForm[0],
        };

        if (reqType === 'graph') {
          fetchGraphPlots(i === 0, mockEvent);
        } else if (reqType === 'gti') {
          fetchGTIPlot(mockEvent);
        }

        await new Promise((resolve) => setTimeout(resolve, 600));
      }
    })();
  }

  // Initialize the status bar
  StatusBar.getInstance();

  // Ensure jQuery is loaded
  if (typeof $ === 'undefined') {
    console.error(
      'jQuery is not loaded. Cannot initialize synchronized selection.',
    );
    return;
  }

  dropdowns();

  $('#plot-graph').submit(function (event) {
    event.preventDefault();
    fetchGraphPlots(true, event);
  });

  $('#add-obs').submit(function (event) {
    $('#options')
      .find('input:checked')
      .each(function () {
        $('#add-obs').append(
          $('<input>', {
            type: 'hidden',
            name: $(this).attr('name'),
            value: $(this).val(),
          }),
        );
      });

    event.preventDefault();
    fetchGraphPlots(false, event);
  });

  $('#observation-search').keyup(function () {
    fetchOptions(`obs_id=${this.value}`, $('#obs-id-dropdown'));
  });

  $('#additional-observation-search').keyup(function () {
    fetchOptions(`obs_id=${this.value}`, $('#add-obs-dropdown'));
  });

  $('#source-search').keyup(function () {
    fetchOptions(`source=${this.value}`, $('#source-name-dropdown'));
  });

  $('#add-obs-btn').click(function () {
    $('#add-obs-dropdown').toggle();
  });

  $('#search-type').change(function () {
    const OBS_SEARCH = $(this).val() === 'true';
    $('#obs-id-dropdown').toggle(OBS_SEARCH);
    $('#source-name-dropdown').toggle(!OBS_SEARCH);
  });

  $('#advance-search-btn').click(function () {
    $('#advanced-search').toggle();
  });

  $('.change-quality').click(function () {
    $('#quality-select').val(this.textContent);
  });

  $(document).on('submit', '.fetch-gti', function (event) {
    fetchGTIPlot(event);
  });

  $(document).on('submit', '.combine-gtis', function (event) {
    combineAndPlotGTIs(event);
  });

  $(document).on('click', '.popup-close', function () {
    $('#plot-selection-popup').hide();
  });

  $(document).on('click', '.plot-button', function () {
    const obsID = $(this).data('obs-id');
    showPlotSelectionPopup(obsID);
  });

  $(document).on('click', '.download-data', function () {
    const dataType = $(this).data('type');
    const obsId = $(this).data('obs-id');
    // First try to get GTI from button data attribute, then fallback to table row
    let gtiNum = $(this).data('gti');
    if (!gtiNum) {
      gtiNum = $(this).closest('tr').data('gti')?.replace('GTI', '');
    }
    const quality = $('#quality-select').val();

    if (dataType === 'gti' && gtiNum) {
      downloadData(dataType, obsId, null, [gtiNum], quality);
    } else {
      downloadData(dataType, obsId, null, null, quality);
    }
  });

  $(document).on('click', '.plot-gti', function (event) {
    event.preventDefault();

    const obsId = $(this).data('obs-id');
    const gtiNum = $(this).data('gti');

    // Store the GTI number
    window.selectedGTI = gtiNum;
    window.selectedGTIObsId = obsId;

    // Show the plot selection popup
    showPlotSelectionPopup(obsId);
  });

  $(document).on('change', '.gti-checkbox', function () {
    const $table = $(this).closest('table');
    const hasChecked = $table.find('.gti-checkbox:checked').length > 0;
    $table.siblings('.selected-gti-actions').toggle(hasChecked);
  });

  $(document).on('click', '.download-selected-gtis', function () {
    const $table = $(this).closest('.obs-info-container').find('table');
    const obsId = $table.find('tr:first').data('obs-id');
    const selectedGtis = [];
    const quality = $('#quality-select').val();

    $table.find('.gti-checkbox:checked').each(function () {
      const gtiNum = $(this).closest('tr').data('gti').replace('GTI', '');
      selectedGtis.push(gtiNum);
    });

    if (selectedGtis.length > 0) {
      downloadData('gti', obsId, null, selectedGtis, quality);
    }
  });

  // Initialize synchronized selection when new plots are loaded
  $(document).ajaxComplete(function (event, xhr, settings) {
    if (
      settings.url.includes('plot_data') ||
      settings.url.includes('plot_gti')
    ) {
      // Use a flag to track if we've successfully initialized
      let initialized = false;

      // First attempt with short delay
      setTimeout(() => {
        if (initialized) return;

        // Ensure global Plotly object is available
        if (typeof Plotly !== 'undefined') {
          console.log('First attempt initializing interactive features...');

          const plots = document.querySelectorAll('.js-plotly-plot');
          if (plots.length > 0) {
            // Only initialize if not already initialized
            const alreadyInitialized = Array.from(plots).some(
              (plot) =>
                plot.getAttribute('data-interactive-linking') === 'true',
            );

            if (!alreadyInitialized) {
              initSynchronizedSelection();
              initInteractiveLinking();
              initGTICrossLinking(); // Add GTI cross-linking initialization
              initialized = true;
            } else {
              console.log('Interactive features already initialized, skipping');
              initialized = true;
            }
          }
        } else {
          console.error(
            'Plotly is not loaded. Cannot initialize interactive features.',
          );
        }
      }, 500);

      // Second attempt only if first failed
      setTimeout(() => {
        if (initialized) return;

        if (typeof Plotly !== 'undefined') {
          console.log('Second attempt initializing interactive features...');

          const plots = document.querySelectorAll('.js-plotly-plot');
          if (plots.length > 0 && !initialized) {
            initSynchronizedSelection();
            updateAllSelections();
            initInteractiveLinking();
            initGTICrossLinking(); // Add GTI cross-linking initialization
            initialized = true;
          }
        }
      }, 1000);
    }
  });

  window.diagnosePlotlyGraphs = diagnosePlotlyGraphs;
});

// Initialize interactive linking feature when plots are added
$(document).on('DOMNodeInserted', function (e) {
  // Only process if contains a plotly graph
  if (
    $(e.target).find('.js-plotly-plot').length > 0 ||
    $(e.target).hasClass('js-plotly-plot')
  ) {
    // Allow DOM to fully render
    setTimeout(() => {
      const plots = document.querySelectorAll('.js-plotly-plot');
      const initialized = Array.from(plots).some(
        (plot) => plot.getAttribute('data-interactive-linking') === 'true',
      );

      if (!initialized) {
        console.log('Initializing interactive linking after DOM insertion');
        initInteractiveLinking();
      }
    }, 500);
  }
});

// Add a global fallback click handler for plots
$(document).on('click', '.js-plotly-plot', function (event) {
  // Only handle if it appears we don't have working interactive linking
  if (this.getAttribute('data-interactive-linking') !== 'true') {
    const plots = document.querySelectorAll('.js-plotly-plot');
    // Only attempt if we haven't tried to initialize yet
    if (plots.length >= 2 && !window.interactiveLinkingAttempted) {
      console.log(
        'Attempting to initialize interactive linking from global handler',
      );
      window.interactiveLinkingAttempted = true;
      initInteractiveLinking();
    }
  }
});

// Listen for our custom plotly_direct_click event
$(document).on('plotly_direct_click', function (e) {
  // Only try to initialize interactive linking if not already done
  if (!window.interactiveLinkingAttempted) {
    const plots = document.querySelectorAll('.js-plotly-plot');
    if (plots.length >= 2) {
      console.log(
        'Attempting to initialize interactive linking from direct click event',
      );
      window.interactiveLinkingAttempted = true;
      initInteractiveLinking();
    }
  }
});
