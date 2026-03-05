import { useState, useEffect, useRef } from "react";
import { updateTransaction } from "@/features/transactions/api";
import { confirmReceipt, deleteReceipt, getCandidateTransactions } from "./api";
import BulkUploadReceipts from "./BulkUploadReceipts";
import SelectableReceiptTable from "./SelectableReceiptTable";
import ImagePreview from "./ImagePreview";
import CandidateTransactions from "./CandidateTransactions";
import './ProcessReceipts.css';

function ProcessReceipts() {
  // All processed receipts
  const [receipts, setReceipts] = useState([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState(null);
  
  // Track if we've auto-selected the first receipt (use ref to avoid stale closure)
  const hasAutoSelectedRef = useRef(false);
  
  // Processing state
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [error, setError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [linkSuccess, setLinkSuccess] = useState(false);

  // Editable data for selected receipt
  const [editableData, setEditableData] = useState({
    vendor: "",
    date: "",
    amount: ""
  });

  // Candidate transactions
  const [candidateTransactions, setCandidateTransactions] = useState([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [linkedTransactionId, setLinkedTransactionId] = useState(null);

  // Get the currently selected receipt
  const selectedReceipt = receipts.find(r => r.receipt_id === selectedReceiptId);

  // Update editable data when selected receipt changes
  useEffect(() => {
    if (selectedReceipt) {
      const extracted = selectedReceipt.extracted_data || {};
      setEditableData({
        vendor: extracted.vendor || "",
        date: extracted.date ? extracted.date.split('T')[0] : "",
        amount: extracted.amount?.toString() || ""
      });
      setLinkedTransactionId(null);
      setSaveSuccess(false);
      setLinkSuccess(false);
      setError(null);
    } else {
      setEditableData({ vendor: "", date: "", amount: "" });
      setCandidateTransactions([]);
    }
  }, [selectedReceiptId, selectedReceipt]);

  // Fetch candidate transactions when editableData changes
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
        console.error("Failed to fetch candidate transactions:", err);
        setCandidateTransactions([]);
      } finally {
        setIsLoadingCandidates(false);
      }
    };

    const timeoutId = setTimeout(fetchCandidates, 500);
    return () => clearTimeout(timeoutId);
  }, [editableData.date, editableData.amount, editableData.vendor, selectedReceipt]);

  // Handle new receipt from bulk upload
  const handleReceiptProcessed = (result) => {
    const newReceipt = {
      ...result,
      receipt_id: result.receipt_id,
      filename: result.filename,
      extracted_data: result.extracted_data || {},
      status: 'pending'
    };
    
    setReceipts(prev => [...prev, newReceipt]);
    
    // Only auto-select the FIRST receipt using ref to avoid race conditions
    if (!hasAutoSelectedRef.current) {
      hasAutoSelectedRef.current = true;
      setSelectedReceiptId(result.receipt_id);
    }
  };

  const handleProcessingStart = () => {
    setIsUploading(true);
    // Reset auto-select tracking for new batch
    hasAutoSelectedRef.current = false;
  };

  const handleProcessingComplete = () => {
    setIsUploading(false);
  };

  const handleSelectReceipt = (receiptId) => {
    setSelectedReceiptId(receiptId);
  };

  const handleInputChange = (field, value) => {
    setEditableData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Build receipt data for saving
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

  const handleSave = async () => {
    if (!selectedReceipt) return;
    
    setError(null);
    setIsSaving(true);

    try {
      const receiptData = buildReceiptData();
      console.log("Saving receipt data:", receiptData);
      
      const saveResult = await confirmReceipt(receiptData);
      console.log("Save result:", saveResult);
      
      // Update receipt status and data in list
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
      
      setSaveSuccess(true);
      
      // Move to next receipt after delay
      setTimeout(() => {
        selectNextReceipt();
      }, 1500);
      
    } catch (err) {
      setError(err.message || "Failed to save receipt");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSelectTransaction = async (transaction) => {
    if (!selectedReceipt) return;
    
    setError(null);
    setLinkSuccess(false);
    setIsLinking(true);

    try {
      const receiptData = buildReceiptData();
      console.log("Saving receipt before linking:", receiptData);
      
      const saveResult = await confirmReceipt(receiptData);
      console.log("Receipt save result:", saveResult);

      const receiptId = saveResult.data?.receipt?.id || saveResult.receipt?.id || saveResult.id || selectedReceipt.receipt_id;
      
      if (!receiptId) {
        throw new Error("Failed to get receipt ID from save response");
      }

      console.log(`Linking transaction ${transaction.id} to receipt ${receiptId}`);
      
      const updateResult = await updateTransaction(transaction.id, {
        receipt_id: receiptId
      });
      console.log("Transaction update result:", updateResult);

      // Update receipt status and data in list
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
      setLinkSuccess(true);

      // Move to next receipt after delay
      setTimeout(() => {
        selectNextReceipt();
      }, 2000);

    } catch (err) {
      console.error("Failed to link receipt to transaction:", err);
      setError(err.message || "Failed to link receipt to transaction");
    } finally {
      setIsLinking(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedReceipt) return;
    
    setError(null);
    setIsSaving(true);

    try {
      // const receiptData = {
      //   receiptId: selectedReceipt.receipt_id
      // };

      console.log("Deleting receipt:", selectedReceipt.receipt_id);
      const deleteResult = await deleteReceipt(selectedReceipt.receipt_id);
      console.log("Deletion result:", deleteResult);

      // Remove from list and select next
      const currentIndex = receipts.findIndex(r => r.receipt_id === selectedReceiptId);
      setReceipts(prev => prev.filter(r => r.receipt_id !== selectedReceiptId));
      
      // Select next available receipt
      const remainingReceipts = receipts.filter(r => r.receipt_id !== selectedReceiptId);
      if (remainingReceipts.length > 0) {
        const nextIndex = Math.min(currentIndex, remainingReceipts.length - 1);
        setSelectedReceiptId(remainingReceipts[nextIndex].receipt_id);
      } else {
        setSelectedReceiptId(null);
      }
      
    } catch (err) {
      setError(err.message || "Failed to delete receipt");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveFromList = (receiptId) => {
    const currentIndex = receipts.findIndex(r => r.receipt_id === receiptId);
    setReceipts(prev => prev.filter(r => r.receipt_id !== receiptId));
    
    if (selectedReceiptId === receiptId) {
      const remainingReceipts = receipts.filter(r => r.receipt_id !== receiptId);
      if (remainingReceipts.length > 0) {
        const nextIndex = Math.min(currentIndex, remainingReceipts.length - 1);
        setSelectedReceiptId(remainingReceipts[nextIndex].receipt_id);
      } else {
        setSelectedReceiptId(null);
      }
    }
  };

  const selectNextReceipt = () => {
    const currentIndex = receipts.findIndex(r => r.receipt_id === selectedReceiptId);
    const pendingReceipts = receipts.filter(r => r.status === 'pending' && r.receipt_id !== selectedReceiptId);
    
    if (pendingReceipts.length > 0) {
      // Find the next pending receipt after current position
      const pendingAfterCurrent = pendingReceipts.find(r => 
        receipts.indexOf(r) > currentIndex
      );
      setSelectedReceiptId(pendingAfterCurrent?.receipt_id || pendingReceipts[0].receipt_id);
    } else {
      // No more pending, keep current selected but clear success message
      setSaveSuccess(false);
      setLinkSuccess(false);
    }
  };

  const handleClearAll = () => {
    setReceipts([]);
    setSelectedReceiptId(null);
    setEditableData({ vendor: "", date: "", amount: "" });
    setCandidateTransactions([]);
    setError(null);
    setSaveSuccess(false);
    setLinkSuccess(false);
    hasAutoSelectedRef.current = false;
  };

  const canSave = selectedReceipt && 
                  selectedReceipt.status === 'pending' && 
                  editableData.vendor.trim() !== '' && 
                  !isSaving && 
                  !isLinking;
                  
  const canDelete = selectedReceipt && 
                    selectedReceipt.status === 'pending' && 
                    !isSaving && 
                    !isLinking;

  const pendingCount = receipts.filter(r => r.status === 'pending').length;
  const processedCount = receipts.filter(r => r.status !== 'pending').length;

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

      {/* Error and Success Messages */}
      {error && (
        <div className="receipt-error">{error}</div>
      )}
      {saveSuccess && (
        <div className="receipt-success">Receipt saved successfully!</div>
      )}
      {linkSuccess && (
        <div className="receipt-success">Receipt successfully linked to transaction!</div>
      )}

      {/* Main 3-Column Layout */}
      <div className="three-column-layout">
        {/* Left Column - Upload and Receipt List */}
        <div className="column column-left">
          <div className="column-section upload-section">
            <h3>Upload Receipts</h3>
            <BulkUploadReceipts
              onReceiptProcessed={handleReceiptProcessed}
              onProcessingStart={handleProcessingStart}
              onProcessingComplete={handleProcessingComplete}
              onError={(err) => setError(err)}
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

        {/* Middle Column - Image Preview */}
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

        {/* Right Column - Details and Candidates */}
        <div className="column column-right">
          <div className="column-section details-section">
            <h3>Receipt Details</h3>
            {selectedReceipt ? (
              <div className="receipt-form">
                <div className="form-group">
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
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="date">Date:</label>
                  <input
                    id="date"
                    type="date"
                    value={editableData.date}
                    onChange={(e) => handleInputChange("date", e.target.value)}
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="amount">Amount:</label>
                  <input
                    id="amount"
                    type="number"
                    step="0.01"
                    value={editableData.amount}
                    onChange={(e) => handleInputChange("amount", e.target.value)}
                    placeholder="Enter amount"
                    disabled={isLinking || isSaving || selectedReceipt.status !== 'pending'}
                  />
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