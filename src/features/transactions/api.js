import { apiCall, unwrap } from '@/lib/apiClient';

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
  
  const response = await apiCall(url);
  
  return unwrap(response, 'transactions') || [];
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
    body
  });
  return unwrap(response, 'account') || response; // Return the created account
}

/**
 * Update a transaction
 */
export async function updateTransaction(transactionId, updates) {
  const response = await apiCall(`/transactions/${transactionId}`, {
    method: 'PUT',
    body: updates
  });
  return unwrap(response, 'transaction') || response; // Return the updated transaction
}

export async function bulkUpdateTransactions(transactionIds, updates) {
  const body = {
    transaction_ids: transactionIds,
    updates: updates
  };
  const response = await apiCall('/transactions/bulk', {
    method: 'PUT',
    body
  });
  return response;
}

/**
 * Get all categories
 */
export async function getCategories() {
  const response = await apiCall('/categories');
  return unwrap(response, 'categories');
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
  
  return unwrap(response, 'sub_categories');
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
  return unwrap(response, 'types');
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
  return unwrap(response, 'parties');
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
    body
  });
  return unwrap(response, 'category');
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
    body
  });
  return unwrap(response, 'sub_category');
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
    body
  });
  return unwrap(response, 'type');
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
    body
  });
  return unwrap(response, 'party');
}

export async function remapParty(partyId, newTypeId) {
  const body = {
    type_id: newTypeId
  };
  return apiCall(`/parties/${partyId}/remap`, {
    method: 'PUT',
    body
  });
}

/**
 * Get list of uploads, sorted by most recent first
 */
export async function getUploads() {
  return await apiCall('/uploads');
}