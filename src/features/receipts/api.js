import { apiCall, unwrap } from '@/lib/apiClient';

/**
 * Process receipt image
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
 * Get receipt image
 */
export async function getReceiptImage(receiptId) {
  return await apiCall(`/receipts/${receiptId}/image`);
}

/**
 * Confirm receipt attributes
 */
export const confirmReceipt = (receiptData) =>
  apiCall('/receipts/confirm', {
    method: 'POST',
    body: receiptData,
  });

/**
 * Delete receipt
 */
export const deleteReceipt = async(receiptId) => {
  return await apiCall(`/receipts/${receiptId}/cancel`, {
    method: 'POST'
  });
}

/**
 * Get candidate transactions for a receipt
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
 * Upload multiple receipt files using the upload-stream endpoint
 */
export async function uploadReceiptsStream(formData) {
  // Return the fetch response directly for streaming
  return await apiCall('/receipts/upload-stream', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Get list of uploads, sorted by most recent first
 */
export async function getUploads() {
  return await apiCall('/uploads');
}