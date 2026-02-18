
const API_BASE_URL = 'http://localhost:5000/api';

/**
 * Generic API call handler with error handling
 */
async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || 'API request failed');
    }

    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

/**
 * Get all accounts
 */
export async function getAccounts() {
  const response = await apiCall('/accounts');
  // Keep backward compatibility - extract data array if it exists
  return response.data || response;
}

/**
 * Preview a tabular file
 */
export async function previewFile(file, numRows = 20) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('num_rows', numRows);
  formData.append('include_types', 'true');

  return await apiCall('/tabular/preview', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Import a tabular file
 */
export async function importFile(file, startRow, accountId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('start_row', startRow.toString());
  formData.append('account_id', parseInt(accountId).toString());
  formData.append('has_header', 'true');
  formData.append('skip_empty_rows', 'true');
  formData.append('strip_whitespace', 'true');
  formData.append('original_filename', file.name);

  console.log('Import request:', {
    url: '/tabular/import',
    startRow,
    accountId: parseInt(accountId),
    fileName: file.name
  });

  return await apiCall('/tabular/import', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Get transactions with optional filters
 */
export async function getTransactions(filters = {}) {
  const params = new URLSearchParams();
  
  // Add filters to query params
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      params.append(key, value);
    }
  });
  
  const queryString = params.toString();
  const url = `/transactions${queryString ? '?' + queryString : ''}`;
  
  console.log('Get Transactions URL:', url);
  
  const response = await apiCall(url);
  
  // Extract transactions from nested structure
  if (response && response.data && response.data.transactions) {
    return response.data.transactions;
  } else if (response && response.transactions) {
    return response.transactions;
  } else if (Array.isArray(response)) {
    return response;
  } else {
    console.error('Unexpected response format:', response);
    return [];
  }
}

/**
 * Create a new account
 */
export async function createAccount(accountName, accountType, statementFormat = null) {
  const body = {
    account_name: accountName,
    account_type: accountType
  };
  if (statementFormat) {
    body.statement_format = statementFormat;
  }

  const response = await apiCall('/accounts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  return response.data || response; // Return the created account
}

/**
 * Update a transaction
 */
export async function updateTransaction(transactionId, updates) {
  const response = await apiCall(`/transactions/${transactionId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });
  // Handle nested response
  if (response && response.data && response.data.transaction) {
    return response.data.transaction;
  } else if (response && response.transaction) {
    return response.transaction;
  } else if (response && response.data) {
    return response.data;
  } else {
    return response;
  }
}


/**
 * Get all categories
 */
export async function getCategories() {
  const response = await apiCall('/categories');
  // Handle nested structure
  if (response && response.data && response.data.categories) {
    return response.data.categories;
  } else if (response && response.categories) {
    return response.categories;
  } else if (response && response.data) {
    return response.data;
  } else {
    return response || [];
  }
}

/**
 * Get sub-categories, optionally filtered by category
 */
export async function getSubCategories(categoryId = null) {
  const params = new URLSearchParams();
  if (categoryId) params.append('category_id', categoryId);
  
  const queryString = params.toString();
  const url = `/sub-categories${queryString ? '?' + queryString : ''}`;
  
  const response = await apiCall(url);
  // Handle nested structure
  if (response && response.data && response.data.sub_categories) {
    return response.data.sub_categories;
  } else if (response && response.sub_categories) {
    return response.sub_categories;
  } else if (response && response.data) {
    return response.data;
  } else {
    return response || [];
  }
}

/**
 * Get types, optionally filtered by sub-category
 */
export async function getTypes(subCategoryId = null) {
  const params = new URLSearchParams();
  if (subCategoryId) params.append('sub_category_id', subCategoryId);
  
  const queryString = params.toString();
  const url = `/types${queryString ? '?' + queryString : ''}`;
  
  const response = await apiCall(url);
  // Handle nested structure
  if (response && response.data && response.data.types) {
    return response.data.types;
  } else if (response && response.types) {
    return response.types;
  } else if (response && response.data) {
    return response.data;
  } else {
    return response || [];
  }
}

/**
 * Get parties, optionally filtered by type
 */
export async function getParties(typeId = null) {
  const params = new URLSearchParams();
  if (typeId) params.append('type_id', typeId);
  
  const queryString = params.toString();
  const url = `/parties${queryString ? '?' + queryString : ''}`;
  
  const response = await apiCall(url);
  // Handle nested structure
  if (response && response.data && response.data.parties) {
    return response.data.parties;
  } else if (response && response.parties) {
    return response.parties;
  } else if (response && response.data) {
    return response.data;
  } else {
    return response || [];
  }
}

/**
 * Create a new category
 */
export async function createCategory(category, description = null) {
  const body = {
    category
  };
  
  // Only add description if it's provided and not empty
  if (description && description.trim()) {
    body.description = description.trim();
  }
  
  const response = await apiCall('/categories', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return response.category || response;
}

/**
 * Create a new sub-category
 */
export async function createSubCategory(subCategory, categoryId, description = null) {
  const body = {
    sub_category: subCategory,
    category_id: categoryId
  };
  
  // Only add description if it's provided and not empty
  if (description && description.trim()) {
    body.description = description.trim();
  }
  
  const response = await apiCall('/sub-categories', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return response.sub_category || response;
}

/**
 * Create a new type
 */
export async function createType(type, subCategoryId, description = null) {
  const body = {
    type,
    sub_category_id: subCategoryId
  };
  
  // Only add description if it's provided and not empty
  if (description && description.trim()) {
    body.description = description.trim();
  }
  
  const response = await apiCall('/types', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return response.type || response;
}

/**
 * Create a new party
 */
export async function createParty(name, typeId, description = null) {
  const body = {
    name,
    type_id: typeId
  };
  
  // Only add description if it's provided and not empty
  if (description && description.trim()) {
    body.description = description.trim();
  }
  
  const response = await apiCall('/parties', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return response.party || response;
}

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
  console.log('API url: ', `/receipts/${receiptId}/image`);
  return await apiCall(`/receipts/${receiptId}/image`, {
    method: 'GET'
  });
}

/**
 * Confirm receipt attributes
 */
export const confirmReceipt = async (receiptData) => {
  const response = await fetch('/api/receipts/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(receiptData)
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || 'Failed to save receipt');
  }

  return response.json();
};

/**
 * Delete receipt
 */
export const deleteReceipt = async(receiptId) => {
  console.log('API url: ', `/receipts/${receiptId.receiptId}/cancel`);
  return await apiCall(`/receipts/${receiptId.receiptId}/cancel`, {
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
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params)
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

export async function fetchStatementFormats() {
  const response = await apiCall('/accounts/statement-formats');
  return response.data || response;
}