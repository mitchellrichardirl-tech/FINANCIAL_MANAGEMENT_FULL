const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export async function apiCall(endpoint, { method = 'GET', body, headers, ...rest } = {}) {
  const opts = { method, headers, ...rest };

  if (body instanceof FormData) {
    opts.body = body;                     // browser sets multipart boundary — don't touch headers
  } else if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json', ...headers };
    opts.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, opts);

  // Handle errors first — try to extract a JSON message, but don't crash if the
  // error response isn't JSON (e.g. Flask debug HTML page on a 500)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      message = data.error || data.message || message;
    } catch { /* wasn't JSON — status text is the best we've got */ }
    throw new Error(message);
  }

  return response.json();
}

export function unwrap(response, key) {
  if (response?.data?.[key] !== undefined) return response.data[key];
  if (response?.[key] !== undefined) return response[key];
  if (response?.data !== undefined) return response.data;
  return response;
}