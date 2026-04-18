function FilePreview({ files, onRemove, disabled = false }) {
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (file) => {
    if (file.type.startsWith('image/')) return '🖼️';
    if (file.type === 'application/pdf') return '📄';
    return '📎';
  };

  return (
    <div className="flex flex-col gap-1">
      {files.map((file, index) => (
        <div
          key={`${file.name}-${index}`}
          className="flex items-center gap-2 py-1 px-2 bg-white border border-[#e0e0e0] rounded"
        >
          <span>{getFileIcon(file)}</span>
          <div className="flex-1 flex flex-col min-w-0">
            <span className="text-sm truncate" title={file.name}>
              {file.name.length > 30
                ? `${file.name.substring(0, 27)}...`
                : file.name}
            </span>
            <span className="text-xs text-[#666]">{formatFileSize(file.size)}</span>
          </div>
          <button
            type="button"
            onClick={() => onRemove(index)}
            disabled={disabled}
            title="Remove file"
            className="bg-transparent border-0 text-[#bbb] cursor-pointer text-sm hover:enabled:text-[#dc3545] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export default FilePreview;
