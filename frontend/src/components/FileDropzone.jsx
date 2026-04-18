import { useState } from 'react';

function FileDropzone({
  onFileSelect,
  disabled,
  acceptedFileTypes = '.csv,.xlsx,.xls,.tsv,.txt',
  supportedFormatsText = 'CSV, Excel, TSV, TXT',
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
    if (files.length > 0) onFileSelect(files[0]);
  };
  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files.length > 0) onFileSelect(files[0]);
  };

  const dragCls = isDragging
    ? 'border-2 border-solid border-[#007bff] bg-[#f0f8ff]'
    : 'border-2 border-dashed border-[#ccc] bg-[#fafafa]';
  const disabledCls = disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer';

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`rounded-lg p-10 text-center ${dragCls} ${disabledCls}`}
    >
      <p className="text-lg mb-[10px]">
        {isDragging ? 'Drop file here...' : 'Drag and drop a file here'}
      </p>
      <p className="text-[#666] mb-5">or</p>
      <label
        className={`py-[10px] px-5 bg-[#007bff] text-white rounded inline-block ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
      >
        Choose File
        <input
          type="file"
          onChange={handleFileInput}
          disabled={disabled}
          accept={acceptedFileTypes}
          className="hidden"
        />
      </label>
      <p className="text-xs text-[#999] mt-[10px]">
        Supported formats: {supportedFormatsText}
      </p>
    </div>
  );
}

export default FileDropzone;
