/**
 * @file features/receipts/api.js
 * HTTP wrappers for the receipt-processing endpoints.
 *
 * Covers the receipt lifecycle: upload an image/PDF for OCR + parsing,
 * review the extracted attributes, find the matching bank transaction,
 * and confirm (link) or discard the receipt.
 *
 * All functions delegate to {@link apiCall} and therefore throw
 * `AppError` on network failure or `ApiError` on non-2xx responses.
 */

import { apiCall } from '@/lib/apiClient';

/**
 * Upload a single receipt file for server-side extraction.
 *
 * The backend OCRs/parses the file and returns the extracted
 * attributes (vendor, date, amount, line items, …) plus a receipt id
 * used by {@link confirmReceipt} / {@link deleteReceipt}.
 *
 * @async
 * @param {File} file - Receipt image or PDF selected by the user.
 * @returns {Promise<Object>} Raw API response containing the parsed receipt.
 * @throws {AppError|ApiError}
 */
export async function processReceiptImage(file) {
  const formData = new FormData();
  formData.append('file', file);

  return await apiCall('/receipts/upload', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Fetch the stored image metadata/URL for a previously uploaded receipt.
 *
 * @async
 * @param {number|string} receiptId - Receipt identifier.
 * @returns {Promise<Object>} Raw API response.
 * @throws {AppError|ApiError}
 */
export async function getReceiptImage(receiptId) {
  return await apiCall(`/receipts/${receiptId}/image`);
}

/**
 * Confirm (persist) a receipt's extracted attributes and link it to a
 * transaction.
 *
 * Typically called after the user has reviewed/edited the OCR output
 * and picked a matching transaction from
 * {@link getCandidateTransactions}.
 *
 * @param {Object} receiptData
 *        Finalized receipt payload. Shape is defined by the backend
 *        (`/receipts/confirm`); commonly includes `receipt_id`,
 *        `transaction_id`, and the corrected attribute fields.
 * @returns {Promise<Object>} Raw API response.
 * @throws {AppError|ApiError}
 */
export const confirmReceipt = (receiptData) =>
  apiCall('/receipts/confirm', {
    method: 'POST',
    body: receiptData,
  });

/**
 * Discard a pending receipt and its uploaded file.
 *
 * @async
 * @param {number|string} receiptId - Receipt identifier.
 * @returns {Promise<Object>} Raw API response.
 * @throws {AppError|ApiError}
 */
export const deleteReceipt = async (receiptId) => {
  return await apiCall(`/receipts/${receiptId}/cancel`, {
    method: 'POST'
  });
};

/**
 * Search for bank transactions likely to match a parsed receipt.
 *
 * Builds a `/transactions/search` query from the receipt's extracted
 * fields. `amount` is negated before sending because receipts record a
 * positive spend while transactions store outflows as negative values.
 *
 * @async
 * @param {Object} receiptData - Extracted receipt attributes.
 * @param {string} [receiptData.date]   - Receipt date → `transaction_date` filter.
 * @param {number} [receiptData.amount] - Receipt total; sent as `amount * -1`.
 * @param {string} [receiptData.vendor] - Vendor name → `party_name` filter.
 * @returns {Promise<Object>} Raw API response containing candidate transactions.
 * @throws {AppError|ApiError}
 */
export const getCandidateTransactions = async (receiptData) => {
  const params = {};
  if (receiptData.date) params.transaction_date = receiptData.date;
  if (receiptData.amount) params.amount = receiptData.amount * -1;
  if (receiptData.vendor) params.party_name = receiptData.vendor;
  return await apiCall('/transactions/search', {
    method: 'POST',
    body: params
  });
};

/**
 * Bulk-upload multiple receipt files via the streaming endpoint.
 *
 * Caller is expected to have already assembled the `FormData`
 * (e.g. one `file` entry per receipt).
 *
 * @async
 * @param {FormData} formData - Multipart payload of receipt files.
 * @returns {Promise<Object>} Raw API response.
 * @throws {AppError|ApiError}
 */
export async function uploadReceiptsStream(formData) {
  // Return the fetch response directly for streaming
  return await apiCall('/receipts/upload-stream', {
    method: 'POST',
    body: formData,
  });
}

/**
 * List prior upload batches, newest first.
 *
 * @async
 * @returns {Promise<Object>} Raw API response containing the upload history.
 * @throws {AppError|ApiError}
 */
export async function getUploads() {
  return await apiCall('/uploads');
}