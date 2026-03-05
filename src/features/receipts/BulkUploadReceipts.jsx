import { useState, useRef } from "react";
import FilePreview from "@/components/FilePreview";
import './BulkUploadReceipts.css';

function BulkUploadReceipts({
  onReceiptProcessed,
  onProcessingStart,
  onProcessingComplete,
  onError,
  compact = false
}) {
  const [files, setFiles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const fileInputRef = useRef(null);
  // Track processed receipt IDs to avoid double-counting
  const processedIdsRef = useRef(new Set());

  const handleFileSelect = (event) => {
    const selectedFiles = Array.from(event.target.files);
    setFiles(prev => [...prev, ...selectedFiles]);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.currentTarget.classList.remove('drag-over');
    const droppedFiles = Array.from(event.dataTransfer.files).filter(
      file => file.type.startsWith('image/') || file.type === 'application/pdf'
    );
    setFiles(prev => [...prev, ...droppedFiles]);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (event) => {
    event.currentTarget.classList.remove('drag-over');
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const clearFiles = () => {
    setFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const processReceipts = async () => {
    if (files.length === 0) return;

    const totalFiles = files.length;
    setIsProcessing(true);
    setProgress({ current: 0, total: totalFiles });
    processedIdsRef.current = new Set(); // Reset tracking
    onProcessingStart?.();

    const formData = new FormData();
    files.forEach((file) => {
      console.log(`Adding file ${file.name} to payload`);
      formData.append('files', file);
    });

    try {
      const response = await fetch('/api/receipts/upload-stream', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (trimmedLine.startsWith('data: ')) {
            try {
              const jsonStr = trimmedLine.slice(6);
              const result = JSON.parse(jsonStr);
              console.log('Receipt result:', result);
              
              // Only process each receipt_id once
              if (result.receipt_id && !processedIdsRef.current.has(result.receipt_id)) {
                processedIdsRef.current.add(result.receipt_id);
                
                if (result.status === 'success') {
                  onReceiptProcessed?.(result);
                }
                
                // Update progress based on unique receipts processed
                setProgress(prev => ({ 
                  ...prev, 
                  current: Math.min(processedIdsRef.current.size, totalFiles)
                }));
              }
            } catch (parseError) {
              console.error('Failed to parse SSE data:', parseError, trimmedLine);
            }
          }
        }
      }

      // Process any remaining data in buffer
      if (buffer.trim().startsWith('data: ')) {
        try {
          const jsonStr = buffer.trim().slice(6);
          const result = JSON.parse(jsonStr);
          if (result.receipt_id && !processedIdsRef.current.has(result.receipt_id)) {
            processedIdsRef.current.add(result.receipt_id);
            if (result.status === 'success') {
              onReceiptProcessed?.(result);
            }
          }
        } catch (parseError) {
          console.error('Failed to parse final SSE data:', parseError);
        }
      }

      onProcessingComplete?.();
      clearFiles();
    } catch (error) {
      console.error('Bulk upload error:', error);
      onError?.(error.message || 'Failed to process receipts');
    } finally {
      setIsProcessing(false);
      setProgress({ current: 0, total: 0 });
      processedIdsRef.current = new Set();
    }
  };

  return (
    <div className={`bulk-upload-receipts ${compact ? 'compact' : ''}`}>
      <div 
        className={`dropzone ${isProcessing ? 'disabled' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf"
          onChange={handleFileSelect}
          disabled={isProcessing}
          id="bulk-file-input"
          className="file-input-hidden"
        />
        <label htmlFor="bulk-file-input" className="dropzone-label">
          <div className="dropzone-content">
            <span className="dropzone-icon">{compact ? '📁' : '📁'}</span>
            <span className="dropzone-text">
              {compact ? 'Drop files or click to select' : 'Drop files here or click to select'}
            </span>
            {!compact && (
              <span className="dropzone-hint">
                Supports JPG, PNG, PDF
              </span>
            )}
          </div>
        </label>
      </div>

      {files.length > 0 && (
        <div className="selected-files-section">
          <div className="selected-files-header">
            <span className="file-count">{files.length} file{files.length !== 1 ? 's' : ''}</span>
            <button 
              onClick={clearFiles} 
              className="btn-clear-files"
              disabled={isProcessing}
            >
              Clear
            </button>
          </div>
          
          {!compact && (
            <FilePreview files={files} onRemove={removeFile} disabled={isProcessing} />
          )}
          
          <button
            onClick={processReceipts}
            disabled={isProcessing || files.length === 0}
            className="btn-process"
          >
            {isProcessing 
              ? `Processing ${progress.current}/${progress.total}...`
              : `Process ${files.length} Receipt${files.length !== 1 ? 's' : ''}`
            }
          </button>
        </div>
      )}

      {isProcessing && (
        <div className="processing-progress">
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default BulkUploadReceipts;