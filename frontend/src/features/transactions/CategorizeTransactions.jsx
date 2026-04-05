/**
 * @file CategorizeTransactions.jsx
 * Top-level page for reviewing and categorizing imported bank
 * transactions.
 *
 * Responsibilities:
 *  - Load and own all reference data (accounts, taxonomy, uploads).
 *  - Fetch transactions with server-side filtering, sorting, and paging.
 *  - Wire up inline-edit, bulk-edit, and party-remap flows.
 *  - Surface success/error feedback via toasts.
 *
 * Child components:
 *  - {@link TransactionTable} — sortable, filterable grid.
 *  - {@link Pagination}
 *  - {@link BulkEditModal} — multi-select mass update.
 *  - {@link RemapPartyModal} — move a party to a different type.
 */

import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/components/ToastContext';
import {
  getTransactions,
  updateTransaction,
  bulkUpdateTransactions,
  generateCashTransactions,
  createCashTransaction,
  getCategories,
  getSubCategories,
  getTypes,
  getParties,
  getUploads,
  createCategory,
  createSubCategory,
  createType,
  createParty,
  remapParty,
} from './api';
import { getAccounts } from '@/features/statements/api';
import TransactionTable from './TransactionTable';
import Pagination from '@/components/Pagination';
import BulkEditModal from './BulkEditModal';
import RemapPartyModal from './RemapPartyModal';
import GenerateCashModal from './GenerateCashModal';
import CreateCashTransactionModal from './CreateCashTransactionModal';
import './CategorizeTransactions.css';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CategorizeTransactions');

/** Page size for server-side pagination. */
const ITEMS_PER_PAGE = 100;

/**
 * Main categorization view.
 *
 * @component
 * @returns {JSX.Element}
 */
