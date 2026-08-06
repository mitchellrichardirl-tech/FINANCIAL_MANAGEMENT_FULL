import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/components/ToastContext';
import {
  getTransactions,
  updateTransaction,
  bulkUpdateTransactions,
  generateCashTransactions,
  bulkDeleteTransactions,
  restoreTransaction,
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
import { unwrap } from '@/lib/apiClient';
import TransactionTable from './TransactionTable';
import Pagination from '@/components/Pagination';
import DeleteTransactionsModal from './DeleteTransactionsModal';
import BulkEditModal from './BulkEditModal';
import RemapPartyModal from './RemapPartyModal';
import GenerateCashModal from './GenerateCashModal';
import CreateCashTransactionModal from './CreateCashTransactionModal';
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CategorizeTransactions');
/** Page size for server-side pagination. */
const ITEMS_PER_PAGE = 100;
/* ── Header action buttons ─────────────────────────────────────────── */
const ACTION_BTN =
  'cursor-pointer rounded px-5 py-2.5 text-sm font-medium text-white transition-colors';
/**
 * Secondary variant for "+ New Cash Transaction".
 * NOTE: the old CSS had no `.new-cash-button` rule, so this button was
 * relying on native browser chrome. Preflight removes that, so it needs
 * explicit styling. Neutral treatment chosen because it's the
 * always-visible action, unlike the two selection-contextual buttons.
 */
const ACTION_BTN_SECONDARY =
  'cursor-pointer rounded border border-gray-300 bg-white px-5 py-2.5 text-sm ' +
  'font-medium text-gray-800 transition-colors hover:bg-gray-50';
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
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [filters, setFilters] = useState({});
  const [selectedTransactions, setSelectedTransactions] = useState([]);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isBulkEditOpen, setIsBulkEditOpen] = useState(false)
  const [isGenerateCashOpen, setIsGenerateCashOpen] = useState(false);
  const [isCreateCashOpen, setIsCreateCashOpen] = useState(false);
  const [sortField, setSortField] = useState('transaction_date');
  const [sortDir, setSortDir] = useState('desc');
  const [remapPartyId, setRemapPartyId] = useState(null);
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
      const data = await getTransactions(cleanFilters)
      const rows = unwrap(data, 'transactions')
      const pagination = unwrap(data, 'pagination')
      // With a real total we can jump straight to the last valid page rather
      // than stranding the user on an empty one after a delete.
      const lastPage = Math.max(1, Math.ceil(pagination.total / ITEMS_PER_PAGE));
      if (currentPage > lastPage) {
        setCurrentPage(lastPage);   // effect refires with the corrected page
        return;
      }
      setTransactions(rows);
      setTotalTransactions(pagination.total);
    } catch (err) {
      logger.error('Error loading transactions:', err);
      addToast({
        message: `Failed to load transactions: ${err.userMessage || err.message}`,
        type: 'error',
      });
      setTransactions([]);
      setTotalTransactions(0);
    } finally {
      setLoading(false);
    }
  };
  
  // ── Mutation handlers ─────────────────────────────────────────────
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

  const handleDeleteTransactions = async () => {
    if (selectedTransactions.length === 0) {
      throw new Error('No transactions selected');
    }
    setIsDeleting(true);
    try {
      const response = await bulkDeleteTransactions(selectedTransactions);
      const result = response?.data ?? response;
      // Optimistically remove affected rows so the table updates instantly.
      const removedIds = new Set([
        ...(result.deleted_ids ?? []),
        ...(result.cascaded_ids ?? []),
      ]);
      setTransactions((prev) => prev.filter((t) => !removedIds.has(t.id)));
      setSelectedTransactions([]);
      setIsDeleteOpen(false);
      const parts = [`${result.deleted_count} deleted`];
      if (result.cascaded_ids?.length > 0) {
        parts.push(`${result.cascaded_ids.length} linked cash transaction(s) also deleted`);
      }
      if (result.skipped_ids?.length > 0) {
        parts.push(`${result.skipped_ids.length} skipped`);
      }
      addToast({
        message: `Transactions: ${parts.join(' · ')}`,
        type: result.deleted_count > 0 ? 'success' : 'info',
        duration: 5000,
      });
      // An upload disappears from the list once its last live transaction is
      // deleted. If that's the one currently being filtered on, the select
      // silently falls back to "All Uploads" while filters.upload_id still
      // points at the dead id — so clear it explicitly.
      const freshUploads = await refreshUploads();
      const selectedUploadId = filters.upload_id;
      // A controlled <select> whose value has no matching <option> renders as the
      // first option while the state says otherwise. Derive the value so the
      // control can never display something different from what's being filtered.
      const uploadFilterValue = uploads.some((u) => u.id === filters.upload_id)
        ? String(filters.upload_id)
        : '';
      const uploadFilterStale =
        Boolean(selectedUploadId) &&
        !freshUploads.some((u) => u.id === selectedUploadId);
      if (uploadFilterStale) {
        logger.info(
          `Upload ${selectedUploadId} has no live transactions left; clearing filter`
        );
        // Do NOT call loadTransactions() here. It closes over the current
        // render's `filters`, which still holds the dead upload_id. Updating
        // the filter re-runs the effect with a fresh closure.
        handleFilterChange({ ...filters, upload_id: null });
        addToast({
          message: 'Showing all uploads — the selected upload has no transactions left',
          type: 'info',
          duration: 4000,
        });
      } else {
        // Filter is still valid; reload to fix pagination counts and pick up
        // any cascaded removals the optimistic pass missed.
        await loadTransactions();
      }
    } catch (err) {
      logger.error('Error deleting transactions:', err);
      addToast({
        message: `Failed to delete transactions: ${err.userMessage || err.message}`,
        type: 'error',
      });
      throw err;
    } finally {
      setIsDeleting(false);
    }
  };

  const handleGenerateCash = async () => {
    if (selectedTransactions.length === 0) {
      throw new Error('No transactions selected');
    }
    setLoading(true);
    try {
      const response = await generateCashTransactions(selectedTransactions);
      const result = response?.data ?? response;
      const [accountsData] = await Promise.all([getAccounts(), refreshUploads()]);
      setAccounts(accountsData);
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
  const handleCreateCashTransaction = async (opts) => {
    setLoading(true);
    try {
      await createCashTransaction(opts);
      const [accountsData] = await Promise.all([getAccounts(), refreshUploads()]);
      setAccounts(accountsData);
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

  /**
   * Refetch uploads and return the fresh list.
   *
   * Uploads whose transactions have all been soft-deleted are filtered out
   * server-side, so the list can shrink after a delete and grow after a
   * restore.
   *
   * @returns {Promise<Array<{id: number, original_filename: string, upload_date: string}>>}
   */
  const refreshUploads = useCallback(async () => {
    const uploadsData = await getUploads();
    const fresh = uploadsData.data || uploadsData;
    setUploads(fresh);
    return fresh;
  }, []);

  // ── Create-item factory ───────────────────────────────────────────
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
    'Category', createCategory, getCategories, setCategories,
    (list, name) => list.find((c) => c.category === name)
  );
  const handleSubCategoryCreated = makeCreateHandler(
    'Sub-category', createSubCategory, getSubCategories, setSubCategories,
    (list, name, categoryId) =>
      list.find((sc) => sc.sub_category === name && sc.category_id === categoryId)
  );
  const handleTypeCreated = makeCreateHandler(
    'Type', createType, getTypes, setTypes,
    (list, name, subCategoryId) =>
      list.find((t) => t.type === name && t.sub_category_id === subCategoryId)
  );
  const handlePartyCreated = makeCreateHandler(
    'Party', createParty, getParties, setParties,
    (list, name, typeId) => list.find((p) => p.name === name && p.type_id === typeId)
  );
  const handleReceiptChange = (updatedTransaction) => {
    setTransactions((prevTransactions) =>
      prevTransactions.map((txn) =>
        txn.id === updatedTransaction.id ? { ...txn, ...updatedTransaction } : txn
      )
    );
  };
  // ── Misc handlers ─────────────────────────────────────────────────
  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
    setCurrentPage(1);
  }, []);
  const handlePageChange = (page) => {
    setCurrentPage(page);
    setSelectedTransactions([]);
  };
  const handleSortChange = useCallback((field, dir) => {
    setSortField(field);
    setSortDir(dir);
    setCurrentPage(1);
  }, []);
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
  const handleOpenRemap = useCallback((partyId = null, targetTypeId = null) => {
    setRemapPartyId(partyId ?? true);
    setRemapTargetTypeId(targetTypeId);
  }, []);
  const handleCloseRemap = () => {
    setRemapPartyId(null);
    setRemapTargetTypeId(null);
  };
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
    <div className="mx-auto flex h-full w-full max-w-[1600px] flex-col overflow-hidden p-5">
      <div className="shrink-0 mb-4 flex items-center justify-between">
        <h1 className="text-[28px] font-semibold text-gray-800">Categorize Transactions</h1>
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsCreateCashOpen(true)}
            className={ACTION_BTN_SECONDARY}
          >
            + New Cash Transaction
          </button>
          {selectedTransactions.length > 0 && (
            <>
              <button
                onClick={() => setIsBulkEditOpen(true)}
                className={`${ACTION_BTN} bg-[#2196f3] hover:bg-[#1976d2]`}
              >
                Bulk Edit ({selectedTransactions.length})
              </button>
              <button
                onClick={() => setIsGenerateCashOpen(true)}
                className={`${ACTION_BTN} bg-[#43a047] hover:bg-[#2e7d32]`}
              >
                Generate Cash ({selectedTransactions.length})
              </button>
              <button
                onClick={() => setIsDeleteOpen(true)}
                className={`${ACTION_BTN} bg-[#e53935] hover:bg-[#c62828]`}
              >
                Delete ({selectedTransactions.length})
              </button>
            </>
          )}
        </div>
      </div>
      {/* shrink-0 added — the original omitted it, leaving the filter bar
          squashable inside the flex column. */}
      <div className="shrink-0 mb-5 rounded border border-gray-300 bg-gray-50 p-4">
        <div className="flex items-center gap-2.5">
          <label
            htmlFor="upload-filter"
            className="whitespace-nowrap font-medium text-gray-600"
          >
            Filter by Upload:
          </label>
          <select
            id="upload-filter"
            value={filters.upload_id || ''}
            onChange={(e) => {
              const value = e.target.value;
              handleFilterChange({ ...filters, upload_id: value ? parseInt(value) : null });
            }}
            className="min-w-[250px] rounded border border-gray-300 bg-white px-3 py-2 text-sm focus:border-[#4a90e2] focus:shadow-[0_0_0_2px_rgba(74,144,226,0.2)] focus:outline-none"
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
        onReceiptChange={handleReceiptChange}
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
      <DeleteTransactionsModal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        onConfirm={handleDeleteTransactions}
        transactionCount={selectedTransactions.length}
        loading={isDeleting}
      />      
    </div>
  );
}