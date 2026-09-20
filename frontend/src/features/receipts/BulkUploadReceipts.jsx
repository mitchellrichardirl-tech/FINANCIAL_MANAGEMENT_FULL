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

import { useEffect, useState, useRef } from 'react';

import FilePreview from '@/components/FilePreview';
import Checkbox from '@/components/Checkbox';
import { API_BASE_URL } from '@/lib/apiClient';
import { createLogger } from '@/lib/logger';
import { AppError } from '@/lib/errors';
import { getErrorMessage } from '@/lib/apiErrors';

import { readEventStream } from '@/lib/sse';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('BulkUploadReceipts');

/**
 * @typedef {Object} ProcessingSummary
 * @property {'completed'|'fatal'|'disconnected'|'aborted'|'rejected'} outcome
 * @property {number} succeeded
 * @property {number} failed      Files the backend reported as failed.
 * @property {number} cancelled   Files with no result (cancelled, aborted, or dropped).
 * @property {Object[]} failures
 * @property {Object[]} cancellations
 * @property {string|null} error  Stream-level error message, if any.
 */

/**
 * Bulk receipt uploader with streaming progress.
 *
 * @component
 * @param {Object} props
 * @param {(result: Object) => void} [props.onReceiptProcessed]
 * @param {() => void} [props.onProcessingStart]
 * @param {(summary: ProcessingSummary) => void} [props.onProcessingComplete]
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
  const streamOutcomeRef = useRef(null);
  const cancelledRef = useRef([]);
  const abortControllerRef = useRef(null);
  /**
   * Treat the stream as dead after this long with no data. Must be well above
   * the backend's RECEIPT_STREAM_HEARTBEAT (10s). Change both together.
   */
  const STREAM_IDLE_TIMEOUT_MS = 30_000;
  const handleStreamEvent = (event, totalFiles) => {
    switch (event.status) {
      case 'success':
      case 'error':
        // Stream-level failure. The backend sets `fatal`. The missing
        // file_index check also catches older fatal events.
        if (event.status === 'error' && (event.fatal || event.file_index == null)) {
          handleFatalEvent(event);
        } else {
          handleFileResult(event, totalFiles);
        }
        return;
      case 'completed':
        streamOutcomeRef.current = {
          type: 'completed',
          summary: {
            processed: event.total_processed,
            successes: event.successes,
            errors: event.errors,
          },
        };
        return;
      default:
        // 'starting', 'processing', 'heartbeat', or anything added later.
        return;
    }
  };
  const handleFileResult = (event, totalFiles) => {
    if (event.file_index == null) return;
    if (completedIndicesRef.current.has(event.file_index)) return;
    completedIndicesRef.current.add(event.file_index);
    if (event.status === 'success') {
      onReceiptProcessed?.(event);
    } else if (event.cancelled) {
      cancelledRef.current.push(event);
      logger.info(`Receipt ${event.filename ?? event.file_index} was cancelled:`, event);
    } else {
      failedRef.current.push(event);
      logger.warn(`Receipt ${event.filename ?? event.file_index} failed to process:`, event);
    }

    setProgress((prev) => ({
      ...prev,
      current: Math.min(completedIndicesRef.current.size, totalFiles),
    }));
  };
  const handleFatalEvent = (event) => {
    // Keep the first fatal event, since it's the real cause.
    if (streamOutcomeRef.current?.type === 'fatal') return;
    streamOutcomeRef.current = {
      type: 'fatal',
      error: event.error ?? 'Processing failed',
      details: event.details,
      summary: {
        processed: event.total_processed,
        successes: event.successes,
        errors: event.errors,
        cancelled: event.cancelled,
      },
    };
    logger.error('Receipt processing aborted:', event);
  };
  // Abort any in-flight upload when the component unmounts.
  useEffect(() => () => abortControllerRef.current?.abort(), []);
  const cancelProcessing = () => {
    abortControllerRef.current?.abort();
  };
  /** Mark every file the backend never reported as cancelled. */
  const markUnreportedAsCancelled = (batch, reason) => {
    let count = 0;
    batch.forEach((file, index) => {
      if (completedIndicesRef.current.has(index)) return;
      completedIndicesRef.current.add(index);
      cancelledRef.current.push({
        status: 'error',
        cancelled: true,
        file_index: index,
        filename: file.name,
        error: reason,
      });
      count += 1;
    });
    return count;
  };
  /** Decide the final outcome and notify the parent. */
  const finishProcessing = (batch, aborted) => {
    const outcome = streamOutcomeRef.current;
    let outcomeType;
    let errorMessage = null;
    let unreportedReason;
    if (aborted) {
      outcomeType = 'aborted';
      unreportedReason = 'Cancelled by user';
    } else if (outcome?.type === 'fatal') {
      outcomeType = 'fatal';
      errorMessage = outcome.error;
      unreportedReason = `Not processed: ${outcome.error}`;
    } else if (outcome?.type === 'completed') {
      outcomeType = 'completed';
      unreportedReason = 'No result received from server';
    } else {
      // The stream ended with no 'completed' and no fatal event.
      outcomeType = 'disconnected';
      errorMessage =
        'Lost connection to the server';
      unreportedReason = 'Connection lost before a result was received';
    }
    const unreported = markUnreportedAsCancelled(batch, unreportedReason);
    if (unreported > 0 && outcomeType === 'completed') {
      logger.warn(`Stream completed but ${unreported} file(s) were never reported`);
    }
    const failed = failedRef.current.length;
    const cancelled = cancelledRef.current.length;
    const succeeded = completedIndicesRef.current.size - failed - cancelled;
    logger.info(
      `Receipt processing ${outcomeType}: ` +
      `succeeded=${succeeded} failed=${failed} cancelled=${cancelled}`
    );
    onProcessingComplete?.({
      outcome: outcomeType, // 'completed' | 'fatal' | 'disconnected' | 'aborted'
      succeeded,
      failed,
      cancelled,
      failures: failedRef.current,
      cancellations: cancelledRef.current,
      error: errorMessage,
    });
    // Some receipts may already be saved, so clear the selection to
    // prevent duplicate uploads. The failures and cancellations lists
    // tell the user which files to check.
    clearFiles();
  };
  const processReceipts = async () => {
    if (files.length === 0) return;
    if ( abortControllerRef.current ) {
      // Check the ref, not state, for the reason given earlier.
      logger.warn('Processing already in progress; ignoring click');
      return;
    };
    const batch = [...files]; // snapshot; indices match the backend's file_index
    const totalFiles = batch.length;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    failedRef.current = [];
    cancelledRef.current = [];
    completedIndicesRef.current = new Set();
    streamOutcomeRef.current = null;
    setIsProcessing(true);
    setProgress({ current: 0, total: totalFiles });
    onProcessingStart?.();
    const extractionMethod = useMultimodal ? 'multimodal' : 'ocr';
    const formData = new FormData();
    batch.forEach((file) => {
      logger.debug(`Adding file ${file.name} to payload`);
      formData.append('files', file);
    });
    formData.append('extraction_method', extractionMethod);
    logger.debug(`Extraction method: ${extractionMethod}`);
    try {
      // Phase 1: the request. If this fails, nothing was processed.
      let response;
      try {
        response = await fetch(`${API_BASE_URL}/receipts/upload-stream`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
        if (!response.ok) throw response;
      } catch (error) {
        const aborted = controller.signal.aborted;
        let message = null;
        if (aborted) {
          logger.info('Receipt upload cancelled before processing started');
        } else {
          logger.error('Receipt upload request failed:', error);
          message = await getErrorMessage(error, 'Receipt upload');
          onError?.(message);
        }
        // Always pair onProcessingStart with onProcessingComplete, so the
        // parent can reset its state.
        onProcessingComplete?.({
          outcome: aborted ? 'aborted' : 'rejected',
          succeeded: 0,
          failed: 0,
          cancelled: 0,
          failures: [],
          cancellations: [],
          error: message,
        });
        return; // keep the files so the user can retry
      }
      // Phase 2: the stream. Failures here mean partial results.
      try {
        await readEventStream(
          response,
          (event) => {
            logger.debug('Stream event:', event);
            handleStreamEvent(event, totalFiles);
          },
          { idleTimeoutMs: STREAM_IDLE_TIMEOUT_MS },
        );
      } catch (error) {
        if (!controller.signal.aborted) {
          logger.error('Receipt stream interrupted:', error);
        }
        // finishProcessing handles this. The outcome is still null.
      }
      finishProcessing(batch, controller.signal.aborted);
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
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
              type="button"
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
            {isProcessing ? (
              <button
                type="button"
                onClick={cancelProcessing}
                className="flex-1 cursor-pointer rounded border border-[#dc3545] bg-white px-4 py-2 text-sm font-medium text-[#dc3545] hover:bg-[#dc3545] hover:text-white"
              >
                Cancel ({progress.current}/{progress.total})
              </button>
            ) : (
              <button
                type="button"
                onClick={processReceipts}
                disabled={files.length === 0}
                className="flex-1 cursor-pointer rounded bg-[#007bff] px-4 py-2 text-sm font-medium text-white hover:bg-[#0056b3] disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                Process {files.length} receipt{files.length === 1 ? '' : 's'}
              </button>
            )}
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