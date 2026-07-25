/**
 * @file BulkUploadReceipts.jsx
 * Multi-file receipt uploader with drag-and-drop and streaming progress.
 *
 * Unlike the generic {@link module:components/FileDropzone}, this
 * component:
 *  - Accepts **multiple** files (images + PDFs) in one batch.
 *  - Talks to `/receipts/upload-stream` directly via `fetch` (bypassing
 *    `apiClient`) so it can read the response as an SSE-style stream
 *    and emit per-receipt events as the backend finishes each file.
 *  - Shows a live progress bar driven by unique `receipt_id`s seen in
 *    the stream.
 *
 * The parent ({@link ProcessReceipts}) is notified via callbacks:
 *  - `onProcessingStart()` — batch has begun.
 *  - `onReceiptProcessed(result)` — one receipt succeeded.
 *  - `onProcessingComplete({succeeded, failed, failures})` — batch done.
 *  - `onError(message)` — transport-level failure (non-2xx, network).
 * 
 * Sends an `extraction_method` form field (`'ocr'` | `'multimodal'`)
 *  - controlled by the "AI extraction" checkbox, selecting the backend
 *  - extraction engine per batch.
 */

import { useState, useRef } from 'react';
import FilePreview from '@/components/FilePreview';
import Checkbox from '@/components/Checkbox';
import { API_BASE_URL } from '@/lib/apiClient';
import { createLogger } from '@/lib/logger';
import { AppError } from '@/lib/errors';
import { getErrorMessage } from '@/lib/apiErrors';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('BulkUploadReceipts');
/**
 * Bulk receipt uploader with streaming progress.
 *
 * @component
 * @param {Object} props
 * @param {(result: Object) => void} [props.onReceiptProcessed]
 * @param {() => void} [props.onProcessingStart]
 * @param {(summary: {succeeded: number, failed: number, failures: Object[]}) => void} [props.onProcessingComplete]
 * @param {(message: string) => void} [props.onError]
 * @param {boolean} [props.compact=false]
 * @returns {JSX.Element}
 */
