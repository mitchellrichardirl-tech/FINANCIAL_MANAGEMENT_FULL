import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { createLogger } from '@/lib/logger';
import { parseApiError, isNotFound } from '@/lib/apiErrors';

const logger = createLogger('ImagePreview');

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

function ImagePreview({
  src,
  alt = 'File preview',
  maxWidth = '100%',
  maxHeight = '400px',
  enableZoom = true,
}) {
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fileType, setFileType] = useState(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);

  useEffect(() => {
    if (!src) {
      setPreviewUrl(null);
      setIsLoading(false);
      return;
    }
    setError(null);
    setPageNumber(1);
    setIsLoading(true);

    fetch(src, { method: 'HEAD' })
      .then((response) => {
        if (!response.ok) {
          const parsed = parseApiError(response);
          throw new Error(
            isNotFound(parsed)
              ? 'File not found (it may have been deleted)'
              : 'Unable to load file preview'
          );
        }
        const contentType = response.headers.get('Content-Type');
        if (!contentType) throw new Error('No content type specified');
        const isImage = contentType.startsWith('image/');
        const isPDF = contentType.includes('application/pdf');
        if (!isImage && !isPDF) throw new Error(`Unsupported file type: ${contentType}`);
        setFileType(isImage ? 'image' : 'pdf');
        setPreviewUrl(src);
        if (isImage) setIsLoading(true);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, [src]);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
    setIsLoading(false);
  };
  const onDocumentLoadError = (err) => {
    logger.error('Error loading PDF:', err);
    setError('Failed to load PDF');
    setIsLoading(false);
  };
  const handleImageLoad = () => setIsLoading(false);
  const handleImageError = () => {
    setIsLoading(false);
    setError('Failed to load image');
  };
  const openModal = () => enableZoom && setIsModalOpen(true);
  const closeModal = () => setIsModalOpen(false);
  const goToPrevPage = (e) => {
    e.stopPropagation();
    setPageNumber((p) => Math.max(p - 1, 1));
  };
  const goToNextPage = (e) => {
    e.stopPropagation();
    setPageNumber((p) => Math.min(p + 1, numPages));
  };

  if (error) return <div className="p-5 bg-[#f8d7da] text-[#721c24] rounded-lg text-center">{error}</div>;
  if (!previewUrl && !isLoading) return null;

  const showPagination = fileType === 'pdf' && numPages > 1;
  const pagBtnCls =
    'py-1 px-2.5 cursor-pointer border border-[#ccc] bg-white rounded transition-colors duration-200 hover:enabled:bg-[#f0f0f0] disabled:cursor-not-allowed disabled:opacity-50';

  return (
    <>
      <div
        className={`relative w-full ${enableZoom ? 'cursor-zoom-in' : ''}`}
        style={{ maxWidth }}
      >
        {isLoading && <div className="p-10 text-center text-[#666]">Loading...</div>}

        {fileType === 'image' && previewUrl && (
          <img
            src={previewUrl}
            alt={alt}
            onLoad={handleImageLoad}
            onError={handleImageError}
            onClick={openModal}
            className={`max-w-full rounded-lg shadow-[0_2px_8px_rgba(0,0,0,0.1)] block ${isLoading ? 'hidden' : ''}`}
            style={{ maxHeight }}
          />
        )}

        {fileType === 'pdf' && previewUrl && (
          <div onClick={openModal} className={isLoading ? 'hidden' : ''}>
            <Document
              file={previewUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading=""
            >
              <Page
                pageNumber={pageNumber}
                height={parseInt(maxHeight)}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>
            {showPagination && (
              <div className="flex justify-center items-center gap-2.5 mt-2.5">
                <button type="button" onClick={goToPrevPage} disabled={pageNumber <= 1} className={pagBtnCls}>
                  Previous
                </button>
                <span>Page {pageNumber} of {numPages}</span>
                <button type="button" onClick={goToNextPage} disabled={pageNumber >= numPages} className={pagBtnCls}>
                  Next
                </button>
              </div>
            )}
          </div>
        )}

        {enableZoom && !isLoading && previewUrl && (
          <div
            onClick={openModal}
            className={`absolute right-2 bg-black/60 text-white py-1 px-2 rounded text-xs cursor-pointer ${showPagination ? 'bottom-[50px]' : 'bottom-2'}`}
          >
            Click to enlarge
          </div>
        )}
      </div>

      {isModalOpen && (
        <div
          className="fixed inset-0 bg-black/90 flex flex-col items-center justify-center z-[1000] cursor-zoom-out p-5"
          onClick={closeModal}
        >
          <button
            type="button"
            onClick={closeModal}
            className="absolute top-5 right-5 bg-transparent border-0 text-white text-[32px] cursor-pointer z-[1001] p-0 leading-none hover:text-[#ccc]"
          >
            ×
          </button>
          <div className="flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            {fileType === 'image' ? (
              <img src={previewUrl} alt={alt} className="max-w-[90vw] max-h-[90vh] object-contain" />
            ) : (
              <>
                <Document file={previewUrl} onLoadSuccess={onDocumentLoadSuccess}>
                  <Page
                    pageNumber={pageNumber}
                    width={Math.min(window.innerWidth * 0.9, 1200)}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                  />
                </Document>
                {showPagination && (
                  <div className="flex justify-center items-center gap-2.5 mt-5 text-white">
                    <button type="button" onClick={goToPrevPage} disabled={pageNumber <= 1} className={`${pagBtnCls} py-2 px-4`}>
                      Previous
                    </button>
                    <span>Page {pageNumber} of {numPages}</span>
                    <button type="button" onClick={goToNextPage} disabled={pageNumber >= numPages} className={`${pagBtnCls} py-2 px-4`}>
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default ImagePreview;
