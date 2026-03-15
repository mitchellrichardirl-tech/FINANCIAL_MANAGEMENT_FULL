const STATUS_MESSAGES = {
  400: 'The request was invalid.',
  401: 'Your session has expired. Please log in again.',
  403: "You don't have permission to do this.",
  404: 'The requested resource was not found.',
  409: 'This conflicts with an existing record.',
  422: 'Please check your input and try again.',
  429: 'Too many requests. Please wait a moment.',
  500: 'Something went wrong on the server.',
  502: 'The server is temporarily unavailable.',
  503: 'The server is temporarily unavailable.',
};

export class AppError extends Error {
  constructor({ message, userMessage, status, context, cause }) {
    super(message);
    this.name = 'AppError';
    this.userMessage = userMessage || STATUS_MESSAGES[status] || 'Something went wrong.';
    this.status = status || null;
    this.context = context || null;
    this.cause = cause || null;
  }
}