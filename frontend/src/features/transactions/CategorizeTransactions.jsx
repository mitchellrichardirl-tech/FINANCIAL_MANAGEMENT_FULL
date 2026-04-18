import { useState, useCallback } from 'react';
import { useToast } from '@/components/ToastContext';
import {
  useTransactions,
  useAccounts,
  useUploads,
  useCategories,
  useSubCategories,
  useTypes,
  useParties,
  useUpdateTransaction,
  useBulkUpdateTransactions,
  useGenerateCashTransactions,
  useCreateCashTransaction,
  useCreateCategory,
  useCreateSubCategory,
  useCreateType,
  useCreateParty,
  useRemapParty,
} from './hooks';
import TransactionTable from './TransactionTable';
import Pagination from '@/components/Pagination';
import BulkEditModal from './BulkEditModal';
import RemapPartyModal from './RemapPartyModal';
import GenerateCashModal from './GenerateCashModal';
import CreateCashTransactionModal from './CreateCashTransactionModal';
import { createLogger } from '@/lib/logger';

const logger = createLogger('CategorizeTransactions');
const ITEMS_PER_PAGE = 100;

export default function CategorizeTransactions() {
  const { addToast } = useToast();

  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState({});
  const [selectedTransactions, setSelectedTransactions] = useState([]);
  const [isBulkEditOpen, setIsBulkEditOpen] = useState(false);
  const [isGenerateCashOpen, setIsGenerateCashOpen] = useState(false);
  const [isCreateCashOpen, setIsCreateCashOpen] = useState(false);
  const [sortField, setSortField] = useState('transaction_date');
  const [sortDir, setSortDir] = useState('desc');
  const [remapPartyId, setRemapPartyId] = useState(null);
  const [remapTargetTypeId, setRemapTargetTypeId] = useState(null);

  const isRemapOpen = remapPartyId !== null;

  const queryFilters = {
    ...Object.fromEntries(
      Object.entries(filters).filter(
        ([, v]) => v !== null && v !== undefined && v !== ''
      )
    ),
    limit: ITEMS_PER_PAGE,
    offset: (currentPage - 1) * ITEMS_PER_PAGE,
    ...(sortField ? { sort_by: sortField, sort_dir: sortDir } : {}),
  };

  const txnQuery = useTransactions(queryFilters);
  const accountsQuery = useAccounts();
  const uploadsQuery = useUploads();
  const categoriesQuery = useCategories();
  const subCategoriesQuery = useSubCategories();
  const typesQuery = useTypes();
  const partiesQuery = useParties();

  const updateTxn = useUpdateTransaction();
  const bulkUpdateTxn = useBulkUpdateTransactions();
  const generateCash = useGenerateCashTransactions();
  const createCash = useCreateCashTransaction();
  const createCategoryMutation = useCreateCategory();
  const createSubCategoryMutation = useCreateSubCategory();
  const createTypeMutation = useCreateType();
  const createPartyMutation = useCreateParty();
  const remapPartyMutation = useRemapParty();

  const transactions = txnQuery.data || [];
  const accounts = accountsQuery.data || [];
  const categories = categoriesQuery.data || [];
  const subCategories = subCategoriesQuery.data || [];
  const types = typesQuery.data || [];
  const parties = partiesQuery.data || [];
  const uploadsRaw = uploadsQuery.data;
  const uploads = uploadsRaw?.data || uploadsRaw || [];

  const totalTransactions =
    transactions.length === ITEMS_PER_PAGE
      ? currentPage * ITEMS_PER_PAGE + 1
      : (currentPage - 1) * ITEMS_PER_PAGE + transactions.length;

  const handleTransactionUpdate = async (transactionId, updates) => {
    try {
      return await updateTxn.mutateAsync({ id: transactionId, updates });
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
    try {
      await bulkUpdateTxn.mutateAsync({ ids: selectedTransactions, updates });
      setSelectedTransactions([]);
      setIsBulkEditOpen(false);
      addToast({
        message: `Updated ${count} transaction${count === 1 ? '' : 's'}`,
        type: 'success',
        duration: 3000,
      });
    } catch (err) {
      const msg = err.userMessage || err.message || 'Failed to update transactions';
      addToast({ message: msg, type: 'error' });
      throw err;
    }
  };

  const handleGenerateCash = async () => {
    if (selectedTransactions.length === 0) throw new Error('No transactions selected');
    try {
      const response = await generateCash.mutateAsync(selectedTransactions);
      const result = response?.data ?? response;

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
    }
  };

  const handleCreateCashTransaction = async (opts) => {
    try {
      await createCash.mutateAsync(opts);
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
    }
  };

  const handleRemapParty = async (partyId, newTypeId) => {
    try {
      const result = await remapPartyMutation.mutateAsync({ partyId, newTypeId });
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

  const makeCreateHandler = useCallback(
    (label, mutation, finder) =>
      async (...args) => {
        try {
          let payload;
          if (label === 'Category') {
            payload = { name: args[0], description: args[1] };
          } else {
            payload = { name: args[0], description: args[2] };
            if (label === 'Sub-category') payload.categoryId = args[1];
            if (label === 'Type') payload.subCategoryId = args[1];
            if (label === 'Party') payload.typeId = args[1];
          }
          const created = await mutation.mutateAsync(payload);
          addToast({
            message: `${label} "${args[0]}" created`,
            type: 'success',
            duration: 2500,
          });
          return created;
        } catch (err) {
          throw err;
        }
      },
    [addToast]
  );

  const handleCategoryCreated = makeCreateHandler('Category', createCategoryMutation);
  const handleSubCategoryCreated = makeCreateHandler('Sub-category', createSubCategoryMutation);
  const handleTypeCreated = makeCreateHandler('Type', createTypeMutation);
  const handlePartyCreated = makeCreateHandler('Party', createPartyMutation);

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
    <div className="w-full max-w-[1600px] h-full mx-auto p-5 box-border flex flex-col overflow-hidden">
      <div className="shrink-0 flex justify-between items-center mb-4">
        <h1 className="m-0 text-[28px] font-semibold text-[#333]">Categorize Transactions</h1>
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setIsCreateCashOpen(true)}
            className="py-2.5 px-5 bg-[#2196f3] text-white border-0 rounded text-sm font-medium cursor-pointer hover:bg-[#1976d2]"
          >
            + New Cash Transaction
          </button>
          {selectedTransactions.length > 0 && (
            <>
              <button
                type="button"
                onClick={() => setIsBulkEditOpen(true)}
                className="py-2.5 px-5 bg-[#2196f3] text-white border-0 rounded text-sm font-medium cursor-pointer hover:bg-[#1976d2]"
              >
                Bulk Edit ({selectedTransactions.length})
              </button>
              <button
                type="button"
                onClick={() => setIsGenerateCashOpen(true)}
                className="py-2.5 px-5 bg-[#43a047] text-white border-0 rounded text-sm font-medium cursor-pointer hover:bg-[#2e7d32]"
              >
                Generate Cash ({selectedTransactions.length})
              </button>
            </>
          )}
        </div>
      </div>

      <div className="mb-5 p-4 bg-[#f8f9fa] rounded border border-[#dee2e6]">
        <div className="flex items-center gap-2.5">
          <label htmlFor="upload-filter" className="font-medium text-[#495057] whitespace-nowrap">
            Filter by Upload:
          </label>
          <select
            id="upload-filter"
            value={filters.upload_id || ''}
            onChange={(e) => {
              const value = e.target.value;
              handleFilterChange({ ...filters, upload_id: value ? parseInt(value) : null });
            }}
            className="py-2 px-3 border border-[#ced4da] rounded text-sm min-w-[250px] bg-white focus:outline-none focus:border-[#4a90e2] focus:shadow-[0_0_0_2px_rgba(74,144,226,0.2)]"
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
