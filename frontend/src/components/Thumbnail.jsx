import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { parseApiError, getUserMessage, isNotFound } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

const logger = createLogger('ReceiptThumbnail');

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

function ReceiptThumbnail({
  src,
  alt = 'File thumbnail',
  maxWidth = '50px',
  maxHeight = '100px',
}) {
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fileType, setFileType] = useState(null);
  const [pdfReady, setPdfReady] = useState(false);

  useEffect(() => {
    if (!src) {
      setPreviewUrl(null);
      setIsLoading(false);
      setPdfReady(false);
      return;
    }

    setError(null);
    setIsLoading(true);
    setPdfReady(false);

    fetch(src, { method: 'HEAD' })
      .then(async (response) => {
        if (!response.ok) {
          const parsed = await parseApiError(response);
          if (isNotFound(parsed)) throw new Error('Image no longer available');
          throw new Error(getUserMessage(parsed, 'Loading thumbnail'));
        }
        const contentType = response.headers.get('Content-Type');
        if (!contentType) throw new Error('Unknown file type');
        const isImage = contentType.startsWith('image/');
        const isPDF = contentType.includes('application/pdf');
        if (!isImage && !isPDF) throw new Error('Unsupported file type');
        setFileType(isImage ? 'image' : 'pdf');
        setPreviewUrl(src);
        if (isImage) setIsLoading(true);
      })
      .catch((err) => {
        logger.warn('Thumbnail load failed:', err.message);
        setError(err.message);
        setIsLoading(false);
      });
  }, [src]);

  const onDocumentLoadSuccess = () => {
    setPdfReady(true);
    setIsLoading(false);
  };
  const onDocumentLoadError = (err) => {
    logger.error('Error loading PDF:', err);
    setPdfReady(false);
    setError('Failed to load PDF');
    setIsLoading(false);
  };
  const handleImageLoad = () => setIsLoading(false);
  const handleImageError = (err) => {
    logger.error('Error loading image:', err);
    setError('Failed to load image');
    setIsLoading(false);
  };

  if (error) return <div className="text-xs text-[#dc3545]">{error}</div>;
  if (!previewUrl && !isLoading) return null;

  return (
    <div className="rounded overflow-hidden bg-[#f5f5f5]" style={{ maxWidth }}>
      {isLoading && <div className="text-xs text-[#666] p-1">Loading...</div>}
      {fileType === 'image' && previewUrl && (
        <img
          src={previewUrl}
          alt={alt}
          onLoad={handleImageLoad}
          onError={handleImageError}
          className={isLoading ? 'hidden' : 'block'}
          style={{ maxHeight }}
        />
      )}
      {fileType === 'pdf' && previewUrl && (
        <div className={isLoading ? 'hidden' : ''}>
          <Document
            key={previewUrl}
            file={previewUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading=""
          >
            {pdfReady && (
              <Page
                pageNumber={1}
                height={parseInt(maxHeight)}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onLoadError={(err) => {
                  logger.warn('PDF page load error:', err.message);
                }}
              />
            )}
          </Document>
        </div>
      )}
    </div>
  );
}

export default ReceiptThumbnail;
