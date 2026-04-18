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
import { ErrorCode } from '@/lib/apiErrors';
import { useToast } from '@/stores/toastStore';
import BulkUploadReceipts from './BulkUploadReceipts';
import SelectableReceiptTable from './SelectableReceiptTable';
import ImagePreview from './ImagePreview';
import CandidateTransactions from './CandidateTransactions';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ProcessReceipts');

/**
 * Maps backend `error.field` names → local form input ids.
 * A `null` value means "not user-editable — surface as a general
 * form error instead of highlighting an input."
 *
 * @type {Object<string, ?string>}
 */
const FIELD_MAP = {
  vendor: 'vendor',
  date: 'date',
  amount: 'amount',
  original_filename: null,
};

/**
 * A receipt item held in local session state.
 *
 * @typedef {Object} SessionReceipt
 * @property {number|string} receipt_id  - Server-assigned id.
 * @property {string} filename           - Original filename as uploaded.
 * @property {string} [stored_filename]  - Server-side stored name.
 * @property {string} [file_path]        - Server-side path.
 * @property {number} [page_number]      - For multi-page PDFs.
 * @property {Object} extracted_data     - OCR output (`vendor`, `date`,
 *           `amount`, `confidence`, `selected_method`, `raw_text`).
 * @property {'pending'|'saved'|'linked'} status
 * @property {number} [linked_transaction_id]
 */

/**
 * Receipt-processing page.
 *
 * Owns all session state (uploaded receipts live only in memory for
 * the life of this component) and wires together the upload, preview,
 * edit, and link-to-transaction flows.
 *
 * @component
 * @returns {JSX.Element}
 */
function ProcessReceipts() {
  const { addToast } = useToast();

  // ── Session data ──────────────────────────────────────────────────
  /** @type {[SessionReceipt[], Function]} */
  const [receipts, setReceipts] = useState([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState(null);

  /**
   * Tracks whether we've already auto-selected the first receipt of
   * the current upload batch. Stored in a ref so it survives re-renders
   * without triggering them, and is reset per batch in
   * {@link handleProcessingStart}.
   */
  const hasAutoSelectedRef = useRef(false);

  // ── Async flags ───────────────────────────────────────────────────
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLinking, setIsLinking] = useState(false);

  /**
   * Field-level validation errors keyed by input id
   * (`vendor` / `date` / `amount`), plus `_general` for form-scoped
   * errors that don't map to a single input.
   * @type {[Object<string,string>, Function]}
   */
  const [fieldErrors, setFieldErrors] = useState({});

  /** Editable copy of the selected receipt's extracted fields. */
  const [editableData, setEditableData] = useState({
    vendor: '',
    date: '',
    amount: '',
  });

  // ── Candidate-transaction search ─────────────────────────────────
  const [candidateTransactions, setCandidateTransactions] = useState([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  /** Id of the transaction just linked (highlighted in the list). */
  const [linkedTransactionId, setLinkedTransactionId] = useState(null);
  /**
   * Incremented to force a candidate refetch without changing form
   * data — used after a stale-link `NOT_FOUND` so the user doesn't
   * retry on a transaction that no longer exists.
   */
  const [candidateRefreshKey, setCandidateRefreshKey] = useState(0);

  /** The currently selected receipt object, or `undefined`. */
  const selectedReceipt = receipts.find((r) => r.receipt_id === selectedReceiptId);

  // ── Taxonomy reference data (loaded once for the cash modal) ─────
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [types, setTypes] = useState([]);
  const [parties, setParties] = useState([]);

  // ── Generate-cash modal ──────────────────────────────────────────
  const [isCashModalOpen, setIsCashModalOpen] = useState(false);
  /** Fuzzy-matched party id for the current receipt's vendor, or null. */
  const [suggestedPartyId, setSuggestedPartyId] = useState(null);
  const [isGeneratingCash, setIsGeneratingCash] = useState(false);


  // ── Effect: reset the edit form when selection changes ──────────
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

  // ── Effect: debounced candidate search ───────────────────────────
  /**
   * Refetches candidate transactions 500ms after the last edit to
   * vendor/date/amount. Requires at least a date or amount to search;
   * failures are logged but not toasted (an empty list is an
   * acceptable fallback).
   */
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

  // ── Effect: load taxonomy reference data once ───────────────────
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
        // Non-fatal — the cash modal will just start blank.
      }
    })();
  }, []);

  // ── Error routing ─────────────────────────────────────────────────

  /**
   * Route an `ApiError` to the appropriate UI surface.
   *
   * Priority:
   *  1. `err.field` maps via {@link FIELD_MAP} → inline under that input.
   *  2. Validation-ish code (`INVALID_VALUE` / `REQUIRED_FIELD`) with no
   *     recognised field → inline general banner.
   *  3. Anything else → toast.
   *
   * @param {Error & {code?: string, field?: string, userMessage?: string}} err
   * @param {string} fallbackMessage - Used if `err` has no message.
   */
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

  // ── Upload callbacks (from BulkUploadReceipts) ───────────────────

  /**
   * Called once per successfully processed file in the upload batch.
   * Appends the receipt to the session list and auto-selects the first
   * one of the batch.
   *
   * @param {Object} result - Server response for one file.
   */
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

  /** Upload batch started — lock UI and reset auto-select latch. */
  const handleProcessingStart = () => {
    setIsUploading(true);
    hasAutoSelectedRef.current = false;
  };

  /**
   * Upload batch finished.
   * @param {{succeeded: number, failed: number}} summary
   */
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

  // ── Create-item factory (mirrors CategorizeTransactions) ─────────
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

  // ── Form handlers ─────────────────────────────────────────────────

  /** Select a receipt from the list. */
  const handleSelectReceipt = (receiptId) => {
    setSelectedReceiptId(receiptId);
  };

  /**
   * Update one editable field and clear any inline error on it.
   * @param {'vendor'|'date'|'amount'} field
   * @param {string} value
   */
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

  /**
   * Assemble the `/receipts/confirm` payload from the selected receipt
   * + current form values.
   * @returns {?Object}
   */
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

  /**
   * Open the generate-cash modal. Fuzzy-match the current vendor
   * first so the party cascade can be pre-filled.
   */
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

  /**
   * Confirm the receipt, then create a Cash-account transaction
   * from it. Called from {@link GenerateCashFromReceiptModal}.
   *
   * @param {{partyId:number, isWithdrawal:boolean, isCredit:boolean, isKids:boolean, isOneOff:boolean}} opts
   */
  const handleGenerateCash = async ({ partyId, isWithdrawal, isCredit, isKids, isOneOff }) => {
    if (!selectedReceipt) return;

    setFieldErrors({});
    setIsGeneratingCash(true);

    try {
      // Step 1 — persist the (possibly edited) receipt fields.
      const receiptData = buildReceiptData();
      const saveResult = await confirmReceipt(receiptData);
      const receiptId =
        saveResult.data?.receipt?.id ||
        saveResult.receipt?.id ||
        saveResult.id ||
        selectedReceipt.receipt_id;

      if (!receiptId) {
        throw new Error('Failed to get receipt ID from save response');
      }

      // Step 2 — create the cash transaction.
      const result = await createCashTransactionFromReceipt({
        receiptId,
        partyId,
        isWithdrawal,
        isCredit,
        isKids,
        isOneOff
      });
      const txn = result?.data?.transaction ?? result?.transaction;

      // Step 3 — mark the receipt as linked in local session state.
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
      addToast({
        message: 'Cash transaction created from receipt',
        type: 'success',
        duration: 2500,
      });
      setTimeout(selectNextReceipt, 1000);
    } catch (err) {
      logger.error('Failed to generate cash transaction:', err);
      routeError(err, 'Failed to generate cash transaction');
      throw err; // let the modal reset its spinner
    } finally {
      setIsGeneratingCash(false);
    }
  };

  // ── Mutations ─────────────────────────────────────────────────────

  /**
   * Confirm (persist) the current receipt without linking it to a
   * transaction. Marks status `'saved'` and auto-advances to the next
   * pending receipt after a short pause.
   */
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
            : r
        )
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

  /**
   * Confirm the receipt **and** attach it to the chosen transaction.
   *
   * Two-step:
   *  1. `confirmReceipt` to persist the (possibly edited) attributes
   *     and obtain the canonical receipt id.
   *  2. `updateTransaction(txn.id, { receipt_id })` to link.
   *
   * Handles the race where the transaction was deleted between
   * candidate fetch and click by refreshing candidates instead of
   * showing a hard error.
   *
   * @param {Object} transaction - Candidate transaction clicked in the list.
   */
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

      if (!receiptId) {
        throw new Error('Failed to get receipt ID from save response');
      }

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
          message: 'That transaction no longer exists. Refreshing candidates\u2026',
          type: 'info',
        });
        setCandidateRefreshKey((k) => k + 1);
      } else {
        routeError(err, 'Failed to link receipt');
      }
    } finally {
      setIsLinking(false);
    }
  };

  /**
   * Discard the selected (pending) receipt on the server and remove it
   * from the session list. If the server reports `NOT_FOUND`, treat it
   * as already-deleted and clean up locally anyway.
   */
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

  // ── Navigation helpers ────────────────────────────────────────────

  /**
   * Remove a receipt from the session list **without** calling the
   * server (it may already be saved/linked). Keeps a sensible
   * selection afterward.
   * @param {number|string} receiptId
   */
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

  /**
   * Advance selection to the next `'pending'` receipt (after the
   * current one if possible, otherwise wrap to the first). No-op if
   * nothing is pending.
   */
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

  /** Wipe all session state (local only; does not touch the server). */
  const handleClearAll = () => {
    setReceipts([]);
    setSelectedReceiptId(null);
    setEditableData({ vendor: '', date: '', amount: '' });
    setCandidateTransactions([]);
    setFieldErrors({});
    hasAutoSelectedRef.current = false;
  };

  // ── Derived flags ─────────────────────────────────────────────────

  /** Save is enabled only for pending receipts with a non-blank vendor. */
  const canSave =
    selectedReceipt &&
    selectedReceipt.status === 'pending' &&
    editableData.vendor.trim() !== '' &&
    !isSaving &&
    !isLinking;

  const canDelete =
    selectedReceipt && selectedReceipt.status === 'pending' && !isSaving && !isLinking;

  /** Generate-cash requires vendor, date and amount to all be present. */
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
    <div className="mx-auto max-w-[calc(100vw-4rem)] px-8 py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="m-0">Process Receipts</h1>
        <div className="flex items-center gap-4">
          {receipts.length > 0 && (
            <span className="rounded-[20px] bg-nav-bg px-4 py-2 text-[0.9rem] text-text-muted">
              {pendingCount} pending, {processedCount} processed
            </span>
          )}
        </div>
      </div>

      <div className="grid min-h-[calc(100vh-200px)] grid-cols-[minmax(520px,600px)_minmax(400px,1fr)_minmax(600px,700px)] gap-8 max-[1600px]:grid-cols-[minmax(480px,550px)_minmax(350px,1fr)_minmax(500px,600px)] max-[1600px]:gap-6 max-[1400px]:grid-cols-[minmax(450px,500px)_minmax(320px,1fr)_minmax(450px,500px)] max-[1400px]:gap-5 max-[1200px]:grid-cols-1 max-[1200px]:grid-rows-[auto] min-[1920px]:grid-cols-[minmax(550px,650px)_minmax(450px,1fr)_minmax(650px,750px)]">
        {/* ── Left: upload + session list ── */}
        <div className="flex flex-col gap-6 min-[1401px]:min-w-[500px] max-[1400px]:min-w-[420px] max-[1200px]:min-w-full">
          <div className="shrink-0 rounded-[10px] bg-surface p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]">
            <h3 className="m-0 mb-4 border-b-2 border-nav-bg pb-3 text-[1.1rem] text-text-dark">Upload Receipts</h3>
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
              compact={true}
            />
          </div>

          <div className="flex flex-1 flex-col overflow-hidden rounded-[10px] bg-surface p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="m-0 border-none p-0 text-[1.1rem] text-text-dark">Receipts ({receipts.length})</h3>
              {receipts.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="cursor-pointer rounded border border-danger-alt bg-transparent px-3 py-1.5 text-[0.8rem] text-danger-alt transition-all duration-200 hover:enabled:bg-danger-alt hover:enabled:text-white disabled:cursor-not-allowed disabled:opacity-50"
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
        <div className="flex flex-col gap-6 min-w-[350px] max-[1200px]:min-w-full">
          <div className="flex flex-1 flex-col rounded-[10px] bg-surface p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]">
            <h3 className="m-0 mb-4 border-b-2 border-nav-bg pb-3 text-[1.1rem] text-text-dark">Receipt Image</h3>
            {selectedReceipt ? (
              <ImagePreview
                src={`/api/receipts/${selectedReceipt.receipt_id}/image`}
                alt="Receipt image"
                maxHeight="600px"
              />
            ) : (
              <div className="flex min-h-[300px] flex-1 items-center justify-center rounded-lg border-2 border-dashed border-[#e0e0e0] bg-[#fafafa] text-base text-[#999]">
                {receipts.length === 0
                  ? 'Upload receipts to get started'
                  : 'Select a receipt to view'}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: details form + candidate transactions ── */}
        <div className="flex flex-col gap-6 min-[1401px]:min-w-[580px] max-[1400px]:min-w-[420px] max-[1200px]:min-w-full">
          <div className="shrink-0 rounded-[10px] bg-surface p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]">
            <h3 className="m-0 mb-4 border-b-2 border-nav-bg pb-3 text-[1.1rem] text-text-dark">Receipt Details</h3>
            {selectedReceipt ? (
              <div className="flex flex-col gap-5">
                {fieldErrors._general && (
                  <div className="rounded-md bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24]" role="alert">
                    {fieldErrors._general}
                  </div>
                )}

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="vendor" className="text-[0.9rem] font-semibold text-border-dark">
                    Vendor: <span className="text-danger-alt">*</span>
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
                    className="rounded-md border border-border px-3 py-2.5 text-[0.95rem] transition-[border-color,box-shadow] duration-200 focus:border-primary focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)] focus:outline-none disabled:cursor-not-allowed disabled:bg-[#f5f5f5] disabled:text-[#999]"
                  />
                  {fieldErrors.vendor && (
                    <span id="vendor-error" className="mt-1.5 block text-sm text-[#dc2626]">
                      {fieldErrors.vendor}
                    </span>
                  )}
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="date" className="text-[0.9rem] font-semibold text-border-dark">Date:</label>
                  <input
                    id="date"
                    type="date"
                    value={editableData.date}
                    onChange={(e) => handleInputChange('date', e.target.value)}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.date}
                    aria-describedby={fieldErrors.date ? 'date-error' : undefined}
                    className="rounded-md border border-border px-3 py-2.5 text-[0.95rem] transition-[border-color,box-shadow] duration-200 focus:border-primary focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)] focus:outline-none disabled:cursor-not-allowed disabled:bg-[#f5f5f5] disabled:text-[#999]"
                  />
                  {fieldErrors.date && (
                    <span id="date-error" className="mt-1.5 block text-sm text-[#dc2626]">
                      {fieldErrors.date}
                    </span>
                  )}
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="amount" className="text-[0.9rem] font-semibold text-border-dark">Amount:</label>
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
                    className="rounded-md border border-border px-3 py-2.5 text-[0.95rem] transition-[border-color,box-shadow] duration-200 focus:border-primary focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)] focus:outline-none disabled:cursor-not-allowed disabled:bg-[#f5f5f5] disabled:text-[#999]"
                  />
                  {fieldErrors.amount && (
                    <span id="amount-error" className="mt-1.5 block text-sm text-[#dc2626]">
                      {fieldErrors.amount}
                    </span>
                  )}
                </div>

                <div className="mt-2 flex gap-3">
                  <button
                    onClick={handleSave}
                    className="flex-1 cursor-pointer rounded-md border-none bg-success px-5 py-2.5 text-[0.95rem] font-semibold text-white transition-colors duration-200 hover:enabled:bg-success-hover disabled:cursor-not-allowed disabled:bg-[#ccc]"
                    disabled={!canSave}
                    title="Save receipt without linking to a transaction"
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    onClick={handleOpenCashModal}
                    className="cursor-pointer rounded border-none bg-[#43a047] px-5 py-2.5 text-sm font-medium text-white transition-colors duration-200 hover:enabled:bg-[#2e7d32] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canGenerateCash}
                    title="Create a Cash-account transaction from this receipt"
                  >
                    Generate Cash
                  </button>
                  <button
                    onClick={handleDelete}
                    className="cursor-pointer rounded-md border-none bg-danger-alt px-5 py-2.5 font-medium text-white transition-colors duration-200 hover:enabled:bg-[#c82333] disabled:cursor-not-allowed disabled:bg-[#ccc]"
                    disabled={!canDelete}
                  >
                    {isSaving ? 'Deleting...' : 'Delete'}
                  </button>
                </div>

                {selectedReceipt.status !== 'pending' && (
                  <div
                    className={`mt-3 rounded-md p-2.5 text-center text-[0.9rem] font-semibold ${
                      selectedReceipt.status === 'saved'
                        ? 'bg-[#d4edda] text-[#155724]'
                        : 'bg-[#cce5ff] text-[#004085]'
                    }`}
                  >
                    {selectedReceipt.status === 'saved' && '\u2713 Saved'}
                    {selectedReceipt.status === 'linked' && '\u2713 Linked to Transaction'}
                  </div>
                )}
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-[0.95rem] text-[#999]">Select a receipt to edit details</div>
            )}
          </div>

          <div className="flex flex-1 flex-col overflow-hidden rounded-[10px] bg-surface p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]">
            <h3 className="m-0 mb-4 border-b-2 border-nav-bg pb-3 text-[1.1rem] text-text-dark">Link to Transaction</h3>
            <div className="min-h-0 flex-1 overflow-y-auto max-h-[calc(100vh-550px)] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-[#f1f1f1] [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-text-light [&::-webkit-scrollbar-thumb:hover]:bg-[#555]">
              {selectedReceipt ? (
                selectedReceipt.status !== 'pending' ? (
                  <div className="px-4 py-8 text-center text-[0.95rem] text-[#999]">This receipt has already been processed</div>
                ) : isLoadingCandidates ? (
                  <div className="p-6 text-center text-[0.9rem] text-text-muted">Loading candidate transactions...</div>
                ) : (
                  <CandidateTransactions
                    transactions={candidateTransactions}
                    onSelectTransaction={handleSelectTransaction}
                    linkedTransactionId={linkedTransactionId}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                  />
                )
              ) : (
                <div className="px-4 py-8 text-center text-[0.95rem] text-[#999]">Select a receipt to find matching transactions</div>
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
