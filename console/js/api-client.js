/**
 * api-client.js -- Fetch wrapper with X-User/X-Role headers and SSE factory.
 *
 * All API calls go through this module so auth headers are attached
 * consistently. The SSE factory creates EventSource connections with
 * query-param auth (since EventSource can't send headers).
 */

const ApiClient = (() => {

  const BASE = '';  // Same origin — API served by FastAPI

  /**
   * Get the currently selected role from the nav selector.
   * @returns {{user: string, role: string}}
   */
  function getAuth() {
    const roleEl = document.getElementById('roleSelect');
    const role = roleEl ? roleEl.value : 'viewer';
    return { user: role, role: role };
  }

  /**
   * Fetch wrapper that attaches X-User and X-Role headers.
   * @param {string} path - API path, e.g., "/api/nodes"
   * @param {object} options - fetch options
   * @returns {Promise<Response>}
   */
  async function apiFetch(path, options = {}) {
    const auth = getAuth();
    const headers = {
      'Content-Type': 'application/json',
      'X-User': auth.user,
      'X-Role': auth.role,
      ...(options.headers || {}),
    };
    const resp = await fetch(BASE + path, { ...options, headers });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(body.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  /** GET shorthand */
  function get(path) { return apiFetch(path); }

  /** POST shorthand */
  function post(path, body = {}) {
    return apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
  }

  /**
   * Create an EventSource for SSE streaming.
   * Auth is passed as query params since EventSource can't send headers.
   * @param {string} path
   * @returns {EventSource}
   */
  function createSSE(path) {
    const auth = getAuth();
    const url = `${BASE}${path}?x_user=${auth.user}&x_role=${auth.role}`;
    return new EventSource(url);
  }

  return { get, post, createSSE, getAuth };
})();
