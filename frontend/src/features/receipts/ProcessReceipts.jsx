import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { useUpdateTransaction } from '@/features/transactions/hooks';
import {
  useConfirmReceipt,
  useDeleteReceipt,
  useCandidateTransactions,
  useMatchParty,
  useCreateCashFromReceipt,
} from './hooks';
import {
  useCategories,
  useSubCategories,
  useTypes,
  useParties,
  useCreateCategory,
  useCreateSubCategory,
  useCreateType,
  useCreateParty,
} from '@/features/transactions/hooks';
import GenerateCashFromReceiptModal from './GenerateCashFromReceiptModal';
import { ErrorCode } from '@/lib/apiErrors';
import { useToast } from '@/components/ToastContext';
import BulkUploadReceipts from './BulkUploadReceipts';
import SelectableReceiptTable from './SelectableReceiptTable';
import ImagePreview from './ImagePreview';
import CandidateTransactions from './CandidateTransactions';
import { createLogger } from '@/lib/logger';

const logger = createLogger('ProcessReceipts');

const FIELD_MAP = {
  vendor: 'vendor',
  date: 'date',
  amount: 'amount',
  original_filename: null,
};

function ProcessReceipts() {
  const { addToast } = useToast();

  const [receipts, setReceipts] = useState([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState(null);
  const hasAutoSelectedRef = useRef(false);

  const [isUploading, setIsUploading] = useState(false);
  const [linkedTransactionId, setLinkedTransactionId] = useState(null);
  const [isCashModalOpen, setIsCashModalOpen] = useState(false);
  const [suggestedPartyId, setSuggestedPartyId] = useState(null);

  const {
    register,
    setValue,
    watch,
    reset,
    setError,
    clearErrors,
    formState: { errors },
  } = useForm({ defaultValues: { vendor: '', date: '', amount: '' } });

  const editableData = watch();
  const [generalError, setGeneralError] = useState(null);

  const selectedReceipt = receipts.find((r) => r.receipt_id === selectedReceiptId);

  const categoriesQuery = useCategories();
  const subCategoriesQuery = useSubCategories();
  const typesQuery = useTypes();
  const partiesQuery = useParties();
  const categories = categoriesQuery.data || [];
  const subCategories = subCategoriesQuery.data || [];
  const types = typesQuery.data || [];
  const parties = partiesQuery.data || [];

  const createCategoryMut = useCreateCategory();
  const createSubCategoryMut = useCreateSubCategory();
  const createTypeMut = useCreateType();
  const createPartyMut = useCreateParty();

  const updateTxn = useUpdateTransaction();
  const confirmReceiptMut = useConfirmReceipt();
  const deleteReceiptMut = useDeleteReceipt();
  const matchPartyMut = useMatchParty();
  const createCashFromReceiptMut = useCreateCashFromReceipt();

  const candidateQuery = useCandidateTransactions(
    selectedReceipt && (editableData.date || editableData.amount)
      ? {
          date: editableData.date || null,
          amount: editableData.amount ? parseFloat(editableData.amount) : null,
          vendor: editableData.vendor || null,
        }
      : null,
    !!selectedReceipt
  );

  const candidateTransactions = (() => {
    const r = candidateQuery.data;
    if (!r) return [];
    if (r.success && r.data?.transactions) return r.data.transactions;
    if (r.transactions) return r.transactions;
    return [];
  })();
  const isLoadingCandidates = candidateQuery.isFetching;

  const isSaving = confirmReceiptMut.isPending || deleteReceiptMut.isPending;
  const isLinking = updateTxn.isPending && confirmReceiptMut.isPending;
  const isGeneratingCash = createCashFromReceiptMut.isPending;

  useEffect(() => {
    if (selectedReceipt) {
      const extracted = selectedReceipt.extracted_data || {};
      reset({
        vendor: extracted.vendor || '',
        date: extracted.date ? extracted.date.split('T')[0] : '',
        amount: extracted.amount?.toString() || '',
      });
      setLinkedTransactionId(null);
      clearErrors();
      setGeneralError(null);
    } else {
      reset({ vendor: '', date: '', amount: '' });
      clearErrors();
      setGeneralError(null);
    }
  }, [selectedReceiptId, selectedReceipt, reset, clearErrors]);

  const routeError = (err, fallbackMessage) => {
    const message = err.userMessage || err.message || fallbackMessage;
    const mappedField = err.field ? FIELD_MAP[err.field] : null;
    if (mappedField) {
      setError(mappedField, { type: 'server', message });
      return;
    }
    if (err.code === ErrorCode.INVALID_VALUE || err.code === ErrorCode.REQUIRED_FIELD) {
      setGeneralError(message);
      return;
    }
    addToast({ message, type: 'error' });
  };

  const handleReceiptProcessed = (result) => {
    const newReceipt = {
      ...result,
      receipt_id: result.receipt_id,
      filename: result.filename,
      extracted_data: result.extracted_data || {},
      status: 'pending',
    };
    setReceipts((prev) => [...prev, newReceipt]);
    if (!hasAutoSelectedRef.current) {
      hasAutoSelectedRef.current = true;
      setSelectedReceiptId(result.receipt_id);
    }
  };

  const handleProcessingStart = () => {
    setIsUploading(true);
    hasAutoSelectedRef.current = false;
  };

  const handleProcessingComplete = ({ succeeded, failed }) => {
    setIsUploading(false);
    if (failed > 0) {
      addToast({
        message: `${succeeded} processed, ${failed} failed`,
        type: failed === succeeded + failed ? 'error' : 'info',
      });
    } else if (succeeded > 0) {
      addToast({
        message: `${succeeded} receipt${succeeded === 1 ? '' : 's'} processed`,
        type: 'success',
      });
    }
  };

  const makeCreateHandler = (label, mutation) => async (...args) => {
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
    addToast({ message: `${label} "${args[0]}" created`, type: 'success', duration: 2500 });
    return created;
  };

  const handleCategoryCreated = makeCreateHandler('Category', createCategoryMut);
  const handleSubCategoryCreated = makeCreateHandler('Sub-category', createSubCategoryMut);
  const handleTypeCreated = makeCreateHandler('Type', createTypeMut);
  const handlePartyCreated = makeCreateHandler('Party', createPartyMut);

  const handleSelectReceipt = (id) => setSelectedReceiptId(id);

  const handleInputChange = (field, value) => {
    setValue(field, value);
    if (errors[field]) clearErrors(field);
  };

  const buildReceiptData = () => {
    if (!selectedReceipt) return null;
    return {
      id: selectedReceipt.receipt_id,
      original_filename: selectedReceipt.filename,
      vendor: editableData.vendor,
      amount: editableData.amount ? parseFloat(editableData.amount) : null,
      date: editableData.date || null,
      stored_filename: selectedReceipt.stored_filename,
      file_path: selectedReceipt.file_path,
      confidence: selectedReceipt.extracted_data?.confidence || 0,
      selected_method: selectedReceipt.extracted_data?.selected_method || 'manual',
      raw_text: selectedReceipt.extracted_data?.raw_text,
      page_number: selectedReceipt.page_number || 1,
    };
  };

  const handleOpenCashModal = async () => {
    setSuggestedPartyId(null);
    try {
      const match = await matchPartyMut.mutateAsync(editableData.vendor);
      if (match?.party_id) setSuggestedPartyId(match.party_id);
    } catch (err) {
      logger.warn('Party match failed (non-fatal):', err);
    }
    setIsCashModalOpen(true);
  };

  const handleGenerateCash = async ({ partyId, isWithdrawal, isCredit, isKids, isOneOff }) => {
    if (!selectedReceipt) return;
    clearErrors();
    setGeneralError(null);

    try {
      const receiptData = buildReceiptData();
      const saveResult = await confirmReceiptMut.mutateAsync(receiptData);
      const receiptId =
        saveResult.data?.receipt?.id ||
        saveResult.receipt?.id ||
        saveResult.id ||
        selectedReceipt.receipt_id;

      if (!receiptId) throw new Error('Failed to get receipt ID from save response');

      const result = await createCashFromReceiptMut.mutateAsync({
        receiptId, partyId, isWithdrawal, isCredit, isKids, isOneOff,
      });
      const txn = result?.data?.transaction ?? result?.transaction;

      setReceipts((prev) =>
        prev.map((r) =>
          r.receipt_id === selectedReceiptId
            ? {
                ...r,
                status: 'linked',
                linked_transaction_id: txn?.id,
                extracted_data: {
                  ...r.extracted_data,
                  vendor: editableData.vendor,
                  date: editableData.date,
                  amount: editableData.amount,
                },
              }
            : r,
        ),
      );

      setIsCashModalOpen(false);
      addToast({ message: 'Cash transaction created from receipt', type: 'success', duration: 2500 });
      setTimeout(selectNextReceipt, 1000);
    } catch (err) {
      logger.error('Failed to generate cash transaction:', err);
      routeError(err, 'Failed to generate cash transaction');
      throw err;
    }
  };

  const handleSave = async () => {
    if (!selectedReceipt) return;
    clearErrors();
    setGeneralError(null);
    try {
      const receiptData = buildReceiptData();
      await confirmReceiptMut.mutateAsync(receiptData);
      setReceipts((prev) =>
        prev.map((r) =>
          r.receipt_id === selectedReceiptId
            ? {
                ...r,
                status: 'saved',
                extracted_data: {
                  ...r.extracted_data,
                  vendor: editableData.vendor,
                  date: editableData.date,
                  amount: editableData.amount,
                },
              }
            : r
        )
      );
      addToast({ message: 'Receipt saved', type: 'success', duration: 2000 });
      setTimeout(selectNextReceipt, 800);
    } catch (err) {
      logger.error('Failed to save receipt:', err);
      routeError(err, 'Failed to save receipt');
    }
  };

  const handleSelectTransaction = async (transaction) => {
    if (!selectedReceipt) return;
    clearErrors();
    setGeneralError(null);
    try {
      const receiptData = buildReceiptData();
      const saveResult = await confirmReceiptMut.mutateAsync(receiptData);
      const receiptId =
        saveResult.data?.receipt?.id ||
        saveResult.receipt?.id ||
        saveResult.id ||
        selectedReceipt.receipt_id;
      if (!receiptId) throw new Error('Failed to get receipt ID from save response');

      await updateTxn.mutateAsync({ id: transaction.id, updates: { receipt_id: receiptId } });

      setReceipts((prev) =>
        prev.map((r) =>
          r.receipt_id === selectedReceiptId
            ? {
                ...r,
                status: 'linked',
                linked_transaction_id: transaction.id,
                extracted_data: {
                  ...r.extracted_data,
                  vendor: editableData.vendor,
                  date: editableData.date,
                  amount: editableData.amount,
                },
              }
            : r
        )
      );
      setLinkedTransactionId(transaction.id);
      addToast({ message: 'Receipt linked to transaction', type: 'success', duration: 2500 });
      setTimeout(selectNextReceipt, 1000);
    } catch (err) {
      logger.error('Failed to link receipt to transaction:', err);
      if (err.code === ErrorCode.NOT_FOUND && err.entity === 'Transaction') {
        addToast({
          message: 'That transaction no longer exists. Refreshing candidates…',
          type: 'info',
        });
        candidateQuery.refetch();
      } else {
        routeError(err, 'Failed to link receipt');
      }
    }
  };

  const handleDelete = async () => {
    if (!selectedReceipt) return;
    clearErrors();
    setGeneralError(null);
    try {
      await deleteReceiptMut.mutateAsync(selectedReceipt.receipt_id);
      const currentIndex = receipts.findIndex((r) => r.receipt_id === selectedReceiptId);
      const remaining = receipts.filter((r) => r.receipt_id !== selectedReceiptId);
      setReceipts(remaining);
      if (remaining.length > 0) {
        const nextIndex = Math.min(currentIndex, remaining.length - 1);
        setSelectedReceiptId(remaining[nextIndex].receipt_id);
      } else {
        setSelectedReceiptId(null);
      }
      addToast({ message: 'Receipt deleted', type: 'success', duration: 1500 });
    } catch (err) {
      logger.error('Failed to delete receipt:', err);
      if (err.code === ErrorCode.NOT_FOUND) {
        addToast({ message: 'Receipt was already deleted', type: 'info' });
        setReceipts((prev) => prev.filter((r) => r.receipt_id !== selectedReceiptId));
        setSelectedReceiptId(null);
      } else {
        addToast({ message: err.userMessage || 'Failed to delete receipt', type: 'error' });
      }
    }
  };

  const handleRemoveFromList = (receiptId) => {
    const currentIndex = receipts.findIndex((r) => r.receipt_id === receiptId);
    const remaining = receipts.filter((r) => r.receipt_id !== receiptId);
    setReceipts(remaining);
    if (selectedReceiptId === receiptId) {
      if (remaining.length > 0) {
        const nextIndex = Math.min(currentIndex, remaining.length - 1);
        setSelectedReceiptId(remaining[nextIndex].receipt_id);
      } else {
        setSelectedReceiptId(null);
      }
    }
  };

  const selectNextReceipt = () => {
    const currentIndex = receipts.findIndex((r) => r.receipt_id === selectedReceiptId);
    const pending = receipts.filter(
      (r) => r.status === 'pending' && r.receipt_id !== selectedReceiptId
    );
    if (pending.length > 0) {
      const nextAfter = pending.find((r) => receipts.indexOf(r) > currentIndex);
      setSelectedReceiptId(nextAfter?.receipt_id || pending[0].receipt_id);
    }
  };

  const handleClearAll = () => {
    setReceipts([]);
    setSelectedReceiptId(null);
    reset({ vendor: '', date: '', amount: '' });
    clearErrors();
    setGeneralError(null);
    hasAutoSelectedRef.current = false;
  };

  const canSave =
    selectedReceipt &&
    selectedReceipt.status === 'pending' &&
    editableData.vendor.trim() !== '' &&
    !isSaving &&
    !isLinking;
  const canDelete =
    selectedReceipt && selectedReceipt.status === 'pending' && !isSaving && !isLinking;
  const canGenerateCash =
    selectedReceipt &&
    selectedReceipt.status === 'pending' &&
    editableData.vendor.trim() !== '' &&
    editableData.date !== '' &&
    editableData.amount !== '' &&
    !isSaving &&
    !isLinking &&
    !isGeneratingCash;

  const pendingCount = receipts.filter((r) => r.status === 'pending').length;
  const processedCount = receipts.filter((r) => r.status !== 'pending').length;

  const sectionCls =
    'bg-white rounded-[10px] shadow-[0_2px_8px_rgba(0,0,0,0.08)] p-5';
  const sectionHeadingCls =
    'm-0 mb-4 text-[1.1rem] text-[#333] border-b-2 border-[#f0f0f0] pb-3';
  const inputCls =
    'py-2.5 px-3 border border-[#ddd] rounded-md text-[0.95rem] transition-[border-color,box-shadow] duration-200 focus:outline-none focus:border-[#007bff] focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)] disabled:bg-[#f5f5f5] disabled:cursor-not-allowed disabled:text-[#999]';
  const formGroupCls = 'flex flex-col gap-1.5';
  const labelCls = 'text-[0.9rem] font-semibold text-[#444]';
  const errorInputCls = 'border-[#dc2626] bg-[#fef2f2]';

  return (
    <div className="py-6 px-8 max-w-[calc(100vw-4rem)] mx-auto">
      <div className="flex justify-between items-center mb-6 flex-wrap gap-4">
        <h1 className="m-0">Process Receipts</h1>
        <div className="flex items-center gap-4">
          {receipts.length > 0 && (
            <span className="text-[#666] text-[0.9rem] bg-[#f0f0f0] py-2 px-4 rounded-[20px]">
              {pendingCount} pending, {processedCount} processed
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-[minmax(520px,600px)_minmax(400px,1fr)_minmax(600px,700px)] gap-8 min-h-[calc(100vh-200px)] max-[1600px]:grid-cols-[minmax(480px,550px)_minmax(350px,1fr)_minmax(500px,600px)] max-[1400px]:grid-cols-[minmax(450px,500px)_minmax(320px,1fr)_minmax(450px,500px)] max-[1200px]:grid-cols-1">
        <div className="flex flex-col gap-6 min-w-[500px] max-[1400px]:min-w-[420px] max-[1200px]:min-w-full">
          <div className={`${sectionCls} shrink-0`}>
            <h3 className={sectionHeadingCls}>Upload Receipts</h3>
            <BulkUploadReceipts
              onReceiptProcessed={handleReceiptProcessed}
              onProcessingStart={handleProcessingStart}
              onProcessingComplete={handleProcessingComplete}
              onError={(err) =>
                addToast({
                  message: err.userMessage || err.message || 'Upload failed',
                  type: 'error',
                })
              }
              compact
            />
          </div>

          <div className={`${sectionCls} flex-1 overflow-hidden flex flex-col`}>
            <div className="flex justify-between items-center mb-3">
              <h3 className="m-0 border-0 p-0 text-[1.1rem] text-[#333]">
                Receipts ({receipts.length})
              </h3>
              {receipts.length > 0 && (
                <button
                  type="button"
                  onClick={handleClearAll}
                  disabled={isUploading || isSaving || isLinking}
                  className="py-1.5 px-3 text-[0.8rem] bg-transparent border border-[#dc3545] text-[#dc3545] rounded cursor-pointer transition-all duration-200 hover:enabled:bg-[#dc3545] hover:enabled:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Clear All
                </button>
              )}
            </div>
            <SelectableReceiptTable
              receipts={receipts}
              selectedReceiptId={selectedReceiptId}
              onSelectReceipt={handleSelectReceipt}
              onRemoveReceipt={handleRemoveFromList}
              disabled={isSaving || isLinking}
            />
          </div>
        </div>

        <div className="flex flex-col gap-6 min-w-[350px]">
          <div className={`${sectionCls} flex-1 flex flex-col`}>
            <h3 className={sectionHeadingCls}>Receipt Image</h3>
            {selectedReceipt ? (
              <ImagePreview
                src={`/api/receipts/${selectedReceipt.receipt_id}/image`}
                alt="Receipt image"
                maxHeight="600px"
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-[#999] text-base min-h-[300px] bg-[#fafafa] rounded-lg border-2 border-dashed border-[#e0e0e0]">
                {receipts.length === 0
                  ? 'Upload receipts to get started'
                  : 'Select a receipt to view'}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-6 min-w-[580px] max-[1400px]:min-w-[420px] max-[1200px]:min-w-full">
          <div className={`${sectionCls} shrink-0`}>
            <h3 className={sectionHeadingCls}>Receipt Details</h3>
            {selectedReceipt ? (
              <div className="flex flex-col gap-5">
                {generalError && (
                  <div className="bg-[#f8d7da] text-[#721c24] py-3 px-4 rounded-md" role="alert">
                    {generalError}
                  </div>
                )}

                <div className={formGroupCls}>
                  <label htmlFor="vendor" className={labelCls}>
                    Vendor: <span className="text-[#dc3545]">*</span>
                  </label>
                  <input
                    id="vendor"
                    type="text"
                    {...register('vendor', { required: true })}
                    onChange={(e) => handleInputChange('vendor', e.target.value)}
                    placeholder="Enter vendor name"
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!errors.vendor}
                    className={`${inputCls} ${errors.vendor ? errorInputCls : ''}`}
                  />
                  {errors.vendor && errors.vendor.type === 'server' && (
                    <span className="text-[#dc2626] text-sm">
                      {errors.vendor.message}
                    </span>
                  )}
                </div>

                <div className={formGroupCls}>
                  <label htmlFor="date" className={labelCls}>Date:</label>
                  <input
                    id="date"
                    type="date"
                    {...register('date')}
                    onChange={(e) => handleInputChange('date', e.target.value)}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!errors.date}
                    className={`${inputCls} ${errors.date ? errorInputCls : ''}`}
                  />
                  {errors.date && errors.date.type === 'server' && (
                    <span className="text-[#dc2626] text-sm">{errors.date.message}</span>
                  )}
                </div>

                <div className={formGroupCls}>
                  <label htmlFor="amount" className={labelCls}>Amount:</label>
                  <input
                    id="amount"
                    type="number"
                    step="0.01"
                    {...register('amount')}
                    onChange={(e) => handleInputChange('amount', e.target.value)}
                    placeholder="Enter amount"
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!errors.amount}
                    className={`${inputCls} ${errors.amount ? errorInputCls : ''}`}
                  />
                  {errors.amount && errors.amount.type === 'server' && (
                    <span className="text-[#dc2626] text-sm">{errors.amount.message}</span>
                  )}
                </div>

                <div className="flex gap-3 mt-2">
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!canSave}
                    title="Save receipt without linking to a transaction"
                    className="flex-1 py-2.5 px-5 bg-[#28a745] text-white border-0 rounded-md cursor-pointer font-semibold text-[0.95rem] transition-colors duration-200 hover:enabled:bg-[#218838] disabled:bg-[#ccc] disabled:cursor-not-allowed"
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenCashModal}
                    disabled={!canGenerateCash}
                    title="Create a Cash-account transaction from this receipt"
                    className="py-2.5 px-5 bg-[#43a047] text-white border-0 rounded-md cursor-pointer text-sm font-medium transition-colors duration-200 hover:enabled:bg-[#2e7d32] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Generate Cash
                  </button>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={!canDelete}
                    className="py-2.5 px-5 bg-[#dc3545] text-white border-0 rounded-md cursor-pointer font-medium transition-colors duration-200 hover:enabled:bg-[#c82333] disabled:bg-[#ccc] disabled:cursor-not-allowed"
                  >
                    {isSaving ? 'Deleting...' : 'Delete'}
                  </button>
                </div>

                {selectedReceipt.status !== 'pending' && (
                  <div
                    className={`mt-3 py-2.5 rounded-md text-center font-semibold text-[0.9rem] ${
                      selectedReceipt.status === 'saved'
                        ? 'bg-[#d4edda] text-[#155724]'
                        : 'bg-[#cce5ff] text-[#004085]'
                    }`}
                  >
                    {selectedReceipt.status === 'saved' && '✓ Saved'}
                    {selectedReceipt.status === 'linked' && '✓ Linked to Transaction'}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-[#999] text-center py-8 px-4 text-[0.95rem]">
                Select a receipt to edit details
              </div>
            )}
          </div>

          <div className={`${sectionCls} flex-1 overflow-hidden flex flex-col`}>
            <h3 className={sectionHeadingCls}>Link to Transaction</h3>
            <div className="flex-1 overflow-y-auto min-h-0 max-h-[calc(100vh-550px)]">
              {selectedReceipt ? (
                selectedReceipt.status !== 'pending' ? (
                  <div className="text-[#999] text-center py-8 px-4 text-[0.95rem]">
                    This receipt has already been processed
                  </div>
                ) : isLoadingCandidates ? (
                  <div className="text-[#666] text-center py-6 text-[0.9rem]">
                    Loading candidate transactions...
                  </div>
                ) : (
                  <CandidateTransactions
                    transactions={candidateTransactions}
                    onSelectTransaction={handleSelectTransaction}
                    linkedTransactionId={linkedTransactionId}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                  />
                )
              ) : (
                <div className="text-[#999] text-center py-8 px-4 text-[0.95rem]">
                  Select a receipt to find matching transactions
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <GenerateCashFromReceiptModal
        isOpen={isCashModalOpen}
        onClose={() => setIsCashModalOpen(false)}
        onConfirm={handleGenerateCash}
        receiptData={editableData}
        suggestedPartyId={suggestedPartyId}
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

export default ProcessReceipts;
