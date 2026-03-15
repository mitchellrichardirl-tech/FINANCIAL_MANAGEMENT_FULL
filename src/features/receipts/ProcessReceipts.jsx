import { useState, useEffect, useRef } from "react";
import { updateTransaction } from "@/features/transactions/api";
import { confirmReceipt, deleteReceipt, getCandidateTransactions } from "./api";
import { ErrorCode } from "@/lib/apiErrors";
import { useToast } from "@/components/ToastContext";
import BulkUploadReceipts from "./BulkUploadReceipts";
import SelectableReceiptTable from "./SelectableReceiptTable";
import ImagePreview from "./ImagePreview";
import CandidateTransactions from "./CandidateTransactions";
import './ProcessReceipts.css';
import { createLogger } from "@/lib/logger";

const logger = createLogger('ProcessReceipts');

// Map backend field names to our input IDs
const FIELD_MAP = {
  vendor: 'vendor',
  date: 'date',
  amount: 'amount',
  // Backend may send the column name rather than the form field name
  original_filename: null,  // not user-editable, show as general error
};

function ProcessReceipts() {
  const { addToast } = useToast();

  const [receipts, setReceipts] = useState([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState(null);
  const hasAutoSelectedRef = useRef(false);

  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLinking, setIsLinking] = useState(false);

  // Field-level errors: { vendor: '...', amount: '...', date: '...' }
  const [fieldErrors, setFieldErrors] = useState({});

  const [editableData, setEditableData] = useState({
    vendor: "",
    date: "",
    amount: ""
  });

  const [candidateTransactions, setCandidateTransactions] = useState([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [linkedTransactionId, setLinkedTransactionId] = useState(null);

  // Bump this to force a candidate refetch (e.g. after a stale link attempt)
  const [candidateRefreshKey, setCandidateRefreshKey] = useState(0);

  const selectedReceipt = receipts.find(r => r.receipt_id === selectedReceiptId);

  // ── Reset form when selection changes ──
  useEffect(() => {
    if (selectedReceipt) {
      const extracted = selectedReceipt.extracted_data || {};
      setEditableData({
        vendor: extracted.vendor || "",
        date: extracted.date ? extracted.date.split('T')[0] : "",
        amount: extracted.amount?.toString() || ""
      });
      setLinkedTransactionId(null);
      setFieldErrors({});
    } else {
      setEditableData({ vendor: "", date: "", amount: "" });
      setCandidateTransactions([]);
      setFieldErrors({});
    }
  }, [selectedReceiptId, selectedReceipt]);

  // ── Fetch candidate transactions (debounced) ──
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
          vendor: editableData.vendor || null
        };

        const response = await getCandidateTransactions(params);

        if (response.success && response.data?.transactions) {
          setCandidateTransactions(response.data.transactions);
        } else {
          setCandidateTransactions([]);
        }
      } catch (err) {
        // Search failures are low-stakes — don't toast, just log.
        // User sees empty candidate list, which is a reasonable fallback.
        logger.error("Failed to fetch candidate transactions:", err);
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

  // ── Error routing ──

  /**
   * Route an ApiError to the appropriate UI surface.
   * - Field errors → inline under the input
   * - Everything else → toast
   */
  const routeError = (err, fallbackMessage) => {
    const message = err.userMessage || err.message || fallbackMessage;

    // Field-specific? Highlight the input.
    const mappedField = err.field ? FIELD_MAP[err.field] : null;
    if (mappedField) {
      setFieldErrors({ [mappedField]: message });
      return;
    }

    // INVALID_VALUE / REQUIRED_FIELD with no recognised field still
    // relates to the form — show inline at the top rather than toast.
    if (
      err.code === ErrorCode.INVALID_VALUE ||
      err.code === ErrorCode.REQUIRED_FIELD
    ) {
      setFieldErrors({ _general: message });
      return;
    }

    // Everything else → toast
    addToast({ message, type: 'error' });
  };

  // ── Upload handlers ──

  const handleReceiptProcessed = (result) => {
    const newReceipt = {
      ...result,
      receipt_id: result.receipt_id,
      filename: result.filename,
      extracted_data: result.extracted_data || {},
      status: 'pending'
    };

    setReceipts(prev => [...prev, newReceipt]);

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
      addToast({ message: `${succeeded} receipt${succeeded === 1 ? '' : 's'} processed`, type: 'success' });
    }
  };

  // ── Form handlers ──

  const handleSelectReceipt = (receiptId) => {
    setSelectedReceiptId(receiptId);
  };

  const handleInputChange = (field, value) => {
    setEditableData(prev => ({ ...prev, [field]: value }));
    // Clear field error as user types
    if (fieldErrors[field]) {
      setFieldErrors(prev => {
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
      page_number: selectedReceipt.page_number || 1
    };
  };

  // ── Mutations ──

  const handleSave = async () => {
    if (!selectedReceipt) return;

    setFieldErrors({});
    setIsSaving(true);

    try {
      const receiptData = buildReceiptData();
      logger.debug("Saving receipt data:", receiptData);

      await confirmReceipt(receiptData);

      setReceipts(prev => prev.map(r =>
        r.receipt_id === selectedReceiptId
          ? {
              ...r,
              status: 'saved',
              extracted_data: {
                ...r.extracted_data,
                vendor: editableData.vendor,
                date: editableData.date,
                amount: editableData.amount
              }
            }
          : r
      ));

      addToast({ message: 'Receipt saved', type: 'success', duration: 2000 });

      setTimeout(selectNextReceipt, 800);

    } catch (err) {
      logger.error("Failed to save receipt:", err);
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
      logger.debug("Saving receipt before linking:", receiptData);

      const saveResult = await confirmReceipt(receiptData);

      const receiptId =
        saveResult.data?.receipt?.id ||
        saveResult.receipt?.id ||
        saveResult.id ||
        selectedReceipt.receipt_id;

      if (!receiptId) {
        throw new Error("Failed to get receipt ID from save response");
      }

      logger.debug(`Linking transaction ${transaction.id} to receipt ${receiptId}`);

      await updateTransaction(transaction.id, { receipt_id: receiptId });

      setReceipts(prev => prev.map(r =>
        r.receipt_id === selectedReceiptId
          ? {
              ...r,
              status: 'linked',
              linked_transaction_id: transaction.id,
              extracted_data: {
                ...r.extracted_data,
                vendor: editableData.vendor,
                date: editableData.date,
                amount: editableData.amount
              }
            }
          : r
      ));

      setLinkedTransactionId(transaction.id);
      addToast({
        message: 'Receipt linked to transaction',
        type: 'success',
        duration: 2500,
      });

      setTimeout(selectNextReceipt, 1000);

    } catch (err) {
      logger.error("Failed to link receipt to transaction:", err);

      // Special case: transaction was deleted between fetch and click.
      // Refresh the candidate list so the user doesn't try again on stale data.
      if (err.code === ErrorCode.NOT_FOUND && err.entity === 'Transaction') {
        addToast({
          message: 'That transaction no longer exists. Refreshing candidates…',
          type: 'info',
        });
        setCandidateRefreshKey(k => k + 1);
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
      logger.debug("Deleting receipt:", selectedReceipt.receipt_id);
      await deleteReceipt(selectedReceipt.receipt_id);

      const currentIndex = receipts.findIndex(r => r.receipt_id === selectedReceiptId);
      const remaining = receipts.filter(r => r.receipt_id !== selectedReceiptId);

      setReceipts(remaining);

      if (remaining.length > 0) {
        const nextIndex = Math.min(currentIndex, remaining.length - 1);
        setSelectedReceiptId(remaining[nextIndex].receipt_id);
      } else {
        setSelectedReceiptId(null);
      }

      addToast({ message: 'Receipt deleted', type: 'success', duration: 1500 });

    } catch (err) {
      logger.error("Failed to delete receipt:", err);

      // If the receipt is already gone, treat it as success from the user's POV
      if (err.code === ErrorCode.NOT_FOUND) {
        addToast({ message: 'Receipt was already deleted', type: 'info' });
        setReceipts(prev => prev.filter(r => r.receipt_id !== selectedReceiptId));
        setSelectedReceiptId(null);
      } else {
        addToast({
          message: err.userMessage || 'Failed to delete receipt',
          type: 'error',
        });
      }
    } finally {
      setIsSaving(false);
    }
  };

  // ── Navigation ──

  const handleRemoveFromList = (receiptId) => {
    const currentIndex = receipts.findIndex(r => r.receipt_id === receiptId);
    const remaining = receipts.filter(r => r.receipt_id !== receiptId);

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
    const currentIndex = receipts.findIndex(r => r.receipt_id === selectedReceiptId);
    const pending = receipts.filter(
      r => r.status === 'pending' && r.receipt_id !== selectedReceiptId
    );

    if (pending.length > 0) {
      const nextAfter = pending.find(r => receipts.indexOf(r) > currentIndex);
      setSelectedReceiptId(nextAfter?.receipt_id || pending[0].receipt_id);
    }
    // If none pending, stay on current — status badge shows it's done
  };

  const handleClearAll = () => {
    setReceipts([]);
    setSelectedReceiptId(null);
    setEditableData({ vendor: "", date: "", amount: "" });
    setCandidateTransactions([]);
    setFieldErrors({});
    hasAutoSelectedRef.current = false;
  };

  // ── Derived state ──

  const canSave =
    selectedReceipt &&
    selectedReceipt.status === 'pending' &&
    editableData.vendor.trim() !== '' &&
    !isSaving &&
    !isLinking;

  const canDelete =
    selectedReceipt &&
    selectedReceipt.status === 'pending' &&
    !isSaving &&
    !isLinking;

  const pendingCount = receipts.filter(r => r.status === 'pending').length;
  const processedCount = receipts.filter(r => r.status !== 'pending').length;

  // ── Render ──

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

      {/* error/saveSuccess/linkSuccess banners removed — replaced by toasts + field errors */}

      <div className="three-column-layout">
        {/* Left Column */}
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

        {/* Middle Column */}
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
                  ? "Upload receipts to get started"
                  : "Select a receipt to view"
                }
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="column column-right">
          <div className="column-section details-section">
            <h3>Receipt Details</h3>
            {selectedReceipt ? (
              <div className="receipt-form">
                {/* General form error (validation that doesn't map to a field) */}
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
                    onChange={(e) => handleInputChange("vendor", e.target.value)}
                    placeholder="Enter vendor name"
                    required
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.vendor}
                    aria-describedby={fieldErrors.vendor ? 'vendor-error' : undefined}
                  />
                  {fieldErrors.vendor && (
                    <span id="vendor-error" className="field-error">{fieldErrors.vendor}</span>
                  )}
                </div>

                <div className={`form-group ${fieldErrors.date ? 'has-error' : ''}`}>
                  <label htmlFor="date">Date:</label>
                  <input
                    id="date"
                    type="date"
                    value={editableData.date}
                    onChange={(e) => handleInputChange("date", e.target.value)}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.date}
                    aria-describedby={fieldErrors.date ? 'date-error' : undefined}
                  />
                  {fieldErrors.date && (
                    <span id="date-error" className="field-error">{fieldErrors.date}</span>
                  )}
                </div>

                <div className={`form-group ${fieldErrors.amount ? 'has-error' : ''}`}>
                  <label htmlFor="amount">Amount:</label>
                  <input
                    id="amount"
                    type="number"
                    step="0.01"
                    value={editableData.amount}
                    onChange={(e) => handleInputChange("amount", e.target.value)}
                    placeholder="Enter amount"
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                    aria-invalid={!!fieldErrors.amount}
                    aria-describedby={fieldErrors.amount ? 'amount-error' : undefined}
                  />
                  {fieldErrors.amount && (
                    <span id="amount-error" className="field-error">{fieldErrors.amount}</span>
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
                  <button
                    onClick={handleDelete}
                    className="btn-delete"
                    disabled={!canDelete}
                  >
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
              <div className="empty-state">
                Select a receipt to edit details
              </div>
            )}
          </div>

          <div className="column-section candidates-section">
            <h3>Link to Transaction</h3>
            <div className="candidates-container">
              {selectedReceipt ? (
                selectedReceipt.status !== 'pending' ? (
                  <div className="empty-state">
                    This receipt has already been processed
                  </div>
                ) : isLoadingCandidates ? (
                  <div className="loading-candidates">
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
                <div className="empty-state">
                  Select a receipt to find matching transactions
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProcessReceipts;