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
import { confirmReceipt, deleteReceipt, getCandidateTransactions } from './api';
import { ErrorCode } from '@/lib/apiErrors';
import { useToast } from '@/components/ToastContext';
import BulkUploadReceipts from './BulkUploadReceipts';
import SelectableReceiptTable from './SelectableReceiptTable';
import ImagePreview from './ImagePreview';
import CandidateTransactions from './CandidateTransactions';
import './ProcessReceipts.css';
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
          message: 'That transaction no longer exists. Refreshing candidates…',
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

  const pendingCount = receipts.filter((r) => r.status === 'pending').length;
  const processedCount = receipts.filter((r) => r.status !== 'pending').length;

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="process-receipts">
      <div className="page-header">
        <h1>Process Receipts</h1>
        <div className="header-stats">
          {receipts.length > 0 && (
            <span className="stats-text">
              {pendingCount} pending, {processedCount} processed
            </span>
          )}
        </div>
      </div>

      <div className="three-column-layout">
        {/* ── Left: upload + session list ── */}
        <div className="column column-left">
          <div className="column-section upload-section">
            <h3>Upload Receipts</h3>
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

          <div className="column-section receipt-list-section">
            <div className="section-header">
              <h3>Receipts ({receipts.length})</h3>
              {receipts.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="btn-clear-all"
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
        <div className="column column-middle">
          <div className="column-section image-section">
            <h3>Receipt Image</h3>
            {selectedReceipt ? (
              <ImagePreview
                src={`/api/receipts/${selectedReceipt.receipt_id}/image`}
                alt="Receipt image"
                maxHeight="600px"
              />
            ) : (
              <div className="empty-state">
                {receipts.length === 0
                  ? 'Upload receipts to get started'
                  : 'Select a receipt to view'}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: details form + candidate transactions ── */}
        <div className="column column-right">
          <div className="column-section details-section">
            <h3>Receipt Details</h3>
            {selectedReceipt ? (
              <div className="receipt-form">
                {fieldErrors._general && (
                  <div className="form-error" role="alert">
                    {fieldErrors._general}
                  </div>
                )}

                <div className={`form-group ${fieldErrors.vendor ? 'has-error' : ''}`}>
                  <label htmlFor="vendor">
                    Vendor: <span className="required">*</span>
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
                  />
                  {fieldErrors.vendor && (
                    <span id="vendor-error" className="field-error">
                      {fieldErrors.vendor}
                    </span>
                  )}
                </div>

                <div className={`form-group ${fieldErrors.date ? 'has-error' : ''}`}>
                  <label htmlFor="date">Date:</label>
                  <input
                    id="date"
                    type="date"
                    value={editableData.date}
                    onChange={(e) => handleInputChange('date', e.target.value)}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.date}
                    aria-describedby={fieldErrors.date ? 'date-error' : undefined}
                  />
                  {fieldErrors.date && (
                    <span id="date-error" className="field-error">
                      {fieldErrors.date}
                    </span>
                  )}
                </div>

                <div className={`form-group ${fieldErrors.amount ? 'has-error' : ''}`}>
                  <label htmlFor="amount">Amount:</label>
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
                  />
                  {fieldErrors.amount && (
                    <span id="amount-error" className="field-error">
                      {fieldErrors.amount}
                    </span>
                  )}
                </div>

                <div className="form-actions">
                  <button
                    onClick={handleSave}
                    className="btn-save"
                    disabled={!canSave}
                    title="Save receipt without linking to a transaction"
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  <button onClick={handleDelete} className="btn-delete" disabled={!canDelete}>
                    {isSaving ? 'Deleting...' : 'Delete'}
                  </button>
                </div>

                {selectedReceipt.status !== 'pending' && (
                  <div className={`status-badge status-${selectedReceipt.status}`}>
                    {selectedReceipt.status === 'saved' && '✓ Saved'}
                    {selectedReceipt.status === 'linked' && '✓ Linked to Transaction'}
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-state">Select a receipt to edit details</div>
            )}
          </div>

          <div className="column-section candidates-section">
            <h3>Link to Transaction</h3>
            <div className="candidates-container">
              {selectedReceipt ? (
                selectedReceipt.status !== 'pending' ? (
                  <div className="empty-state">This receipt has already been processed</div>
                ) : isLoadingCandidates ? (
                  <div className="loading-candidates">Loading candidate transactions...</div>
                ) : (
                  <CandidateTransactions
                    transactions={candidateTransactions}
                    onSelectTransaction={handleSelectTransaction}
                    linkedTransactionId={linkedTransactionId}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                  />
                )
              ) : (
                <div className="empty-state">Select a receipt to find matching transactions</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProcessReceipts;