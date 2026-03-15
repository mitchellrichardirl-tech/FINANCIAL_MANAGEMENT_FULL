import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/components/ToastContext';
import {
  getTransactions, updateTransaction, bulkUpdateTransactions,
  getCategories, getSubCategories, getTypes, getParties, getUploads,
  createCategory, createSubCategory, createType, createParty, remapParty
} from './api';
import { getAccounts } from '@/features/statements/api';
import TransactionTable from './TransactionTable';
import Pagination from '@/components/Pagination';
import BulkEditModal from './BulkEditModal';
import RemapPartyModal from './RemapPartyModal';
import './CategorizeTransactions.css';
import { createLogger } from '@/lib/logger';

const logger = createLogger('CategorizeTransactions');
const ITEMS_PER_PAGE = 100;

export default function CategorizeTransactions() {
  const { addToast } = useToast();

  // Data state
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [types, setTypes] = useState([]);
  const [parties, setParties] = useState([]);
  const [uploads, setUploads] = useState([]);

  // UI state — `error` removed
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [filters, setFilters] = useState({});
  const [selectedTransactions, setSelectedTransactions] = useState([]);
  const [isBulkEditOpen, setIsBulkEditOpen] = useState(false);
  const [sortField, setSortField] = useState('transaction_date');
  const [sortDir, setSortDir] = useState('desc');
  const [remapPartyId, setRemapPartyId] = useState(null);
  const [remapTargetTypeId, setRemapTargetTypeId] = useState(null);

  const isRemapOpen = remapPartyId !== null;

  // ── Data loading ──

  useEffect(() => { loadReferenceData(); }, []);
  useEffect(() => { loadTransactions(); }, [filters, currentPage, sortField, sortDir]);

  const loadReferenceData = async () => {
    try {
      const [accountsData, categoriesData, subCategoriesData, typesData, partiesData, uploadsData] =
        await Promise.all([
          getAccounts(), getCategories(), getSubCategories(),
          getTypes(), getParties(), getUploads()
        ]);
      setAccounts(accountsData);
      setCategories(categoriesData);
      setSubCategories(subCategoriesData);
      setTypes(typesData);
      setParties(partiesData);
      setUploads(uploadsData.data || uploadsData);
    } catch (err) {
      logger.error('Error loading reference data:', err);
      addToast({ message: `Failed to load reference data: ${err.userMessage || err.message}`, type: 'error' });
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

      const data = await getTransactions(cleanFilters);
      setTransactions(data);
      setTotalTransactions(
        data.length === ITEMS_PER_PAGE
          ? currentPage * ITEMS_PER_PAGE + 1
          : (currentPage - 1) * ITEMS_PER_PAGE + data.length
      );
    } catch (err) {
      logger.error('Error loading transactions:', err);
      addToast({ message: `Failed to load transactions: ${err.userMessage || err.message}`, type: 'error' });
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  // ── Mutations ──

  const handleTransactionUpdate = async (transactionId, updates) => {
    try {
      const updated = await updateTransaction(transactionId, updates);
      setTransactions(prev =>
        prev.map(t => t.id === transactionId ? { ...t, ...updated } : t)
      );
      // Optional: this fires on every inline cell edit, so keep it short & quick
      // addToast({ message: 'Saved', type: 'success', duration: 1500 });
      return updated;
    } catch (err) {
      addToast({ message: `Failed to update transaction: ${err.userMessage || err.message}`, type: 'error' });
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
      addToast({ message: msg.userMessage || msg.message || 'Failed to update transactions', type: 'error' });
      throw new Error(msg);
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
        duration: merged ? 5000 : 3000,  // give merge info a bit longer
      });
      return result;
    } catch (err) {
      addToast({ message: `Failed to remap party: ${err.userMessage || err.message}`, type: 'error' });
      throw err;
    }
  };

  // ── Create handlers ──
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
          // Don't toast — let CreateCategoryModal show inline error
          throw err;
        }
      },
    [addToast]
  );

  const handleCategoryCreated = makeCreateHandler(
    'Category', createCategory, getCategories, setCategories,
    (list, name) => list.find(c => c.category === name)
  );

  const handleSubCategoryCreated = makeCreateHandler(
    'Sub-category', createSubCategory, getSubCategories, setSubCategories,
    (list, name, categoryId) =>
      list.find(sc => sc.sub_category === name && sc.category_id === categoryId)
  );

  const handleTypeCreated = makeCreateHandler(
    'Type', createType, getTypes, setTypes,
    (list, name, subCategoryId) =>
      list.find(t => t.type === name && t.sub_category_id === subCategoryId)
  );

  const handlePartyCreated = makeCreateHandler(
    'Party', createParty, getParties, setParties,
    (list, name, typeId) =>
      list.find(p => p.name === name && p.type_id === typeId)
  );

  // ── Remaining handlers (unchanged) ──

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

  const handleFindOrCreateParty = useCallback(async (name, typeId) => {
    const existing = parties.find(
      (p) => p.name.toLowerCase() === name.toLowerCase() && p.type_id === typeId
    );
    if (existing) return existing.id;
    const newParty = await handlePartyCreated(name, typeId, '');
    return newParty.id;
  }, [parties, handlePartyCreated]);

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
    <div className="categorize-transactions">
      <div className="page-header">
        <h1>Categorize Transactions</h1>
        <div className="header-actions">
          {selectedTransactions.length > 0 && (
            <button onClick={() => setIsBulkEditOpen(true)} className="bulk-edit-button">
              Bulk Edit ({selectedTransactions.length})
            </button>
          )}
        </div>
      </div>

      {/* error banner removed — replaced by toasts */}

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
    </div>
  );
}