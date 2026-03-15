import { useState } from 'react';

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