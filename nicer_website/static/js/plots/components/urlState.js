export const plotState = {
    requests: []
};

function base64UrlEncode(str) {
    return btoa(str).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

function base64UrlDecode(str) {
    str = str.replace(/-/g, '+').replace(/_/g, '/');
    while (str.length % 4) str += '=';
    return atob(str);
}

export function updateUrlWithState() {
    const params = new URLSearchParams();
    plotState.requests.forEach((req, i) => {
        // Always store the request query as a compact base64url-encoded value
        const encoded = base64UrlEncode(req.query);
        params.set('req' + i, req.type + '|b64:' + encoded);
    });
    
    // Also include the search type and main obs_id so the text boxes stay populated
    const mainObs = document.getElementById('observation-search')?.value;
    const searchType = document.getElementById('search-type')?.value;
    if (mainObs) params.set('obs_id', mainObs);
    if (searchType) params.set('obs_search', searchType);
    
    const newUrl = window.location.pathname + '?' + params.toString();
    window.history.replaceState(null, '', newUrl);
}

export function addPlotRequest(type, queryString) {
    // clean csrf from query string
    queryString = queryString.replace(/&?csrfmiddlewaretoken=[^&]*/g, '').replace(/^&/, '');
    
    // check if it's already there to prevent duplicates
    const exists = plotState.requests.find(r => r.type === type && r.query === queryString);
    if (!exists) {
        plotState.requests.push({ type, query: queryString });
        updateUrlWithState();
    }
}

export function clearPlotRequests() {
    plotState.requests = [];
    updateUrlWithState();
}

export function removePlotRequestByObsId(obsId) {
    const startLen = plotState.requests.length;
    plotState.requests = plotState.requests.filter(req => {
        const params = new URLSearchParams(req.query);
        const reqObsIds = params.getAll('obs_id');
        const reqCombinedIds = params.getAll('combined_obs_ids');
        
        if (reqObsIds.includes(String(obsId))) return false;
        
        // Also check if it's in a combined list
        if (reqCombinedIds.some(c => c.split(' ').includes(String(obsId)))) return false;
        
        return true;
    });
    if (plotState.requests.length !== startLen) {
        updateUrlWithState();
    }
}

export function removePlotRequestByGti(obsId, gtiSearch) {
    if(!gtiSearch) return removePlotRequestByObsId(obsId);
    
    const startLen = plotState.requests.length;
    plotState.requests = plotState.requests.filter(req => {
        const params = new URLSearchParams(req.query);
        if (params.get('obs_id') === String(obsId) && params.get('gti-search') === String(gtiSearch)) {
            return false;
        }
        return true;
    });
    if (plotState.requests.length !== startLen) {
        updateUrlWithState();
    }
}
