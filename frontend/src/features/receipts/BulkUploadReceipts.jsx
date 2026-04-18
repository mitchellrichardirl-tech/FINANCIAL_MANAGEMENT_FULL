import { useState, useRef } from 'react';
import FilePreview from '@/components/FilePreview';
import { API_BASE_URL } from '@/lib/apiClient';
import { createLogger } from '@/lib/logger';
import { AppError } from '@/lib/errors';

const logger = createLogger('BulkUploadReceipts');

function BulkUploadReceipts({
  onReceiptProcessed,
  onProcessingStart,
  onProcessingComplete,
  onError,
  compact = false,
}) {
  const [files, setFiles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  const fileInputRef = useRef(null);
  const processedIdsRef = useRef(new Set());
  const failedRef = useRef([]);

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files);
    setFiles((prev) => [...prev, ...selected]);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter(
      (file) => file.type.startsWith('image/') || file.type === 'application/pdf'
    );
    setFiles((prev) => [...prev, ...dropped]);
  };
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };
  const handleDragLeave = () => setIsDragOver(false);

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const clearFiles = () => {
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const processReceipts = async () => {
    if (files.length === 0) return;
    const totalFiles = files.length;
    failedRef.current = [];
    setIsProcessing(true);
    setProgress({ current: 0, total: totalFiles });
    processedIdsRef.current = new Set();
    onProcessingStart?.();

    const formData = new FormData();
    files.forEach((file) => {
      logger.debug(`Adding file ${file.name} to payload`);
      formData.append('files', file);
    });

    try {
      const response = await fetch(`${API_BASE_URL}/receipts/upload-stream`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new AppError({
          message: `Upload failed: ${response.status} ${response.statusText}`,
          userMessage: errorBody?.user_message,
          status: response.status,
        });
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
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            try {
              const result = JSON.parse(trimmed.slice(6));
              logger.debug('Receipt result:', result);
              if (result.receipt_id && !processedIdsRef.current.has(result.receipt_id)) {
                processedIdsRef.current.add(result.receipt_id);
                if (result.status === 'success') onReceiptProcessed?.(result);
                else { failedRef.current.push(result); logger.warn(`Receipt ${result.receipt_id} failed:`, result); }
                setProgress((prev) => ({
                  ...prev,
                  current: Math.min(processedIdsRef.current.size, totalFiles),
                }));
              }
            } catch (parseError) {
              logger.error('Failed to parse SSE data:', parseError, trimmed);
            }
          }
        }
      }

      if (buffer.trim().startsWith('data: ')) {
        try {
          const result = JSON.parse(buffer.trim().slice(6));
          if (result.receipt_id && !processedIdsRef.current.has(result.receipt_id)) {
            processedIdsRef.current.add(result.receipt_id);
            if (result.status === 'success') onReceiptProcessed?.(result);
          }
        } catch (e) { logger.error('Failed to parse final SSE data:', e); }
      }

      onProcessingComplete?.({
        succeeded: processedIdsRef.current.size - failedRef.current.length,
        failed: failedRef.current.length,
        failures: failedRef.current,
      });
      clearFiles();
    } catch (error) {
      logger.error('Bulk upload error:', error);
      onError?.(error);
    } finally {
      setIsProcessing(false);
      setProgress({ current: 0, total: 0 });
      processedIdsRef.current = new Set();
    }
  };

  let dropzoneCls =
    'rounded-lg text-center transition-all duration-200 ease-in-out bg-[#fafafa] border-2 border-dashed border-[#ccc]';
  if (compact) dropzoneCls += ' p-4'; else dropzoneCls += ' p-6';
  if (isDragOver && !isProcessing)
    dropzoneCls += ' border-solid border-[#007bff] bg-[#e7f1ff]';
  else if (!isProcessing)
    dropzoneCls += ' hover:border-[#007bff] hover:bg-[#f0f7ff]';
  if (isProcessing) dropzoneCls += ' opacity-60 cursor-not-allowed';

  return (
    <div className="flex flex-col gap-4">
      <div
        className={dropzoneCls}
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
          className="hidden"
        />
        <label
          htmlFor="bulk-file-input"
          className={`block ${isProcessing ? 'cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <div className="flex flex-col items-center gap-2">
            <span className={compact ? 'text-2xl' : 'text-[2rem]'}>📁</span>
            <span className={compact ? 'text-sm text-[#333]' : 'text-[0.9rem] text-[#333]'}>
              {compact ? 'Drop files or click to select' : 'Drop files here or click to select'}
            </span>
            {!compact && <span className="text-xs text-[#666]">Supports JPG, PNG, PDF</span>}
          </div>
        </label>
      </div>

      {files.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center">
            <span className="text-xs text-[#666]">
              {files.length} file{files.length !== 1 ? 's' : ''}
            </span>
            <button
              type="button"
              onClick={clearFiles}
              disabled={isProcessing}
              className="py-0.5 px-2 text-xs bg-transparent border border-[#999] text-[#666] rounded cursor-pointer hover:enabled:border-[#dc3545] hover:enabled:text-[#dc3545] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear
            </button>
          </div>

          {!compact && <FilePreview files={files} onRemove={removeFile} disabled={isProcessing} />}

          <button
            type="button"
            onClick={processReceipts}
            disabled={isProcessing || files.length === 0}
            className="py-2 px-4 bg-[#007bff] text-white border-0 rounded cursor-pointer font-medium text-sm hover:enabled:bg-[#0056b3] disabled:bg-[#ccc] disabled:cursor-not-allowed"
          >
            {isProcessing
              ? `Processing ${progress.current}/${progress.total}...`
              : `Process ${files.length} Receipt${files.length !== 1 ? 's' : ''}`}
          </button>
        </div>
      )}

      {isProcessing && (
        <div className="mt-2">
          <div className="w-full h-1 bg-[#e0e0e0] rounded-sm overflow-hidden">
            <div
              className="h-full bg-[#007bff] transition-[width] duration-300 ease-in-out"
              style={{
                width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default BulkUploadReceipts;
