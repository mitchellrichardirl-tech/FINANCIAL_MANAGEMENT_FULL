import { useState, useEffect, useCallback } from 'react';
import {
  getTransactions,
  updateTransaction,
  getAccounts,
  getCategories,
  getSubCategories,
  getTypes,
  getParties,
  getUploads,
  createCategory,
  createSubCategory,
  createType,
  createParty
} from '../services/api';
import TransactionTable from '../components/TransactionTable';
import FilterBar from '../components/FilterBar';
import Pagination from '../components/Pagination';
import BulkEditModal from '../components/BulkEditModal';
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

  // Load reference data on mount
  useEffect(() => {
    loadReferenceData();
  }, []);

  // Load transactions when filters or page changes
  useEffect(() => {
    loadTransactions();
  }, [filters, currentPage]);

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

      console.log('Accounts loaded:', accountsData);
      console.log('Uploads loaded:', uploadsData);
      
      setAccounts(accountsData);
      setCategories(categoriesData);
      setSubCategories(subCategoriesData);
      setTypes(typesData);
      setParties(partiesData);
      setUploads(uploadsData.data || uploadsData);
    } catch (err) {
      console.error('Error loading reference data:', err);
      setError('Failed to load reference data: ' + err.message);
    }
  };

  const handleFilterChange = useCallback((newFilters) => {
    console.log('CategorizeTransactions: handleFilterChange called with:', newFilters);
    setFilters(newFilters);
    setCurrentPage(1); // Reset to first page when filters change
  }, []);

  // In loadTransactions, make sure boolean filters are sent correctly
  const loadTransactions = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Clean filters - remove null/empty values but KEEP false values
      const cleanFilters = Object.entries(filters).reduce((acc, [key, value]) => {
        // Keep the value if it's not null, not undefined, and not empty string
        // This ensures false values are preserved
        if (value !== null && value !== undefined && value !== '') {
          acc[key] = value;
        }
        return acc;
      }, {});

      // Add pagination
      cleanFilters.limit = ITEMS_PER_PAGE;
      cleanFilters.offset = (currentPage - 1) * ITEMS_PER_PAGE;

      console.log('Sending filters to API:', cleanFilters);
      console.log('Filter types:', Object.entries(cleanFilters).map(([k, v]) => `${k}: ${typeof v}`));
      const data = await getTransactions(cleanFilters);
      
      console.log('Transactions received: ', data);
      console.log('Received transactions:', data.length);
      
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
      
      // Update the transaction in the local state
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
    console.log('CategorizeTransactions: handleBulkUpdate called with:', updates);
    console.log('Selected transactions:', selectedTransactions);
    
    if (selectedTransactions.length === 0) {
      console.error('No transactions selected');
      throw new Error('No transactions selected');
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Update all selected transactions
      const updatePromises = selectedTransactions.map(async (id) => {
        console.log(`Updating transaction ${id} with:`, updates);
        try {
          const result = await updateTransaction(id, updates);
          console.log(`Transaction ${id} updated successfully`);
          return result;
        } catch (err) {
          console.error(`Failed to update transaction ${id}:`, err);
          throw err;
        }
      });
      
      // Wait for all updates to complete
      const results = await Promise.all(updatePromises);
      console.log('All transactions updated:', results);
      
      // Reload transactions to get fresh data
      await loadTransactions();
      
      // Clear selection
      setSelectedTransactions([]);
      
      // Close the modal
      setIsBulkEditOpen(false);
      
      console.log('Bulk update complete and modal closed');
      
    } catch (err) {
      console.error('Bulk update failed:', err);
      const errorMessage = err.message || 'Failed to update transactions';
      setError(errorMessage);
      // Re-throw so the modal can show the error
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    setSelectedTransactions([]); // Clear selection when changing pages
  };

  // Create handlers
  const handleCategoryCreated = async (name, description) => {
    try {
      const response = await createCategory(name, description);
      const categoriesData = await getCategories();
      setCategories(categoriesData);
      
      // Return the new category for the callback
      const newCategory = categoriesData.find(c => c.category === name);
      return newCategory || response;
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
      
      const newSubCategory = subCategoriesData.find(
        sc => sc.sub_category === name && sc.category_id === categoryId
      );
      return newSubCategory || response;
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
      
      const newType = typesData.find(
        t => t.type === name && t.sub_category_id === subCategoryId
      );
      return newType || response;
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
      
      const newParty = partiesData.find(
        p => p.name === name && p.type_id === typeId
      );
      return newParty || response;
    } catch (err) {
      setError('Failed to create party: ' + err.message);
      throw err;
    }
  };

  if (loading && transactions.length === 0) {
    return (
      <div className="categorize-transactions">
        <h1>Categorize Transactions</h1>
        <div className="loading">Loading...</div>
      </div>
    );
  }

  const formatUploadDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    
    const date = new Date(dateString);
    
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleDateString('en-GB', { month: 'short' });
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    return `${day} ${month}; ${hours}:${minutes}`;
  };

  return (
    <div className="categorize-transactions">
      <div className="page-header">
        <h1>Categorize Transactions</h1>
        {selectedTransactions.length > 0 && (
          <button 
            onClick={() => setIsBulkEditOpen(true)}
            className="bulk-edit-button"
          >
            Bulk Edit ({selectedTransactions.length})
          </button>
        )}
      </div>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {<div className="filters-section">
        <div className="filter-group">
          <label htmlFor="upload-filter">Filter by Upload:</label>
          <select
            id="upload-filter"
            value={filters.upload_id || ''}
            onChange={(e) => {
              const value = e.target.value;
              handleFilterChange({
                ...filters,
                upload_id: value ? parseInt(value) : null
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
      </div>}
      
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
    </div>
  );
}