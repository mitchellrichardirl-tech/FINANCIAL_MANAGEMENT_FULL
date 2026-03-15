import { createLogger }  from "./logger";
import { AppError } from "./errors";
import { parseApiError, getUserMessage } from './apiErrors';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const logger = createLogger('apiClient');

export async function apiCall(endpoint, { method = 'GET', body, headers, ...rest } = {}) {
  const opts = { method, headers, ...rest };

  if (body instanceof FormData) {
    opts.body = body;                     // browser sets multipart boundary — don't touch headers
  } else if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json', ...headers };
    opts.body = JSON.stringify(body);
  }


  logger.debug(`API call: ${method} ${endpoint}`);
  logger.debug('Request options:', opts);

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, opts);
  } catch (err) {
    logger.error(`Network error during API call: ${method} ${endpoint}`, err);
    throw new AppError({
      message: `Network error: ${err.message}`,
      userMessage: 'Unable to reach the server. Check your connection and try again.',
      cause: err,
    });
  }

  if (!response.ok) {
    const parsed = await parseApiError(response);
    parsed.userMessage = getUserMessage(parsed, `API error during ${method} ${endpoint}`);
    logger.warn('API error', {
      endpoint,
      method,
      status: response.status,
      body: parsed.userMessage,
    });
    
    throw new ApiError(parsed);
  }

  const data = await response.json();
  logger.debug(`API response: ${method} ${endpoint}`, data);
  
  return data;
}

export function unwrap(response, key) {
  if (response?.data?.[key] !== undefined) return response.data[key];
  if (response?.[key] !== undefined) return response[key];
  if (response?.data !== undefined) return response.data;
  return response;
}

class ApiError extends Error {
  constructor(parsed) {
    super(parsed.message);
    this.name = 'ApiError';
    this.code = parsed.code;
    this.field = parsed.field;
    this.entity = parsed.entity;
    this.details = parsed.details;
    this.status = parsed.status;
    this.userMessage = parsed.userMessage ?? getUserMessage(parsed);  // reuse if already set
  }
}