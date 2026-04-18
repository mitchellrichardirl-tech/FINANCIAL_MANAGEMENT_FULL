/**
 * @file FileDropzone.jsx
 * Drag-and-drop target (with click-to-browse fallback) for selecting a
 * single file. Used by statement/receipt upload flows.
 */

import { useState } from 'react';

/**
 * Single-file drag-and-drop upload area.
 *
 * Renders a dashed drop target that highlights while a file is dragged
 * over it, plus a "Choose File" button backed by a hidden
 * `<input type="file">`. Either interaction calls `onFileSelect` with
 * the chosen {@link File}; if multiple files are dropped, only the
 * first is used.
 *
 * The component does **not** validate the dropped file's type —
 * `acceptedFileTypes` only constrains the native file picker. Callers
 * should validate in `onFileSelect` if needed.
 *
 * @component
 * @param {Object} props
 * @param {(file: File) => void} props.onFileSelect
 *        Invoked with the selected/dropped file.
 * @param {boolean} [props.disabled]
 *        Dims the UI and disables the file input. Note: drop events are
 *        still delivered by the browser; guard in `onFileSelect` if a
 *        hard block is required.
 * @param {string} [props.acceptedFileTypes=".csv,.xlsx,.xls,.tsv,.txt"]
 *        Value for the hidden input's `accept` attribute.
 * @param {string} [props.supportedFormatsText="CSV, Excel, TSV, TXT"]
 *        Human-readable hint rendered under the button.
 * @returns {JSX.Element}
 *
 * @example
 * <FileDropzone
 *   onFileSelect={setStatementFile}
 *   disabled={isUploading}
 * />
 */
function FileDropzone({
  onFileSelect,
  disabled,
  acceptedFileTypes = ".csv,.xlsx,.xls,.tsv,.txt",
  supportedFormatsText = "CSV, Excel, TSV, TXT"
}) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      onFileSelect(files[0]);
    }
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      onFileSelect(files[0]);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`rounded-lg p-10 text-center ${isDragging ? 'border-2 border-solid border-primary bg-[#f0f8ff]' : 'border-2 border-dashed border-[#ccc] bg-[#fafafa]'} ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
    >
      <div>
        <p className="text-[18px] mb-2.5">
          {isDragging ? 'Drop file here...' : 'Drag and drop a file here'}
        </p>
        <p className="text-text-muted mb-5">or</p>
        <label className={`py-2.5 px-5 bg-primary text-white rounded inline-block ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
          Choose File
          <input
            type="file"
            onChange={handleFileInput}
            disabled={disabled}
            accept={acceptedFileTypes}
            className="hidden"
          />
        </label>
        <p className="text-xs text-[#999] mt-2.5">
          Supported formats: {supportedFormatsText}
        </p>
      </div>
    </div>
  );
}

export default FileDropzone;