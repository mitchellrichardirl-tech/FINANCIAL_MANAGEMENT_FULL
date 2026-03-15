import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { parseApiError, getUserMessage, isNotFound } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

const logger = createLogger('ReceiptThumbnail');
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

function ReceiptThumbnail({
  src,
  alt = "File thumbnail",
  maxWidth = "50px",
  maxHeight = "100px"
}) {
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fileType, setFileType] = useState(null);
  
  useEffect(() => {
    if (!src) {
      setPreviewUrl(null);
      setIsLoading(false);
      return;
    }

    setError(null);
    setIsLoading(true);

    fetch(src, { method: 'HEAD' })
      .then(async (response) => {
        if (!response.ok) {
          // Try to parse structured error from API
          const parsed = await parseApiError(response);
          
          if (isNotFound(parsed)) {
            throw new Error('Image no longer available');
          }
          
          throw new Error(getUserMessage(parsed, 'Loading thumbnail'));
        }

        const contentType = response.headers.get('Content-Type');

        if (!contentType) {
          throw new Error('Unknown file type');
        }

        const isImage = contentType.startsWith('image/');
        const isPDF = contentType.includes('application/pdf');

        if (!isImage && !isPDF) {
          throw new Error('Unsupported file type');
        }

        setFileType(isImage ? 'image' : 'pdf');
        setPreviewUrl(src);

        if (isImage) {
          setIsLoading(true);
        }
      })
      .catch(err => {
        logger.warn('Thumbnail load failed:', err.message);
        setError(err.message);
        setIsLoading(false);
      });
  }, [src]);

  const onDocumentLoadSuccess = () => {
    setIsLoading(false);
  };

  const onDocumentLoadError = (error) => {
    logger.error('Error loading PDF:', error);
    setError('Failed to load PDF');
    setIsLoading(false);
  };

  const handleImageLoad = () => setIsLoading(false);
  const handleImageError = (error) => {
    logger.error('Error loading image:', error);
    setError('Failed to load image');
    setIsLoading(false);
  };

  if (error) {
    return <div className="receipt-thumbnail-error">{error}</div>;
  }

  if (!previewUrl && !isLoading) {
    return null;
  }

  return (
    <>
      <div
        className={'receipt-thumbnail-container'}
        style={{maxWidth}}
      >
        {isLoading && (
          <div className="receipt-thumbnail-loading">Loading...</div>
        )}

        {fileType === 'image' && previewUrl && (
          <img
            src={previewUrl}
            alt={alt}
            onLoad={handleImageLoad}
            onError={handleImageError}
            className={`receipt-thumbnail${isLoading ? 'hidden' : ''}`}
            style={{maxHeight}}
          />
        )}

        {fileType === 'pdf' && previewUrl && (
          <div
            className={isLoading ? 'hidden' : ''}
          >
            <Document
              file={previewUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading=""
            >
              <Page
                pageNumber={1}
                height={parseInt(maxHeight)}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>
          </div>
        )}
      </div>
    </>
  );
}
  
export default ReceiptThumbnail;