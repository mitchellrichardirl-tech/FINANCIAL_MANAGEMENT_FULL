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
  /**
   * True once react-pdf's `<Document>` has parsed the PDF and its
   * proxy is safe to query. `<Page>` is only rendered when this is
   * true, preventing it from calling `getPage()` on a proxy that
   * hasn't finished loading or has been destroyed.
   */
  const [pdfReady, setPdfReady] = useState(false);       // ← NEW

  useEffect(() => {
    if (!src) {
      setPreviewUrl(null);
      setIsLoading(false);
      setPdfReady(false);                                 // ← NEW
      return;
    }

    setError(null);
    setIsLoading(true);
    setPdfReady(false);                                   // ← NEW

    fetch(src, { method: 'HEAD' })
      .then(async (response) => {
        if (!response.ok) {
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
    setPdfReady(true);                                    // ← NEW
    setIsLoading(false);
  };

  const onDocumentLoadError = (error) => {
    logger.error('Error loading PDF:', error);
    setPdfReady(false);                                   // ← NEW
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
    return <div className="text-xs text-danger italic">{error}</div>;
  }

  if (!previewUrl && !isLoading) {
    return null;
  }

  return (
    <>
      <div
        className="inline-block overflow-hidden"
        style={{ maxWidth }}
      >
        {isLoading && (
          <div className="text-xs text-text-light">Loading...</div>
        )}

        {fileType === 'image' && previewUrl && (
          <img
            src={previewUrl}
            alt={alt}
            onLoad={handleImageLoad}
            onError={handleImageError}
            className={`w-full h-auto object-contain ${isLoading ? 'hidden' : ''}`}
            style={{ maxHeight }}
          />
        )}

        {fileType === 'pdf' && previewUrl && (
          <div
            className={isLoading ? 'hidden' : ''}
          >
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
    </>
  );
}

export default ReceiptThumbnail;