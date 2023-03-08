var quality;

function changeQuality(button) {
    quality = button.textContent.toLowerCase();
    
    document.querySelector('#quality-select').value = button.textContent;
};

function addObservation(observation_option) {
    const OPTION = document.createElement('button');
    const OPTION_TEXT = document.createTextNode(observation_option.name);

    OPTION.appendChild(OPTION_TEXT);

    OPTION.addEventListener('click', () => {
        const OBSERVATION_SEARCH = document.querySelector('#observation-search')
        let observation_text = OBSERVATION_SEARCH.value.split('/').slice(0, -1).join('/') + '/'
        OBSERVATION_SEARCH.value = observation_text + observation_option.name;
    });

    document.querySelector('#observation-options').append(OPTION);
};

function fetchOptions(path) {
    path = path.value
    fetch(`/plots/fetch_observations?path=${path}`)
    .then(response => response.json())
    .then(data => {
        document.querySelector('#observation-options').innerHTML = '';
        data.dir_suggestions.forEach(addObservation);
    })
};

document.addEventListener('DOMContentLoaded', () => {
    const DROPDOWNS = document.getElementsByClassName('dropdown');
    
    for (let i = 0; i < DROPDOWNS.length; i++) {
        const DROPDOWN_FIELD = DROPDOWNS[i].getElementsByClassName('dropdown-field')[0];
        const DROPDOWN_CONTENT = DROPDOWNS[i].getElementsByClassName('dropdown-content')[0];

        DROPDOWN_FIELD.addEventListener('blur', () => {
            setTimeout(() => {
                DROPDOWN_CONTENT.classList.remove('show');
            }, 200);
        })
        
        DROPDOWN_FIELD.addEventListener('focus', () => {
            DROPDOWN_CONTENT.classList.add('show');
        })
    }
})