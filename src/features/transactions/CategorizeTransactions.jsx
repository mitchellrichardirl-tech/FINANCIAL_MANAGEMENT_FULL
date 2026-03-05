import { useState, useEffect, useCallback } from 'react';
import {
  getTransactions,
  updateTransaction,
  bulkUpdateTransactions,
  getCategories,
  getSubCategories,
  getTypes,
  getParties,
  getUploads,
  createCategory,
  createSubCategory,
  createType,
  createParty,
  remapParty
} from './api';
import { getAccounts } from '@/features/statements/api';
import TransactionTable from './TransactionTable';
import FilterBar from './FilterBar';
import Pagination from '@/components/Pagination';
import BulkEditModal from './BulkEditModal';
import RemapPartyModal from './RemapPartyModal';
import './CategorizeTransactions.css';

const ITEMS_PER_PAGE = 100;

export default function CategorizeTransactions() {
  // Data state
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [types, setTypes] = useState([]);
  const [parties, setParties] = useState([]);
  const [uploads, setUploads] = useState([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [filters, setFilters] = useState({});
  const [selectedTransactions, setSelectedTransactions] = useState([]);
  const [isBulkEditOpen, setIsBulkEditOpen] = useState(false);
  const [sortField, setSortField] = useState('transaction_date');
  const [sortDir, setSortDir] = useState('desc');
  // RemapParty modal: null = closed, number = pre-selected party id,
  // true = open with no pre-selection (launched from header button)
  const [remapPartyId, setRemapPartyId] = useState(null);

  const isRemapOpen = remapPartyId !== null;

  // ── Data loading ──

  useEffect(() => { loadReferenceData(); }, []);
  useEffect(() => { loadTransactions(); }, [filters, currentPage, sortField, sortDir]);

  const loadReferenceData = async () => {
    try {
      const [
        accountsData,
        categoriesData,
        subCategoriesData,
        typesData,
        partiesData,
        uploadsData
      ] = await Promise.all([
        getAccounts(),
        getCategories(),
        getSubCategories(),
        getTypes(),
        getParties(),
        getUploads()
      ]);

      setAccounts(accountsData);
      setCategories(categoriesData);
      setSubCategories(subCategoriesData);
      setTypes(typesData);
      setParties(partiesData);
      setUploads(uploadsData.data || uploadsData);
    } catch (err) {
      setError('Failed to load reference data: ' + err.message);
    }
  };

  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
    setCurrentPage(1);
  }, []);

  const loadTransactions = async () => {
    setLoading(true);
    setError(null);

    try {
      const cleanFilters = Object.entries(filters).reduce((acc, [key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
          acc[key] = value;
        }
        return acc;
      }, {});

      cleanFilters.limit = ITEMS_PER_PAGE;
      cleanFilters.offset = (currentPage - 1) * ITEMS_PER_PAGE;

      // Add sort params
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
      console.error('Error loading transactions:', err);
      setError('Failed to load transactions: ' + err.message);
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleTransactionUpdate = async (transactionId, updates) => {
    try {
      const updatedTransaction = await updateTransaction(transactionId, updates);
      setTransactions(prev =>
        prev.map(t => t.id === transactionId ? { ...t, ...updatedTransaction } : t)
      );
      return updatedTransaction;
    } catch (err) {
      setError('Failed to update transaction: ' + err.message);
      throw err;
    }
  };

  const handleBulkUpdate = async (updates) => {
    if (selectedTransactions.length === 0) throw new Error('No transactions selected');

    setLoading(true);
    setError(null);
    try {
      await bulkUpdateTransactions(selectedTransactions, updates);
      await loadTransactions();
      setSelectedTransactions([]);
      setIsBulkEditOpen(false);
    } catch (err) {
      const msg = err.message || 'Failed to update transactions';
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    setSelectedTransactions([]);
  };

  // ── Remap Party ──

  const handleRemapParty = async (partyId, newTypeId) => {
    try {
      const result = await remapParty(partyId, newTypeId);
      const [partiesData] = await Promise.all([getParties(), loadTransactions()]);
      setParties(partiesData);
      return result;
    } catch (err) {
      setError('Failed to remap party: ' + err.message);
      throw err;
    }
  };

  /**
   * Find an existing party with `name` under `typeId`, or create one.
   * Returns the party id.
   */
  const handleFindOrCreateParty = useCallback(async (name, typeId) => {
    // Check if a party with this name already exists under this type
    const existing = parties.find(
      (p) => p.name.toLowerCase() === name.toLowerCase() && p.type_id === typeId
    );
    if (existing) return existing.id;

    // Create a new one
    const newParty = await handlePartyCreated(name, typeId, '');
    return newParty.id;
  }, [parties]);

  /**
   * Open the remap modal, optionally pre-selecting both party and target type.
   * The second argument lets TransactionRow pass the type the user already
   * chose, so RemapPartyModal can pre-fill it.
   */
  const handleOpenRemap = useCallback((partyId = null, targetTypeId = null) => {
    setRemapPartyId(partyId ?? true);
    setRemapTargetTypeId(targetTypeId);   // new state (see below)
  }, []);

  // Add alongside remapPartyId:
  const [remapTargetTypeId, setRemapTargetTypeId] = useState(null);

  // Clear it when the modal closes:
  const handleCloseRemap = () => {
    setRemapPartyId(null);
    setRemapTargetTypeId(null);
  };
  
  // ── Create handlers ──

  const handleCategoryCreated = async (name, description) => {
    try {
      const response = await createCategory(name, description);
      const categoriesData = await getCategories();
      setCategories(categoriesData);
      return categoriesData.find(c => c.category === name) || response;
    } catch (err) {
      setError('Failed to create category: ' + err.message);
      throw err;
    }
  };

  const handleSubCategoryCreated = async (name, categoryId, description) => {
    try {
      const response = await createSubCategory(name, categoryId, description);
      const subCategoriesData = await getSubCategories();
      setSubCategories(subCategoriesData);
      return subCategoriesData.find(
        sc => sc.sub_category === name && sc.category_id === categoryId
      ) || response;
    } catch (err) {
      setError('Failed to create sub-category: ' + err.message);
      throw err;
    }
  };

  const handleTypeCreated = async (name, subCategoryId, description) => {
    try {
      const response = await createType(name, subCategoryId, description);
      const typesData = await getTypes();
      setTypes(typesData);
      return typesData.find(
        t => t.type === name && t.sub_category_id === subCategoryId
      ) || response;
    } catch (err) {
      setError('Failed to create type: ' + err.message);
      throw err;
    }
  };

  const handlePartyCreated = async (name, typeId, description) => {
    try {
      const response = await createParty(name, typeId, description);
      const partiesData = await getParties();
      setParties(partiesData);
      return partiesData.find(
        p => p.name === name && p.type_id === typeId
      ) || response;
    } catch (err) {
      setError('Failed to create party: ' + err.message);
      throw err;
    }
  };

  const handleSortChange = useCallback((field, dir) => {
    setSortField(field);
    setSortDir(dir);
    setCurrentPage(1); // reset to first page on sort change
  }, []);

  // ── Helpers ──

  const formatUploadDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    const date = new Date(dateString);
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleDateString('en-GB', { month: 'short' });
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${day} ${month}; ${hours}:${minutes}`;
  };

  // Derive the numeric initialPartyId to pass to the modal.
  // When opened from the header button there's no pre-selection (null).
  const initialPartyId = typeof remapPartyId === 'number' ? remapPartyId : null;

  return (
    <div className="categorize-transactions">
      <div className="page-header">
        <h1>Categorize Transactions</h1>
        <div className="header-actions">
          {selectedTransactions.length > 0 && (
            <button
              onClick={() => setIsBulkEditOpen(true)}
              className="bulk-edit-button"
            >
              Bulk Edit ({selectedTransactions.length})
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="filters-section">
        <div className="filter-group">
          <label htmlFor="upload-filter">Filter by Upload:</label>
          <select
            id="upload-filter"
            value={filters.upload_id || ''}
            onChange={(e) => {
              const value = e.target.value;
              handleFilterChange({
                ...filters,
                upload_id: value ? parseInt(value) : null,
              });
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
        // NEW: lets any row open the remap modal pre-filled with its party
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