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
    <div className="file-preview-list">
      {files.map((file, index) => (
        <div key={`${file.name}-${index}`} className="file-preview-item">
          <span className="file-icon">{getFileIcon(file)}</span>
          <div className="file-info">
            <span className="file-name" title={file.name}>
              {file.name.length > 30 
                ? `${file.name.substring(0, 27)}...` 
                : file.name
              }
            </span>
            <span className="file-size">{formatFileSize(file.size)}</span>
          </div>
          <button
            onClick={() => onRemove(index)}
            className="btn-remove-file"
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