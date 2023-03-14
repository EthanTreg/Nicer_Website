/* global PLOT_GRAPH_URL PLOT_GTI_URL */

function changeQuality (buttonQuality) {
  quality = buttonQuality.toLowerCase();
  document.querySelector('#quality-select').value = buttonQuality;
};

function addObservation (observationOption) {
  const OPTION = document.createElement('button');

  OPTION.setAttribute('type', 'button');
  OPTION.innerHTML = observationOption.name;

  OPTION.addEventListener('click', () => {
    document.querySelector('#observation-search').value = observationOption.name;
  });

  document.querySelector('#observation-options').append(OPTION);
};

function fetchOptions (obsID) {
  fetch(`/plots/fetch_observations?obs_id=${obsID}`)
    .then(response => response.json())
    .then(data => {
      document.querySelector('#observation-options').innerHTML = '';
      data.dir_suggestions.forEach(addObservation);
    });
};

function fetchGTI (obsID) {
  $('.fetch-gti').submit(function (e) {
    e.preventDefault();
    const REGEX = /"title":\{"text":"(.+?)"\}/;
    let serializedData = $(this).serialize();

    serializedData += `&csrfmiddlewaretoken=${$("input[name='csrfmiddlewaretoken']").val()}`;
    serializedData += `&quality=${quality}`;
    serializedData += `&obs_id=${obsID}`;

    $.ajax({
      type: 'POST',
      url: PLOT_GTI_URL,
      data: serializedData,
      success: function (response) {
        const NAME = REGEX.exec(response.plotDivs[0])[1].toLowerCase().replaceAll(' ', '_');
        const PLOT_DIV = $(response.plotDivs[0]).attr('id', NAME);

        $(`#${NAME}`).replaceWith(PLOT_DIV);
      }
    });
  });
};

function columnLayout (elements) {
  const ROW = document.createElement('div');

  ROW.classList.add('row');

  for (const ELEMENT of elements) {
    const COLUMN = document.createElement('div');

    COLUMN.classList.add('column');
    COLUMN.append(ELEMENT);
    ROW.append(COLUMN);
  }

  return ROW;
};

function GTISelection (maxGTI, plotType) {
  const FORM = document.createElement('form');
  const TYPE = document.createElement('input');
  const SEARCH = document.createElement('input');
  const SUBMIT = document.createElement('button');

  TYPE.setAttribute('type', 'hidden');
  TYPE.setAttribute('name', 'plot_type');
  TYPE.setAttribute('value', plotType);
  SEARCH.setAttribute('type', 'text');
  SEARCH.setAttribute('name', 'gti-search');
  SEARCH.setAttribute(
    'placeholder', `GTI numbers (,) and/or range (-) between 0 and ${maxGTI - 1}`
  );
  SUBMIT.setAttribute('type', 'submit');
  SUBMIT.innerHTML = 'Submit';
  FORM.classList.add('fetch-gti');

  FORM.append(TYPE);
  FORM.append(columnLayout([SEARCH, SUBMIT]));

  return FORM;
};

function fetchGraphPlots () {
  $('#plot-graph').submit(function (e) {
    const SERIALIZED_DATA = $(this).serialize();
    const REGEX = /"title":\{"text":"(.+?)"\}/;

    e.preventDefault();

    $.ajax({
      type: 'POST',
      url: PLOT_GRAPH_URL,
      data: SERIALIZED_DATA,
      success: function (response) {
        $('#plots').empty();

        for (let i = 0; i < response.plotDivs.length; i++) {
          const NAME = REGEX.exec(response.plotDivs[i])[1].toLowerCase().replaceAll(' ', '_');
          const PLOT_DIV = $(response.plotDivs[i]).attr('id', NAME);

          $('#plots').append(PLOT_DIV);
          $('#plots').append(GTISelection(response.maxGTI[i], NAME));
          fetchGTI(response.obsID);
        }
      }
    });
  });
};

function dropdownFocus (field, content) {
  field.addEventListener('blur', () => {
    setTimeout(() => {
      content.classList.remove('show');
    }, 200);
  });

  field.addEventListener('focus', () => {
    content.classList.add('show');
  });
};

function dropdowns () {
  const DROPDOWNS = document.getElementsByClassName('dropdown');

  for (const DROPDOWN of DROPDOWNS) {
    const DROPDOWN_FIELD = DROPDOWN.getElementsByClassName('dropdown-field')[0];
    const DROPDOWN_CONTENT = DROPDOWN.getElementsByClassName('dropdown-content')[0];

    dropdownFocus(DROPDOWN_FIELD, DROPDOWN_CONTENT);
  }
};

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
