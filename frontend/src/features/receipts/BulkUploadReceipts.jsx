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
import './BulkUploadReceipts.css';
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
 *        Fired once per receipt that the server successfully parsed.
 *        `result` contains `receipt_id`, `filename`, `extracted_data`,
 *        etc., and is consumed verbatim by {@link ProcessReceipts}.
 * @param {() => void} [props.onProcessingStart]
 *        Fired when the user clicks "Process" and the request begins.
 * @param {(summary: {succeeded: number, failed: number, failures: Object[]}) => void} [props.onProcessingComplete]
 *        Fired after the stream closes. `failures` holds the raw stream
 *        events for receipts that reported a non-success status.
 * @param {(message: string) => void} [props.onError]
 *        Fired for transport-level failures (network error, non-2xx
 *        before the stream starts). Per-receipt failures are reported
 *        via `onProcessingComplete`, not here.
 * @param {boolean} [props.compact=false]
 *        Render in compact mode (hides {@link FilePreview} list and
 *        shortens copy) for use in the sidebar.
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
    event.currentTarget.classList.remove('drag-over');
    const droppedFiles = Array.from(event.dataTransfer.files).filter(
      (file) => file.type.startsWith('image/') || file.type === 'application/pdf'
    );
    setFiles((prev) => [...prev, ...droppedFiles]);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (event) => {
    event.currentTarget.classList.remove('drag-over');
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
  /**
   * Handle one parsed stream event. Terminal events (success/error) drive
   * progress, keyed by task `index` -- present on every event, unlike
   * `receipt_id`, which failures lack.
   */
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

  /**
   * POST all queued files to `/receipts/upload-stream` and parse the
   * streamed response line-by-line.
   *
   * The server sends SSE-style lines: `data: {json}\n`. Each JSON
   * object has at least `{ receipt_id, status }`. We:
   *  - De-duplicate by `receipt_id` via `completedIndicesRef`.
   *  - Call `onReceiptProcessed` for successes.
   *  - Collect failures into `failedRef` for the summary callback.
   *  - Update the progress bar as unique ids arrive.
   *
   * Uses raw `fetch` (not `apiClient`) because `apiClient` calls
   * `response.json()`, which would block until the stream ends.
   */
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
            {!compact && <span className="dropzone-hint">Supports JPG, PNG, PDF</span>}
          </div>
        </label>
      </div>

      {files.length > 0 && (
        <div className="selected-files-section">
          <div className="selected-files-header">
            <span className="file-count">
              {files.length} file{files.length !== 1 ? 's' : ''}
            </span>
            <button onClick={clearFiles} className="btn-clear-files" disabled={isProcessing}>
              Clear
            </button>
          </div>

          {!compact && <FilePreview files={files} onRemove={removeFile} disabled={isProcessing} />}

          <div className="process-controls">
            <Checkbox
              checked={useMultimodal}
              onChange={setUseMultimodal}
              disabled={isProcessing}
              label="AI extraction"
            />
            <button
              onClick={processReceipts}
              disabled={isProcessing || files.length === 0}
              className="btn-process"
            >
              {isProcessing
                ? `Processing ${progress.current}/${progress.total}...`
                : `Process ${files.length} Receipt${files.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      )}

      {isProcessing && (
        <div className="processing-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
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