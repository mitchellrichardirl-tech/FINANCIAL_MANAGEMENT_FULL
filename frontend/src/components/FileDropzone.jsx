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
      style={{
        border: isDragging ? '2px solid #007bff' : '2px dashed #ccc',
        borderRadius: '8px',
        padding: '40px',
        textAlign: 'center',
        backgroundColor: isDragging ? '#f0f8ff' : '#fafafa',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <div>
        <p style={{ fontSize: '18px', marginBottom: '10px' }}>
          {isDragging ? 'Drop file here...' : 'Drag and drop a file here'}
        </p>
        <p style={{ color: '#666', marginBottom: '20px' }}>or</p>
        <label style={{
          padding: '10px 20px',
          backgroundColor: '#007bff',
          color: 'white',
          borderRadius: '4px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'inline-block',
        }}>
          Choose File
          <input
            type="file"
            onChange={handleFileInput}
            disabled={disabled}
            accept={acceptedFileTypes}
            style={{ display: 'none' }}
          />
        </label>
        <p style={{ fontSize: '12px', color: '#999', marginTop: '10px' }}>
          Supported formats: {supportedFormatsText}
        </p>
      </div>
    </div>
  );
}

export default FileDropzone;