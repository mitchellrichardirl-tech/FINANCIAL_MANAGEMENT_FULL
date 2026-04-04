/**
 * @file features/transactions/api.js
 * HTTP wrappers for transactions and the categorization taxonomy.
 *
 * The taxonomy is a four-level hierarchy:
 *   Category → SubCategory → Type → Party
 * Each `get*` reader optionally filters by its parent id; each
 * `create*` writer takes the new name, its parent id, and an optional
 * description (trimmed; omitted when blank).
 */

import { apiCall, unwrap } from '@/lib/apiClient';

/**
 * Filters accepted by {@link getTransactions}. Keys map 1:1 to the
 * backend's query parameters; `null`/`undefined` values are skipped.
 *
 * @typedef {Object} TransactionFilters
 * @property {number|string} [account_id]
 * @property {number|string} [category_id]
 * @property {number|string} [sub_category_id]
 * @property {number|string} [type_id]
 * @property {number|string} [party_id]
 * @property {string} [start_date] - ISO date (inclusive).
 * @property {string} [end_date]   - ISO date (inclusive).
 * @property {number} [limit]
 * @property {number} [offset]
 */

/**
 * Fetch transactions, optionally filtered.
 *
 * @async
 * @param {TransactionFilters} [filters={}]
 * @returns {Promise<Array<Object>>} Transaction records (envelope
 *          stripped); `[]` if the response is empty/unkeyed.
 * @throws {AppError|ApiError}
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
 * Create a new account.
 *
 * @async
 * @param {string} accountName - Display name.
 * @param {string} accountType - Backend account-type enum value.
 * @param {?string} [statementFormat=null] - Optional statement-format key.
 * @returns {Promise<Object>} The created account record.
 * @throws {AppError|ApiError}
 * @see module:features/statements/api.createAccount (duplicate definition)
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
 * Patch a single transaction.
 *
 * @async
 * @param {number|string} transactionId
 * @param {Object} updates
 *        Partial transaction fields to change (e.g.
 *        `{ category_id, party_id, description }`).
 * @returns {Promise<Object>} The updated transaction record.
 * @throws {AppError|ApiError}
 */
export async function updateTransaction(transactionId, updates) {
  const response = await apiCall(`/transactions/${transactionId}`, {
    method: 'PUT',
    body: updates
  });
  return unwrap(response, 'transaction') || response; // Return the updated transaction
}

/**
 * Apply the same field updates to many transactions at once.
 *
 * @async
 * @param {Array<number|string>} transactionIds - Ids to modify.
 * @param {Object} updates - Partial fields applied to every listed id.
 * @returns {Promise<Object>} Raw API response (typically a summary of
 *          affected rows).
 * @throws {AppError|ApiError}
 */
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
 * Generate Cash-account counterpart transactions for the given
 * source transactions.
 *
 * For each source transaction, the backend creates a mirror
 * transaction on the Cash account with the amount negated and a
 * `source_transaction_id` link back to the original. Sources already
 * on the Cash account are rejected; sources that already have a
 * counterpart are skipped.
 *
 * @async
 * @param {Array<number|string>} transactionIds - Source transaction ids.
 * @returns {Promise<Object>} Raw API response. The payload (under
 *          `.data` when enveloped) contains:
 *          `{ created_count, skipped_count, rejected_count,
 *             upload_id, transactions, skipped_ids, rejected_ids }`.
 * @throws {AppError|ApiError}
 */
export async function generateCashTransactions(transactionIds) {
  return apiCall('/transactions/generate-cash', {
    method: 'POST',
    body: { transaction_ids: transactionIds },
  });
}

/**
 * Fetch all top-level categories.
 *
 * @async
 * @returns {Promise<Array<Object>>}
 * @throws {AppError|ApiError}
 */
export async function getCategories() {
  const response = await apiCall('/categories');
  return unwrap(response, 'categories');
}

/**
 * Fetch sub-categories, optionally scoped to a parent category.
 *
 * @async
 * @param {?(number|string)} [categoryId=null] - Parent category filter.
 * @returns {Promise<Array<Object>>}
 * @throws {AppError|ApiError}
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
 * Fetch types, optionally scoped to a parent sub-category.
 *
 * @async
 * @param {?(number|string)} [subCategoryId=null] - Parent sub-category filter.
 * @returns {Promise<Array<Object>>}
 * @throws {AppError|ApiError}
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
 * Fetch parties (merchants/payees), optionally scoped to a parent type.
 *
 * @async
 * @param {?(number|string)} [typeId=null] - Parent type filter.
 * @returns {Promise<Array<Object>>}
 * @throws {AppError|ApiError}
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
 * Create a top-level category.
 *
 * @async
 * @param {string} category - Category name.
 * @param {?string} [description=null] - Optional description; trimmed,
 *        and omitted from the request when blank.
 * @returns {Promise<Object>} The created category record.
 * @throws {AppError|ApiError}
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
 * Create a sub-category under a category.
 *
 * @async
 * @param {string} subCategory - Sub-category name.
 * @param {number|string} categoryId - Parent category id.
 * @param {?string} [description=null] - Optional description (trimmed;
 *        omitted when blank).
 * @returns {Promise<Object>} The created sub-category record.
 * @throws {AppError|ApiError}
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
 * Create a type under a sub-category.
 *
 * @async
 * @param {string} type - Type name.
 * @param {number|string} subCategoryId - Parent sub-category id.
 * @param {?string} [description=null] - Optional description (trimmed;
 *        omitted when blank).
 * @returns {Promise<Object>} The created type record.
 * @throws {AppError|ApiError}
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
 * Create a party (merchant/payee) under a type.
 *
 * @async
 * @param {string} name - Party display name.
 * @param {number|string} typeId - Parent type id.
 * @param {?string} [description=null] - Optional description (trimmed;
 *        omitted when blank).
 * @returns {Promise<Object>} The created party record.
 * @throws {AppError|ApiError}
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

/**
 * Move an existing party to a different parent type.
 *
 * Used by the "remap party" flow when the user decides a merchant was
 * classified under the wrong type and wants to re-parent it (and, on
 * the backend, cascade that change to its transactions).
 *
 * @async
 * @param {number|string} partyId - Party to move.
 * @param {number|string} newTypeId - Destination type id.
 * @returns {Promise<Object>} Raw API response.
 * @throws {AppError|ApiError}
 */
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
 * List prior upload batches, newest first.
 *
 * @async
 * @returns {Promise<Object>} Raw API response containing the upload history.
 * @throws {AppError|ApiError}
 */
export async function getUploads() {
  return await apiCall('/uploads');
}