export default function CategorizeTransactions() {
  const { addToast } = useToast();

  // ── Data state ────────────────────────────────────────────────────
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [types, setTypes] = useState([]);
  const [parties, setParties] = useState([]);
  const [uploads, setUploads] = useState([]);

  // ── UI state ──────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  /**
   * Approximate total — API doesn't return a count, so we infer:
   *  - If a full page is returned, assume at least one more exists.
   *  - Otherwise clamp to actual count.
   */
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [filters, setFilters] = useState({});
  const [selectedTransactions, setSelectedTransactions] = useState([]);
  const [isBulkEditOpen, setIsBulkEditOpen] = useState(false)
  const [isGenerateCashOpen, setIsGenerateCashOpen] = useState(false);
  const [isCreateCashOpen, setIsCreateCashOpen] = useState(false);
  const [sortField, setSortField] = useState('transaction_date');
  const [sortDir, setSortDir] = useState('desc');
  /**
   * When set, the remap modal is open. If a number, that party is
   * preselected; if `true`, the modal opens empty.
   * @type {?number|true}
   */
  const [remapPartyId, setRemapPartyId] = useState(null);
  /** Optional target type to pre-fill in the remap modal. */
  const [remapTargetTypeId, setRemapTargetTypeId] = useState(null);

  const isRemapOpen = remapPartyId !== null;

  // ── Effects: load data on mount / filter change ───────────────────

  useEffect(() => {
    loadReferenceData();
  }, []);

  useEffect(() => {
    loadTransactions();
  }, [filters, currentPage, sortField, sortDir]);

  // ── Data loaders ──────────────────────────────────────────────────

  /**
   * Fetch all reference (lookup) data in parallel.
   * Errors are toasted; we don't block the UI.
   */
  const loadReferenceData = async () => {
    try {
      const [
        accountsData,
        categoriesData,
        subCategoriesData,
        typesData,
        partiesData,
        uploadsData,
      ] = await Promise.all([
        getAccounts(),
        getCategories(),
        getSubCategories(),
        getTypes(),
        getParties(),
        getUploads(),
      ]);
      setAccounts(accountsData);
      setCategories(categoriesData);
      setSubCategories(subCategoriesData);
      setTypes(typesData);
      setParties(partiesData);
      setUploads(uploadsData.data || uploadsData);
    } catch (err) {
      logger.error('Error loading reference data:', err);
      addToast({
        message: `Failed to load reference data: ${err.userMessage || err.message}`,
        type: 'error',
      });
    }
  };

  /**
   * Fetch a page of transactions matching the current filters and
   * sort order. Updates `transactions` and `totalTransactions`.
   */
  const loadTransactions = async () => {
    setLoading(true);
    try {
      const cleanFilters = Object.entries(filters).reduce((acc, [key, value]) => {
        if (value !== null && value !== undefined && value !== '') acc[key] = value;
        return acc;
      }, {});

      cleanFilters.limit = ITEMS_PER_PAGE;
      cleanFilters.offset = (currentPage - 1) * ITEMS_PER_PAGE;
      if (sortField) {
        cleanFilters.sort_by = sortField;
        cleanFilters.sort_dir = sortDir;
      }

      const data = await getTransactions(cleanFilters);
      setTransactions(data);
      setTotalTransactions(
        data.length === ITEMS_PER_PAGE
          ? currentPage * ITEMS_PER_PAGE + 1
          : (currentPage - 1) * ITEMS_PER_PAGE + data.length
      );
    } catch (err) {
      logger.error('Error loading transactions:', err);
      addToast({
        message: `Failed to load transactions: ${err.userMessage || err.message}`,
        type: 'error',
      });
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  // ── Mutation handlers ─────────────────────────────────────────────

  /**
   * Persist changes to a single transaction (inline edit).
   *
   * @param {number} transactionId
   * @param {Object} updates
   * @returns {Promise<Object>} The updated transaction.
   */
  const handleTransactionUpdate = async (transactionId, updates) => {
    try {
      const updated = await updateTransaction(transactionId, updates);
      setTransactions((prev) =>
        prev.map((t) => (t.id === transactionId ? { ...t, ...updated } : t))
      );
      return updated;
    } catch (err) {
      addToast({
        message: `Failed to update transaction: ${err.userMessage || err.message}`,
        type: 'error',
      });
      throw err;
    }
  };

  /**
   * Apply `updates` to all selected transactions.
   * Called from {@link BulkEditModal}.
   */
  const handleBulkUpdate = async (updates) => {
    if (selectedTransactions.length === 0) throw new Error('No transactions selected');

    const count = selectedTransactions.length;
    setLoading(true);
    try {
      await bulkUpdateTransactions(selectedTransactions, updates);
      await loadTransactions();
      setSelectedTransactions([]);
      setIsBulkEditOpen(false);
      addToast({
        message: `Updated ${count} transaction${count === 1 ? '' : 's'}`,
        type: 'success',
        duration: 3000,
      });
    } catch (err) {
      const msg = err.message || 'Failed to update transactions';
      addToast({
        message: msg.userMessage || msg.message || 'Failed to update transactions',
        type: 'error',
      });
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  };

   /**
   * Generate Cash-account counterpart transactions for all selected
   * transactions. Called from {@link GenerateCashModal}.
   *
   * On success:
   *  - Reloads the transaction list.
   *  - Refreshes accounts (the Cash account may have just been
   *    created) and uploads (a synthetic upload record is added per
   *    batch).
   *  - Clears the selection and closes the modal.
   *  - Toasts a summary of created / skipped / rejected counts.
   */
  const handleGenerateCash = async () => {
    if (selectedTransactions.length === 0) {
      throw new Error('No transactions selected');
    }

    setLoading(true);
    try {
      const response = await generateCashTransactions(selectedTransactions);
      const result = response?.data ?? response;

      // Refresh everything affected by the generation.
      const [accountsData, uploadsData] = await Promise.all([
        getAccounts(),
        getUploads(),
      ]);
      setAccounts(accountsData);
      setUploads(uploadsData.data || uploadsData);
      await loadTransactions();

      setSelectedTransactions([]);
      setIsGenerateCashOpen(false);

      const parts = [`${result.created_count} created`];
      if (result.skipped_count > 0) parts.push(`${result.skipped_count} skipped`);
      if (result.rejected_count > 0) parts.push(`${result.rejected_count} rejected`);

      addToast({
        message: `Cash transactions: ${parts.join(', ')}`,
        type:
          result.created_count > 0
            ? result.rejected_count > 0
              ? 'warning'
              : 'success'
            : 'info',
        duration: 5000,
      });
    } catch (err) {
      logger.error('Error generating cash transactions:', err);
      addToast({
        message: `Failed to generate cash transactions: ${err.userMessage || err.message}`,
        type: 'error',
      });
      throw err;
    } finally {
      setLoading(false);
    }
  };

  /**
   * Create a single Cash-account transaction from manually entered data.
   * Called from {@link CreateCashTransactionModal}.
   */
  const handleCreateCashTransaction = async (opts) => {
    setLoading(true);
    try {
      await createCashTransaction(opts);

      // Refresh anything the new transaction could affect.
      const [accountsData, uploadsData] = await Promise.all([
        getAccounts(),
        getUploads(),
      ]);
      setAccounts(accountsData);
      setUploads(uploadsData.data || uploadsData);
      await loadTransactions();

      setIsCreateCashOpen(false);
      addToast({
        message: 'Cash transaction created',
        type: 'success',
        duration: 3000,
      });
    } catch (err) {
      logger.error('Error creating cash transaction:', err);
      addToast({
        message: `Failed to create cash transaction: ${err.userMessage || err.message}`,
        type: 'error',
      });
      throw err;
    } finally {
      setLoading(false);
    }
  };

  /**
   * Remap a party to a new parent type.
   * Called from {@link RemapPartyModal}.
   */
  const handleRemapParty = async (partyId, newTypeId) => {
    try {
      const result = await remapParty(partyId, newTypeId);
      const [partiesData] = await Promise.all([getParties(), loadTransactions()]);
      setParties(partiesData);

      const merged = result?.data?.action === 'merged';
      addToast({
        message: merged
          ? `Party merged into existing — ${result.transactions_moved ?? result.data.transactions_moved} transactions moved`
          : 'Party remapped successfully',
        type: 'success',
        duration: merged ? 5000 : 3000,
      });
      return result;
    } catch (err) {
      addToast({
        message: `Failed to remap party: ${err.userMessage || err.message}`,
        type: 'error',
      });
      throw err;
    }
  };

  // ── Create-item factory ───────────────────────────────────────────

  /**
   * Factory producing create handlers for each taxonomy level.
   *
   * Each handler:
   *  1. Calls the create API.
   *  2. Refetches the list and updates local state.
   *  3. Toasts success.
   *  4. Returns the newly created record so callers can auto-select it.
   *
   * @param {string} label - Human label for toast (e.g. "Category").
   * @param {Function} createFn - API function.
   * @param {Function} refetchFn - Refetch list from API.
   * @param {Function} setFn - State setter.
   * @param {Function} findFn - Locate the new item in the refreshed list.
   */
  const makeCreateHandler = useCallback(
    (label, createFn, refetchFn, setFn, findFn) =>
      async (...args) => {
        try {
          const response = await createFn(...args);
          const fresh = await refetchFn();
          setFn(fresh);
          addToast({
            message: `${label} "${args[0]}" created`,
            type: 'success',
            duration: 2500,
          });
          return findFn(fresh, ...args) || response;
        } catch (err) {
          throw err; // let caller (modal) handle inline error
        }
      },
    [addToast]
  );

  const handleCategoryCreated = makeCreateHandler(
    'Category',
    createCategory,
    getCategories,
    setCategories,
    (list, name) => list.find((c) => c.category === name)
  );

  const handleSubCategoryCreated = makeCreateHandler(
    'Sub-category',
    createSubCategory,
    getSubCategories,
    setSubCategories,
    (list, name, categoryId) =>
      list.find((sc) => sc.sub_category === name && sc.category_id === categoryId)
  );

  const handleTypeCreated = makeCreateHandler(
    'Type',
    createType,
    getTypes,
    setTypes,
    (list, name, subCategoryId) =>
      list.find((t) => t.type === name && t.sub_category_id === subCategoryId)
  );

  const handlePartyCreated = makeCreateHandler(
    'Party',
    createParty,
    getParties,
    setParties,
    (list, name, typeId) => list.find((p) => p.name === name && p.type_id === typeId)
  );

  // ── Misc handlers ─────────────────────────────────────────────────

  /** Replace filter state and reset to page 1. */
  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
    setCurrentPage(1);
  }, []);

  /** Navigate to a new page and clear selection. */
  const handlePageChange = (page) => {
    setCurrentPage(page);
    setSelectedTransactions([]);
  };

  /** Change sort column/direction and reset to page 1. */
  const handleSortChange = useCallback((field, dir) => {
    setSortField(field);
    setSortDir(dir);
    setCurrentPage(1);
  }, []);

  /**
   * Find an existing party by name+type, or create one if missing.
   * Used by {@link TransactionRow} when the user chooses "this txn only"
   * after a type conflict.
   */
  const handleFindOrCreateParty = useCallback(
    async (name, typeId) => {
      const existing = parties.find(
        (p) => p.name.toLowerCase() === name.toLowerCase() && p.type_id === typeId
      );
      if (existing) return existing.id;
      const newParty = await handlePartyCreated(name, typeId, '');
      return newParty.id;
    },
    [parties, handlePartyCreated]
  );

  /**
   * Open the remap-party modal.
   * @param {?number} partyId - Pre-selected party, or `null`/`true` to open empty.
   * @param {?number} targetTypeId - Optionally pre-fill target type.
   */
  const handleOpenRemap = useCallback((partyId = null, targetTypeId = null) => {
    setRemapPartyId(partyId ?? true);
    setRemapTargetTypeId(targetTypeId);
  }, []);

  const handleCloseRemap = () => {
    setRemapPartyId(null);
    setRemapTargetTypeId(null);
  };

  /**
   * Format an ISO date string for the uploads dropdown.
   * @param {?string} dateString
   * @returns {string}
   */
  const formatUploadDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    const date = new Date(dateString);
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleDateString('en-GB', { month: 'short' });
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${day} ${month}; ${hours}:${minutes}`;
  };

  const initialPartyId = typeof remapPartyId === 'number' ? remapPartyId : null;

  return (
    <div className="categorize-transactions">
      <div className="page-header">
        <h1>Categorize Transactions</h1>
        <div className="header-actions">
          <button
            onClick={() => setIsCreateCashOpen(true)}
            className="new-cash-button"
          >
            + New Cash Transaction
          </button>
          {selectedTransactions.length > 0 && (
            <>
              <button
                onClick={() => setIsBulkEditOpen(true)}
                className="bulk-edit-button"
              >
                Bulk Edit ({selectedTransactions.length})
              </button>
              <button
                onClick={() => setIsGenerateCashOpen(true)}
                className="generate-cash-button"
              >
                Generate Cash ({selectedTransactions.length})
              </button>
            </>
          )}
        </div>
      </div>

      <div className="filters-section">
        <div className="filter-group">
          <label htmlFor="upload-filter">Filter by Upload:</label>
          <select
            id="upload-filter"
            value={filters.upload_id || ''}
            onChange={(e) => {
              const value = e.target.value;
              handleFilterChange({ ...filters, upload_id: value ? parseInt(value) : null });
            }}
          >
            <option value="">All Uploads</option>
            {uploads.map((upload) => (
              <option key={upload.id} value={upload.id}>
                {upload.original_filename} — {formatUploadDate(upload.upload_date)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <TransactionTable
        transactions={transactions}
        accounts={accounts}
        categories={categories}
        subCategories={subCategories}
        types={types}
        parties={parties}
        onUpdate={handleTransactionUpdate}
        onCategoryCreated={handleCategoryCreated}
        onSubCategoryCreated={handleSubCategoryCreated}
        onTypeCreated={handleTypeCreated}
        onPartyCreated={handlePartyCreated}
        selectedTransactions={selectedTransactions}
        onSelectionChange={setSelectedTransactions}
        filters={filters}
        onFilterChange={handleFilterChange}
        onRemapParty={handleOpenRemap}
        onFindOrCreateParty={handleFindOrCreateParty}
        sortField={sortField}
        sortDir={sortDir}
        onSortChange={handleSortChange}
      />

      <Pagination
        currentPage={currentPage}
        totalItems={totalTransactions}
        itemsPerPage={ITEMS_PER_PAGE}
        onPageChange={handlePageChange}
      />

      <BulkEditModal
        isOpen={isBulkEditOpen}
        onClose={() => setIsBulkEditOpen(false)}
        onSave={handleBulkUpdate}
        transactionCount={selectedTransactions.length}
        categories={categories}
        subCategories={subCategories}
        types={types}
        parties={parties}
        onCategoryCreated={handleCategoryCreated}
        onSubCategoryCreated={handleSubCategoryCreated}
        onTypeCreated={handleTypeCreated}
        onPartyCreated={handlePartyCreated}
      />

      <RemapPartyModal
        isOpen={isRemapOpen}
        onClose={handleCloseRemap}
        onSave={handleRemapParty}
        parties={parties}
        categories={categories}
        subCategories={subCategories}
        types={types}
        onCategoryCreated={handleCategoryCreated}
        onSubCategoryCreated={handleSubCategoryCreated}
        onTypeCreated={handleTypeCreated}
        initialPartyId={initialPartyId}
        initialTypeId={remapTargetTypeId}
      />

      <GenerateCashModal
        isOpen={isGenerateCashOpen}
        onClose={() => setIsGenerateCashOpen(false)}
        onConfirm={handleGenerateCash}
        transactionCount={selectedTransactions.length}
      />
      <CreateCashTransactionModal
        isOpen={isCreateCashOpen}
        onClose={() => setIsCreateCashOpen(false)}
        onConfirm={handleCreateCashTransaction}
        categories={categories}
        subCategories={subCategories}
        types={types}
        parties={parties}
        onCategoryCreated={handleCategoryCreated}
        onSubCategoryCreated={handleSubCategoryCreated}
        onTypeCreated={handleTypeCreated}
        onPartyCreated={handlePartyCreated}
      />
    </div>
  );
}