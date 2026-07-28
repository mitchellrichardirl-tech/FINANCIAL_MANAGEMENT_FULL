/**
 * @file ProcessReceipts.jsx
 * Top-level page for the receipt-processing workflow.
 *
 * Three-column layout:
 *  - **Left**  — upload dropzone + list of receipts in this session.
 *  - **Middle** — image/PDF preview of the selected receipt.
 *  - **Right** — editable OCR-extracted fields (vendor / date / amount)
 *    and a list of candidate bank transactions the receipt can be
 *    linked to.
 *
 * Each uploaded receipt moves through states:
 *   `'pending'` → `'saved'` (confirmed, no txn) or `'linked'`
 *   (confirmed + attached to a transaction).
 *
 * Error surfacing:
 *  - Validation errors targeting a known form field → inline under
 *    that input (see {@link FIELD_MAP} / `fieldErrors`).
 *  - Other validation errors → inline banner (`fieldErrors._general`).
 *  - Everything else → toast.
 */

import { useState, useEffect, useRef } from 'react';
import { updateTransaction } from '@/features/transactions/api';
import {
  confirmReceipt,
  deleteReceipt,
  getCandidateTransactions,
  matchParty,
  createCashTransactionFromReceipt,
} from './api';
import {
  getCategories,
  getSubCategories,
  getTypes,
  getParties,
  createCategory,
  createSubCategory,
  createType,
  createParty,
} from '@/features/transactions/api';
import GenerateCashFromReceiptModal from './GenerateCashFromReceiptModal';
import { ErrorCode, parseApiError } from '@/lib/apiErrors';
import { useToast } from '@/components/ToastContext';
import BulkUploadReceipts from './BulkUploadReceipts';
import SelectableReceiptTable from './SelectableReceiptTable';
import ImagePreview from './ImagePreview';
import CandidateTransactions from './CandidateTransactions';
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ProcessReceipts');
const FIELD_MAP = {
  vendor: 'vendor',
  date: 'date',
  amount: 'amount',
  original_filename: null,
};
/* ── Reused class strings ──────────────────────────────────────────── */
const GRID = [
  'grid grid-cols-1 gap-5 flex-1 min-h-0',
  'min-[1200px]:grid-cols-[minmax(450px,500px)_minmax(320px,1fr)_minmax(450px,500px)]',
  'min-[1400px]:grid-cols-[minmax(480px,550px)_minmax(350px,1fr)_minmax(500px,600px)] min-[1400px]:gap-6',
  'min-[1600px]:grid-cols-[minmax(520px,600px)_minmax(400px,1fr)_minmax(600px,700px)] min-[1600px]:gap-8',
  'min-[1920px]:grid-cols-[minmax(550px,650px)_minmax(450px,1fr)_minmax(650px,750px)]',
].join(' ');
const COLUMN = 'flex min-h-0 flex-col gap-6';
const CARD = 'rounded-[10px] bg-white p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]';
const SECTION_H3 =
  'mb-4 border-b-2 border-[#f0f0f0] pb-3 text-[1.1rem] font-semibold text-gray-800';
