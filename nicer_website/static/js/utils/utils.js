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
 * Generates a grid layout with a column for each element input.
 *
 * Supports jQuery.
 * @param {Array.<HTMLElement>} elements
 * List of HTML elements to spread over a column layout
 * @returns {HTMLDivElement}
 * Grid layout as an HTML div element
 * containing columns with each inputted element
 */
export function columnLayout(elements) {
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
 * Adds event listeners for all search fields with dropdown suggestions.
 */
export function dropdowns() {
  const DROPDOWNS = document.getElementsByClassName('dropdown');

  for (const DROPDOWN of DROPDOWNS) {
    const DROPDOWN_FIELD = DROPDOWN.getElementsByClassName('dropdown-field')[0];
    const DROPDOWN_CONTENT =
      DROPDOWN.getElementsByClassName('dropdown-content')[0];

    dropdownFocus(DROPDOWN_FIELD, DROPDOWN_CONTENT);
  }
}
