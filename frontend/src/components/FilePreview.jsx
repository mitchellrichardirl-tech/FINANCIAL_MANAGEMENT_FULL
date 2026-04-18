/**
 * @file FilePreview.jsx
 * Compact list of selected files with type icon, truncated name,
 * human-readable size, and a per-item remove button. Used alongside
 * upload dropzones to show the current queue before submission.
 */

/**
 * List of staged files awaiting upload.
 *
 * Purely presentational — owns no state. The parent holds the `files`
 * array and mutates it in response to `onRemove(index)`.
 *
 * @component
 * @param {Object} props
 * @param {File[]} props.files
 *        Files to display, in order. Index is used as the removal key.
 * @param {(index: number) => void} props.onRemove
 *        Called with the item's array index when its ✕ button is clicked.
 * @param {boolean} [props.disabled=false]
 *        Disables all remove buttons (e.g. while an upload is in flight).
 * @returns {JSX.Element}
 *
 * @example
 * <FilePreview
 *   files={queuedReceipts}
 *   onRemove={(i) => setQueuedReceipts((q) => q.filter((_, j) => j !== i))}
 *   disabled={isUploading}
 * />
 */
function FilePreview({ files, onRemove, disabled = false }) {
  /**
   * Format a byte count as a short human-readable string.
   * Supports Bytes / KB / MB (sufficient for receipt/statement uploads).
   *
   * @param {number} bytes
   * @returns {string} e.g. `"412.78 KB"`
   * @private
   */
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  /**
   * Pick an emoji icon based on the file's MIME type.
   *
   * @param {File} file
   * @returns {string} 🖼️ for images, 📄 for PDFs, otherwise 📎.
   * @private
   */
  const getFileIcon = (file) => {
    if (file.type.startsWith('image/')) return '🖼️';
    if (file.type === 'application/pdf') return '📄';
    return '📎';
  };

  return (
    <div className="flex flex-col gap-2 mt-2">
      {files.map((file, index) => (
        <div key={`${file.name}-${index}`} className="flex items-center gap-3 p-2 bg-[#f9f9f9] border border-border rounded">
          <span className="text-lg">{getFileIcon(file)}</span>
          <div className="flex flex-col flex-1 min-w-0">
            <span className="text-sm truncate" title={file.name}>
              {file.name.length > 30
                ? `${file.name.substring(0, 27)}...`
                : file.name
              }
            </span>
            <span className="text-xs text-text-light">{formatFileSize(file.size)}</span>
          </div>
          <button
            onClick={() => onRemove(index)}
            className="border-none bg-transparent text-text-light cursor-pointer text-base hover:text-danger disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={disabled}
            title="Remove file"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export default FilePreview;