function BulkUploadReceipts({
  onReceiptProcessed,
  onProcessingStart,
  onProcessingComplete,
  onError,
  compact = false,
}) {
  /** Files queued for upload but not yet submitted. */
  const [files, setFiles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  /** Progress for the bar: `{ current, total }`. */
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  /**
   * Drag-hover state. Previously handled via
   * `currentTarget.classList.add('drag-over')`; lifted into state so the
   * styling can live in Tailwind utilities.
   */
  const [isDragOver, setIsDragOver] = useState(false);
  /** Ref to the hidden `<input type="file">` so we can reset its value. */
  const fileInputRef = useRef(null);
  /** Collects stream events whose `status !== 'success'`. */
  const failedRef = useRef([]);
  /** When true, the backend uses the multimodal (LLM) extractor instead of OCR. */
  const [useMultimodal, setUseMultimodal] = useState(false);
  // ── File selection ────────────────────────────────────────────────
  /** Append files chosen via the native picker. */
  const handleFileSelect = (event) => {
    const selectedFiles = Array.from(event.target.files);
    setFiles((prev) => [...prev, ...selectedFiles]);
  };
  /**
   * Handle drag-and-drop. Only image/* and PDF types are accepted;
   * others are silently ignored.
   */
  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragOver(false);
    const droppedFiles = Array.from(event.dataTransfer.files).filter(
      (file) => file.type.startsWith('image/') || file.type === 'application/pdf'
    );
    setFiles((prev) => [...prev, ...droppedFiles]);
  };
  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragOver(true);
  };
  const handleDragLeave = () => {
    setIsDragOver(false);
  };
  /** Remove a single queued file by index. */
  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };
  /** Clear the queue and reset the native input so the same file can be re-picked. */
  const clearFiles = () => {
    setFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };
  // ── Upload + stream parse ─────────────────────────────────────────
  /** Indices of tasks that have reached a terminal state (success or failure). */
  const completedIndicesRef = useRef(new Set());
  const handleStreamEvent = (result, totalFiles) => {
    const isTerminal = result.status === 'success' || result.status === 'error';
    if (!isTerminal || result.file_index == null) return;
    if (completedIndicesRef.current.has(result.file_index)) return;
    completedIndicesRef.current.add(result.file_index);
    if (result.status === 'success') {
      onReceiptProcessed?.(result);
    } else {
      failedRef.current.push(result);
      logger.warn(`Receipt ${result.identifier ?? result.file_index} failed to process:`, result);
    }
    setProgress((prev) => ({
      ...prev,
      current: Math.min(completedIndicesRef.current.size, totalFiles),
    }));
  };
  const processReceipts = async () => {
    if (files.length === 0) return;
    const totalFiles = files.length;
    failedRef.current = [];
    setIsProcessing(true);
    setProgress({ current: 0, total: totalFiles });
    completedIndicesRef.current = new Set();
    onProcessingStart?.();
    const formData = new FormData();
    files.forEach((file) => {
      logger.debug(`Adding file ${file.name} to payload`);
      formData.append('files', file);
    });
    formData.append('extraction_method', useMultimodal ? 'multimodal' : 'ocr');
    logger.debug(`Extraction method: ${useMultimodal ? 'multimodal' : 'ocr'}`);
    try {
      const response = await fetch(
        `${API_BASE_URL}/receipts/upload-stream`,
        { method: 'POST', body: formData }
      );
      if (!response.ok) {
        throw response;
        // const errorBody = await response.json().catch(() => null);
        // throw new AppError({
        //   message: `Upload failed: ${response.status} ${response.statusText}`,
        //   userMessage: errorBody?.user_message, // falls back to STATUS_MESSAGES via AppError
        //   status: response.status,
        // });
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      // Stream loop: accumulate chunks, split on newline, parse each `data:` line.
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // keep the trailing partial line
        for (const line of lines) {
          const trimmedLine = line.trim();
          if (trimmedLine.startsWith('data: ')) {
            try {
              const jsonStr = trimmedLine.slice(6);
              const result = JSON.parse(jsonStr);
              logger.debug('Receipt result:', result);
              handleStreamEvent(result, totalFiles)
            } catch (parseError) {
              logger.error('Failed to parse SSE data:', parseError, trimmedLine);
            }
          }
        }
      }
      // Flush any trailing `data:` line left in the buffer
      if (buffer.trim().startsWith('data: ')) {
        try {
          const jsonStr = buffer.trim().slice(6);
          const result = JSON.parse(jsonStr);
          logger.debug('Receipt result:', result);
          handleStreamEvent(result, totalFiles);
        } catch (parseError) {
          logger.error('Failed to parse final SSE data:', parseError);
        }
      }
      onProcessingComplete?.({
        succeeded: completedIndicesRef.current.size - failedRef.current.length,
        failed: failedRef.current.length,
        failures: failedRef.current,
      });
      clearFiles();
    } catch (error) {
      logger.error('Bulk upload error:', error);
      const message = await getErrorMessage(error, 'Receipt upload')
      onError?.(message);
    } finally {
      setIsProcessing(false);
      setProgress({ current: 0, total: 0 });
      completedIndicesRef.current = new Set();
    }
  };
  // ── Derived class strings ─────────────────────────────────────────
  const dropzoneCls = [
    'rounded-lg border-2 text-center transition-all duration-200',
    compact ? 'p-4' : 'p-6',
    isDragOver
      ? 'border-solid border-[#007bff] bg-[#e7f1ff]'
      : 'border-dashed border-gray-300 bg-gray-50',
    // hover is suppressed while dragging so drag-over styling wins
    !isProcessing && !isDragOver && 'hover:border-[#007bff] hover:bg-[#f0f7ff]',
    isProcessing && 'cursor-not-allowed opacity-60',
  ]
    .filter(Boolean)
    .join(' ');
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
          className="sr-only"
        />
        <label
          htmlFor="bulk-file-input"
          className={`block ${isProcessing ? 'cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <div className="flex flex-col items-center gap-2">
            <span className={compact ? 'text-[1.5rem]' : 'text-[2rem]'}>📁</span>
            <span className="text-sm text-gray-800">
              {compact ? 'Drop files or click to select' : 'Drop files here or click to select'}
            </span>
            {!compact && <span className="text-xs text-muted">Supports JPG, PNG, PDF</span>}
          </div>
        </label>
      </div>
      {files.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[0.8rem] text-muted">
              {files.length} file{files.length !== 1 ? 's' : ''}
            </span>
            <button
              onClick={clearFiles}
              className="cursor-pointer rounded-[3px] border border-gray-400 bg-transparent px-2 py-0.5 text-xs text-muted hover:border-[#dc3545] hover:text-[#dc3545] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isProcessing}
            >
              Clear
            </button>
          </div>
          {!compact && <FilePreview files={files} onRemove={removeFile} disabled={isProcessing} />}
          <div className="flex items-center gap-3">
            <Checkbox
              checked={useMultimodal}
              onChange={setUseMultimodal}
              disabled={isProcessing}
              label="AI extraction"
            />
            <button
              onClick={processReceipts}
              disabled={isProcessing || files.length === 0}
              className="flex-1 cursor-pointer rounded bg-[#007bff] px-4 py-2 text-sm font-medium text-white hover:bg-[#0056b3] disabled:cursor-not-allowed disabled:bg-gray-300"
            >
              {isProcessing
                ? `Processing ${progress.current}/${progress.total}...`
                : `Process ${files.length} Receipt${files.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      )}
      {isProcessing && (
        <div className="mt-2">
          <div className="h-1 w-full overflow-hidden rounded-[2px] bg-[#e0e0e0]">
            <div
              className="h-full bg-[#007bff] transition-[width] duration-300 ease-out"
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