/* global PLOT_GRAPH_URL PLOT_GTI_URL MathJax */

/**
 * Generates a grid layout with a column for each element input.
 *
 * Supports jQuery.
 * @param {Array.<HTMLElement>} elements
 * List of HTML elements to spread over a column layout
 * @returns {HTMLDivElement}
 * Grid layout as an HTML div element
 * containing columns with each inputted element
 */
function columnLayout(elements) {
  const ROW = document.createElement('div');

  ROW.classList.add('row');

  // For each element, create a column containing the element
  for (const ELEMENT of elements) {
    const COLUMN = document.createElement('div');

    COLUMN.classList.add('column');
    $(COLUMN).append(ELEMENT);
    $(ROW).append(COLUMN);
  }

  return ROW;
}

/**
 * Updates the quality setting when the user activates a quality button.
 * @param {String} buttonQuality Pipeline quality value of the activated
 */
function changeQuality(buttonQuality) {
  quality = buttonQuality.toLowerCase();
  document.querySelector('#quality-select').value = buttonQuality;
}

/**
 * Generates a button for a suggested observation
 * ID that the user can click to autocomplete.
 * @param {String} obsID Observation ID
 */
function addObservation(obsID) {
  const OPTION = document.createElement('button');

  OPTION.setAttribute('type', 'button');
  OPTION.innerHTML = obsID;

  // If button is clicked, set the search field to the
  // observation ID of the clicked button
  OPTION.addEventListener('click', () => {
    document.querySelector('#observation-search').value = obsID;
  });

  document.querySelector('#observation-options').append(OPTION);
}

/**
 * Searches for observation IDs that match the search field.
 *
 * Creates buttons for each observation ID that matches the search field.
 * @param {String} obsID Partial or complete observation ID
 */
function fetchOptions(obsID) {
  fetch(`/plots/fetch_observations?obs_id=${obsID}`)
    .then((response) => response.json())
    .then((data) => {
      // Generates buttons for each observation ID that matches the search field
      document.querySelector('#observation-options').innerHTML = '';
      data.dir_suggestions.forEach(addObservation);
    });
}

/**
 * Displays information for each GTI in a dropdown table.
 * @param {Array.<Object>} info List of information for all GTI
 * @returns {HTMLDivElement}
 * Container containing the expandable table of GTIs
 */
function displayInfo(info) {
  // Information types to display in the table
  const TABLE_INFO = {
    headers: [
      'GTI',
      'Source',
      'MJD',
      String.raw`RA \((^\circ)\)`,
      String.raw`DEC \((^\circ)\)`,
      String.raw`Exposure Time \((s)\)`,
      'Detectors',
      String.raw`Undershoot Rate \((s^{-1})\)`,
      String.raw`Overshoot Rate \((s^{-1})\)`,
      String.raw`COR SAX \((GeV\ c^{-1})\)`,
    ],
    keys: [
      'GTI',
      'OBJECT',
      'TSTART_MJD_UTC',
      'RA',
      'DEC',
      'EXPTIME',
      'NDETS_USED',
      'USHOOT_NET_RATE',
      'OSHOOT_NET_RATE',
      'COR_SAX',
    ],
    precision: [null, null, 5, 2, 2, 2, 0, 2, 4, 3],
  };

  // Constants
  const CONTAINER = $('<div>');
  const TABLE = $('<table>');
  const HEADER_ROW = $('<tr>');
  const BUTTON = $('<button type="button">&#x2304</button>');

  // Add headers to the table
  for (const HEADER of TABLE_INFO.headers) {
    HEADER_ROW.append($(`<th>${HEADER}</th>`));
  }

  TABLE.append(HEADER_ROW);

  // Add each row of data to the table
  for (const [J, GTI] of info.entries()) {
    const DATA_ROW = $('<tr></tr>');

    // Add each table cell to the row
    for (let i = 0; i < TABLE_INFO.headers.length; i++) {
      let data = GTI[TABLE_INFO.keys[i]];

      if (TABLE_INFO.precision[i] != null) {
        data = (+data).toFixed(TABLE_INFO.precision[i]);
      }

      DATA_ROW.append($(`<td>${data}</td>`));
    }

    // Hide all but the first row
    if (J !== 0) {
      DATA_ROW.addClass('hide');
    }

    TABLE.append(DATA_ROW);
  }

  CONTAINER.append(TABLE);
  CONTAINER.append(BUTTON);

  // Add button to expand the table
  BUTTON.click(() => {
    TABLE.children().slice(2).toggleClass('hide');
    BUTTON.html(/\u2304/.test(BUTTON.html()) ? '&#x2303' : '&#x2304');
  });

  return CONTAINER;
}

/**
 * Fetches and plots GTIs from the search field for the given plot type.
 * @param {String} obsID Observation ID
 */