const EMPTY = 'px-4 py-8 text-center text-[0.95rem] text-gray-400';
const INPUT_CLS = [
  'w-full rounded-md border border-gray-300 px-3 py-2.5 text-[0.95rem]',
  'transition-[border-color,box-shadow]',
  'focus:outline-none focus:border-[#007bff] focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)]',
  'disabled:bg-gray-100 disabled:cursor-not-allowed disabled:text-gray-400',
].join(' ');
const BTN_DIS = 'disabled:cursor-not-allowed disabled:bg-gray-300';
const SCROLLBAR = [
  '[&::-webkit-scrollbar]:w-2',
  '[&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-gray-100',
  '[&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-gray-400',
  '[&::-webkit-scrollbar-thumb:hover]:bg-gray-500',
].join(' ');
/* ─────────────────────────────────────────────────────────────────── */
function ProcessReceipts() {
  const { addToast } = useToast();
  // ── State, effects, handlers ────────────────────────────────────
  // (all identical to original — only the render JSX changes)
  const [receipts, setReceipts] = useState([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState(null);
  const hasAutoSelectedRef = useRef(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [editableData, setEditableData] = useState({
    vendor: '',
    date: '',
    amount: '',
  });
  const [candidateTransactions, setCandidateTransactions] = useState([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [linkedTransactionId, setLinkedTransactionId] = useState(null);
  const [candidateRefreshKey, setCandidateRefreshKey] = useState(0);
  const selectedReceipt = receipts.find((r) => r.receipt_id === selectedReceiptId);
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [types, setTypes] = useState([]);
  const [parties, setParties] = useState([]);
  const [isCashModalOpen, setIsCashModalOpen] = useState(false);
  const [suggestedPartyId, setSuggestedPartyId] = useState(null);
  const [isGeneratingCash, setIsGeneratingCash] = useState(false);
  useEffect(() => {
    if (selectedReceipt) {
      const extracted = selectedReceipt.extracted_data || {};
      setEditableData({
        vendor: extracted.vendor || '',
        date: extracted.date ? extracted.date.split('T')[0] : '',
        amount: extracted.amount?.toString() || '',
      });
      setLinkedTransactionId(null);
      setFieldErrors({});
    } else {
      setEditableData({ vendor: '', date: '', amount: '' });
      setCandidateTransactions([]);
      setFieldErrors({});
    }
  }, [selectedReceiptId, selectedReceipt]);
  useEffect(() => {
    if (!selectedReceipt) {
      setCandidateTransactions([]);
      return;
    }
    if (!editableData.date && !editableData.amount) {
      setCandidateTransactions([]);
      return;
    }
    const fetchCandidates = async () => {
      setIsLoadingCandidates(true);
      try {
        const params = {
          date: editableData.date || null,
          amount: editableData.amount ? parseFloat(editableData.amount) : null,
          vendor: editableData.vendor || null,
        };
        const response = await getCandidateTransactions(params);
        if (response.success && response.data?.transactions) {
          setCandidateTransactions(response.data.transactions);
        } else {
          setCandidateTransactions([]);
        }
      } catch (err) {
        logger.error('Failed to fetch candidate transactions:', err);
        setCandidateTransactions([]);
      } finally {
        setIsLoadingCandidates(false);
      }
    };
    const timeoutId = setTimeout(fetchCandidates, 500);
    return () => clearTimeout(timeoutId);
  }, [
    editableData.date,
    editableData.amount,
    editableData.vendor,
    selectedReceipt,
    candidateRefreshKey,
  ]);
  useEffect(() => {
    (async () => {
      try {
        const [cats, subs, ts, ps] = await Promise.all([
          getCategories(),
          getSubCategories(),
          getTypes(),
          getParties(),
        ]);
        setCategories(cats);
        setSubCategories(subs);
        setTypes(ts);
        setParties(ps);
      } catch (err) {
        logger.error('Failed to load taxonomy:', err);
      }
    })();
  }, []);
  const routeError = (err, fallbackMessage) => {
    const message = err.userMessage || err.message || fallbackMessage;
    const mappedField = err.field ? FIELD_MAP[err.field] : null;
    if (mappedField) {
      setFieldErrors({ [mappedField]: message });
      return;
    }
    if (err.code === ErrorCode.INVALID_VALUE || err.code === ErrorCode.REQUIRED_FIELD) {
      setFieldErrors({ _general: message });
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
  const makeCreateHandler =
    (label, createFn, refetchFn, setFn, findFn) =>
    async (...args) => {
      const response = await createFn(...args);
      const fresh = await refetchFn();
      setFn(fresh);
      addToast({ message: `${label} "${args[0]}" created`, type: 'success', duration: 2500 });
      return findFn(fresh, ...args) || response;
    };
  const handleCategoryCreated = makeCreateHandler(
    'Category', createCategory, getCategories, setCategories,
    (list, name) => list.find((c) => c.category === name),
  );
  const handleSubCategoryCreated = makeCreateHandler(
    'Sub-category', createSubCategory, getSubCategories, setSubCategories,
    (list, name, catId) => list.find((s) => s.sub_category === name && s.category_id === catId),
  );
  const handleTypeCreated = makeCreateHandler(
    'Type', createType, getTypes, setTypes,
    (list, name, subId) => list.find((t) => t.type === name && t.sub_category_id === subId),
  );
  const handlePartyCreated = makeCreateHandler(
    'Party', createParty, getParties, setParties,
    (list, name, typeId) => list.find((p) => p.name === name && p.type_id === typeId),
  );
  const handleSelectReceipt = (receiptId) => {
    setSelectedReceiptId(receiptId);
  };
  const handleInputChange = (field, value) => {
    setEditableData((prev) => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
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
      const match = await matchParty(editableData.vendor);
      if (match?.party_id) setSuggestedPartyId(match.party_id);
    } catch (err) {
      logger.warn('Party match failed (non-fatal):', err);
    }
    setIsCashModalOpen(true);
  };
  const handleGenerateCash = async ({ partyId, isWithdrawal, isCredit, isKids, isOneOff }) => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsGeneratingCash(true);
    try {
      const receiptData = buildReceiptData();
      const saveResult = await confirmReceipt(receiptData);
      const receiptId =
        saveResult.data?.receipt?.id ||
        saveResult.receipt?.id ||
        saveResult.id ||
        selectedReceipt.receipt_id;
      if (!receiptId) throw new Error('Failed to get receipt ID from save response');
      const result = await createCashTransactionFromReceipt({
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
    } finally {
      setIsGeneratingCash(false);
    }
  };
  const handleSave = async () => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsSaving(true);
    try {
      const receiptData = buildReceiptData();
      logger.debug('Saving receipt data:', receiptData);
      await confirmReceipt(receiptData);
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
            : r,
        ),
      );
      addToast({ message: 'Receipt saved', type: 'success', duration: 2000 });
      setTimeout(selectNextReceipt, 800);
    } catch (err) {
      logger.error('Failed to save receipt:', err);
      routeError(err, 'Failed to save receipt');
    } finally {
      setIsSaving(false);
    }
  };
  const handleSelectTransaction = async (transaction) => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsLinking(true);
    try {
      const receiptData = buildReceiptData();
      logger.debug('Saving receipt before linking:', receiptData);
      const saveResult = await confirmReceipt(receiptData);
      const receiptId =
        saveResult.data?.receipt?.id ||
        saveResult.receipt?.id ||
        saveResult.id ||
        selectedReceipt.receipt_id;
      if (!receiptId) throw new Error('Failed to get receipt ID from save response');
      logger.debug(`Linking transaction ${transaction.id} to receipt ${receiptId}`);
      await updateTransaction(transaction.id, { receipt_id: receiptId });
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
            : r,
        ),
      );
      setLinkedTransactionId(transaction.id);
      addToast({ message: 'Receipt linked to transaction', type: 'success', duration: 2500 });
      setTimeout(selectNextReceipt, 1000);
    } catch (err) {
      logger.error('Failed to link receipt to transaction:', err);
      if (err.code === ErrorCode.NOT_FOUND && err.entity === 'Transaction') {
        addToast({ message: 'That transaction no longer exists. Refreshing candidates…', type: 'info' });
        setCandidateRefreshKey((k) => k + 1);
      } else {
        routeError(err, 'Failed to link receipt');
      }
    } finally {
      setIsLinking(false);
    }
  };
  const handleDelete = async () => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsSaving(true);
    try {
      logger.debug('Deleting receipt:', selectedReceipt.receipt_id);
      await deleteReceipt(selectedReceipt.receipt_id);
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
    } finally {
      setIsSaving(false);
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
      (r) => r.status === 'pending' && r.receipt_id !== selectedReceiptId,
    );
    if (pending.length > 0) {
      const nextAfter = pending.find((r) => receipts.indexOf(r) > currentIndex);
      setSelectedReceiptId(nextAfter?.receipt_id || pending[0].receipt_id);
    }
  };
  const handleClearAll = () => {
    setReceipts([]);
    setSelectedReceiptId(null);
    setEditableData({ vendor: '', date: '', amount: '' });
    setCandidateTransactions([]);
    setFieldErrors({});
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
  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="mx-auto flex h-full max-w-[calc(100vw-4rem)] flex-1 flex-col px-8 py-6">
      <div className="shrink-0">
        <h1 className="text-2xl font-bold">Process Receipts</h1>
        <div className="flex items-center gap-4">
          {receipts.length > 0 && (
            <span className="rounded-full bg-[#f0f0f0] px-4 py-2 text-sm text-gray-500">
              {pendingCount} pending, {processedCount} processed
            </span>
          )}
        </div>
      </div>
      <div className={GRID}>
        {/* ── Left: upload + session list ── */}
        <div className={`${COLUMN} min-[1200px]:min-w-[420px] min-[1400px]:min-w-[500px]`}>
          <div className={`${CARD} shrink-0`}>
            <h3 className={SECTION_H3}>Upload Receipts</h3>
            <BulkUploadReceipts
              onReceiptProcessed={handleReceiptProcessed}
              onProcessingStart={handleProcessingStart}
              onProcessingComplete={handleProcessingComplete}
              onError={(err) => addToast({ message: err, type: 'error' })}
              compact={true}
            />
          </div>
          <div className={`${CARD} min-h-0 flex-1 overflow-y-auto`}>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[1.1rem] font-semibold text-gray-800">
                Receipts ({receipts.length})
              </h3>
              {receipts.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="cursor-pointer rounded border border-[#dc3545] bg-transparent px-3 py-1.5 text-[0.8rem] text-[#dc3545] transition-all hover:bg-[#dc3545] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isUploading || isSaving || isLinking}
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
        {/* ── Middle: image preview ── */}
        <div className={`${COLUMN} min-[1200px]:min-w-[350px]`}>
          <div className={`${CARD} flex flex-1 flex-col`}>
            <h3 className={SECTION_H3}>Receipt Image</h3>
            {selectedReceipt ? (
              <ImagePreview
                src={`/api/receipts/${selectedReceipt.receipt_id}/image`}
                alt="Receipt image"
                maxHeight="600px"
              />
            ) : (
              <div className="flex flex-1 items-center justify-center min-h-[300px] rounded-lg border-2 border-dashed border-[#e0e0e0] bg-gray-50 text-base text-gray-400">
                {receipts.length === 0
                  ? 'Upload receipts to get started'
                  : 'Select a receipt to view'}
              </div>
            )}
          </div>
        </div>
        {/* ── Right: details form + candidate transactions ── */}
        <div className={`${COLUMN} min-[1200px]:min-w-[420px] min-[1400px]:min-w-[580px]`}>
          <div className={`${CARD} shrink-0`}>
            <h3 className={SECTION_H3}>Receipt Details</h3>
            {selectedReceipt ? (
              <div className="flex flex-col gap-5">
                {fieldErrors._general && (
                  <div
                    className="rounded border border-danger-border bg-danger-bg px-3 py-2.5 text-sm text-danger-text"
                    role="alert"
                  >
                    {fieldErrors._general}
                  </div>
                )}
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="vendor" className="text-sm font-semibold text-[#444]">
                    Vendor: <span className="text-[#dc3545]">*</span>
                  </label>
                  <input
                    id="vendor"
                    type="text"
                    value={editableData.vendor}
                    onChange={(e) => handleInputChange('vendor', e.target.value)}
                    placeholder="Enter vendor name"
                    required
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.vendor}
                    aria-describedby={fieldErrors.vendor ? 'vendor-error' : undefined}
                    className={INPUT_CLS}
                  />
                  {fieldErrors.vendor && (
                    <span id="vendor-error" className="text-sm text-red-600">
                      {fieldErrors.vendor}
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="date" className="text-sm font-semibold text-[#444]">
                    Date:
                  </label>
                  <input
                    id="date"
                    type="date"
                    value={editableData.date}
                    onChange={(e) => handleInputChange('date', e.target.value)}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.date}
                    aria-describedby={fieldErrors.date ? 'date-error' : undefined}
                    className={INPUT_CLS}
                  />
                  {fieldErrors.date && (
                    <span id="date-error" className="text-sm text-red-600">
                      {fieldErrors.date}
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="amount" className="text-sm font-semibold text-[#444]">
                    Amount:
                  </label>
                  <input
                    id="amount"
                    type="number"
                    step="0.01"
                    value={editableData.amount}
                    onChange={(e) => handleInputChange('amount', e.target.value)}
                    placeholder="Enter amount"
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.amount}
                    aria-describedby={fieldErrors.amount ? 'amount-error' : undefined}
                    className={INPUT_CLS}
                  />
                  {fieldErrors.amount && (
                    <span id="amount-error" className="text-sm text-red-600">
                      {fieldErrors.amount}
                    </span>
                  )}
                </div>
                <div className="mt-2 flex gap-3">
                  <button
                    onClick={handleSave}
                    className={`flex-1 cursor-pointer rounded-md bg-[#28a745] px-5 py-2.5 text-[0.95rem] font-semibold text-white transition-colors hover:bg-[#218838] ${BTN_DIS}`}
                    disabled={!canSave}
                    title="Save receipt without linking to a transaction"
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    onClick={handleOpenCashModal}
                    className="cursor-pointer rounded bg-[#43a047] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#2e7d32] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canGenerateCash}
                    title="Create a Cash-account transaction from this receipt"
                  >
                    Generate Cash
                  </button>
                  <button
                    onClick={handleDelete}
                    className={`cursor-pointer rounded-md bg-[#dc3545] px-5 py-2.5 font-medium text-white transition-colors hover:bg-[#c82333] ${BTN_DIS}`}
                    disabled={!canDelete}
                  >
                    {isSaving ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
                {selectedReceipt.status !== 'pending' && (
                  <div
                    className={`mt-3 rounded-md p-2.5 text-center text-sm font-semibold ${
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
              <div className={EMPTY}>Select a receipt to edit details</div>
            )}
          </div>
          <div className={`${CARD} flex min-h-0 flex-1 flex-col`}>
            <h3 className={SECTION_H3}>Link to Transaction</h3>
            <div className={`min-h-0 flex-1 overflow-y-auto ${SCROLLBAR}`}>
              {selectedReceipt ? (
                selectedReceipt.status !== 'pending' ? (
                  <div className={EMPTY}>This receipt has already been processed</div>
                ) : isLoadingCandidates ? (
                  <div className="py-6 text-center text-sm text-gray-500">
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
                <div className={EMPTY}>Select a receipt to find matching transactions</div>
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