function fetchGTIPlot(obsID) {
  $('.fetch-gti').submit(function (e) {
    // Constants
    const REGEX = /"title":\{"text":"(.+?)"\}/;
    let serializedData = $(this).serialize();

    // Prevents reloading the page
    e.preventDefault();

    // Adds information and security token to the request
    serializedData += `&csrfmiddlewaretoken=${$(
      "input[name='csrfmiddlewaretoken']",
    ).val()}`;
    serializedData += `&quality=${quality}`;
    serializedData += `&obs_id=${obsID}`;

    // Sends an asynchronous request to generate a plot with multiple GTIs
    $.ajax({
      type: 'POST',
      url: PLOT_GTI_URL,
      data: serializedData,
      success: function (response) {
        // Gets information on the plot type
        const NAME = REGEX.exec(response.plotDivs[0])[1]
          .toLowerCase()
          .replaceAll(' ', '_');
        const PLOT_DIV = $(response.plotDivs[0]).attr('id', NAME);

        // Updates the plot with the GTIs
        $(`#${NAME}`).replaceWith(PLOT_DIV);
      },
    });
  });
}

/**
 * Generates a GTI selection field for a specific plot
 * for the user to select which GTIs to plot.
 * @param {number} maxGTI Maximum GTI number for the plot type
 * and observation ID
 * @param {String} plotType Which plot is the GTI selection field being added to
 * @returns {HTMLFormElement} HTML form element containing
 * the GTI selection field and submit button
 */
function GTISelection(maxGTI, plotType) {
  // Constants
  const FORM = $('<form class="fetch-gti">');
  const TYPE = $(`<input name="plot_type" type="hidden" value="${plotType}">`);
  const SEARCH = $(
    '<input name="gti-search" type="text" ' +
      `placeholder="GTI numbers (,) and/or range (-) between 0 and ${
        maxGTI - 1
      }">`,
  );
  const MIN_SLIDER = $(
    `<input id="${plotType}-min-slider" name="min_value" ` +
      'type="range" min="1" max="200" value="100">',
  );
  const MIN_VALUE = $(`<p id="${plotType}-min-value">Value: 100 counts</p>`);
  const SUBMIT = $('<button type="submit">Submit</button>');

  // Adds elements to the form
  FORM.append(TYPE);
  FORM.append(columnLayout([SEARCH, SUBMIT]));
  FORM.append(columnLayout([MIN_SLIDER, MIN_VALUE]));

  // Update slider value on change
  MIN_SLIDER.on('input', function () {
    $(`#${plotType}-min-value`).html(
      `Value: ${$(`#${plotType}-min-slider`).val()} counts`,
    );
  });

  return FORM;
}

/**
 * Fetches and displays the plots for the given observation ID,
 * pipeline quality, and plot types.
 */
function fetchGraphPlots() {
  $('#plot-graph').submit(function (e) {
    // Constants
    const SERIALIZED_DATA = $(this).serialize();
    const TYPE_REGEX = /"title":\{"text":"(.+?)"\}/;

    // Prevents reloading the page
    e.preventDefault();

    // Sends an asynchronous request to generate a plot with multiple GTIs
    $.ajax({
      type: 'POST',
      url: PLOT_GRAPH_URL,
      data: SERIALIZED_DATA,
      success: function (response) {
        // Recreate info table
        $('#obs-info').empty();
        $('#obs-info').append(displayInfo(response.info));
        MathJax.typeset();

        // Clears current plots
        $('#plots').empty();

        // Displays each selected plot type
        for (let i = 0; i < response.plotDivs.length; i++) {
          // Gets information on the plot type
          const TYPE = TYPE_REGEX.exec(response.plotDivs[i])[1]
            .toLowerCase()
            .replaceAll(' ', '_');
          const PLOT_DIV = $(response.plotDivs[i]).attr('id', TYPE);

          // Displays the plot and GTI selection field
          $('#plots').append(PLOT_DIV);
          $('#plots').append(GTISelection(response.maxGTI[i], TYPE));
          fetchGTIPlot(response.obsID, TYPE);
        }
      },
    });
  });
}

/**
 * Shows or hides dropdown suggestions depending if the input field is in focus.
 * @param {HTMLInputElement} field Input element which has dropdown suggestions
 * @param {HTMLDivElement} content
 * Div element containing the dropdown suggestions
 */
function dropdownFocus(field, content) {
  field.addEventListener('blur', () => {
    setTimeout(() => {
      content.classList.remove('show');
    }, 200);
  });

  field.addEventListener('focus', () => {
    content.classList.add('show');
  });
}

/**
 * Adds event listeners for all search fields with dropdown suggestions.
 */
function dropdowns() {
  const DROPDOWNS = document.getElementsByClassName('dropdown');

  for (const DROPDOWN of DROPDOWNS) {
    const DROPDOWN_FIELD = DROPDOWN.getElementsByClassName('dropdown-field')[0];
    const DROPDOWN_CONTENT =
      DROPDOWN.getElementsByClassName('dropdown-content')[0];

    dropdownFocus(DROPDOWN_FIELD, DROPDOWN_CONTENT);
  }
}

// When the page loads add event listeners for different input fields
document.addEventListener('DOMContentLoaded', () => {
  dropdowns();
  fetchGraphPlots();

  $('#observation-search').keyup(function () {
    fetchOptions(this.value);
  });

  $('.change-quality').click(function () {
    changeQuality(this.textContent);
  });
});
