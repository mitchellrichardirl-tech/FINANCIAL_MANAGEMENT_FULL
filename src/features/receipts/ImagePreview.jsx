import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import './ImagePreview.css';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

function ImagePreview({ 
  src,
  alt = "File preview",
  maxWidth = "100%",
  maxHeight = "400px",
  enableZoom = true
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
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to fetch file: ${response.status}`);
        }
        
        const contentType = response.headers.get('Content-Type');
        
        if (!contentType) {
          throw new Error('No content type specified');
        }

        const isImage = contentType.startsWith('image/');
        const isPDF = contentType.includes('application/pdf');

        if (!isImage && !isPDF) {
          throw new Error(`Unsupported file type: ${contentType}`);
        }

        setFileType(isImage ? 'image' : 'pdf');
        setPreviewUrl(src);
        
        if (isImage) {
          setIsLoading(true);
        }
      })
      .catch(err => {
        setError(err.message);
        setIsLoading(false);
      });
  }, [src]);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
    setIsLoading(false);
  };

  const onDocumentLoadError = (error) => {
    console.error('Error loading PDF:', error);
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
    setPageNumber(prev => Math.max(prev - 1, 1));
  };

  const goToNextPage = (e) => {
    e.stopPropagation();
    setPageNumber(prev => Math.min(prev + 1, numPages));
  };

  if (error) {
    return <div className="image-preview-error">{error}</div>;
  }

  if (!previewUrl && !isLoading) {
    return null;
  }

  const showPagination = fileType === 'pdf' && numPages > 1;

  return (
    <>
      <div 
        className={`image-preview-container ${enableZoom ? 'zoomable' : ''}`}
        style={{ maxWidth }}
      >
        {isLoading && (
          <div className="image-preview-loading">Loading...</div>
        )}
        
        {fileType === 'image' && previewUrl && (
          <img
            src={previewUrl}
            alt={alt}
            onLoad={handleImageLoad}
            onError={handleImageError}
            onClick={openModal}
            className={`image-preview-img ${isLoading ? 'hidden' : ''}`}
            style={{ maxHeight }}
          />
        )}
        
        {fileType === 'pdf' && previewUrl && (
          <div 
            onClick={openModal}
            className={isLoading ? 'hidden' : ''}
          >
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
              <div className="image-preview-pagination">
                <button 
                  onClick={goToPrevPage}
                  disabled={pageNumber <= 1}
                  className="pagination-btn"
                >
                  Previous
                </button>
                <span>Page {pageNumber} of {numPages}</span>
                <button 
                  onClick={goToNextPage}
                  disabled={pageNumber >= numPages}
                  className="pagination-btn"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}

        {enableZoom && !isLoading && previewUrl && (
          <div 
            onClick={openModal}
            className={`image-preview-zoom-hint ${showPagination ? 'with-pagination' : ''}`}
          >
            Click to enlarge
          </div>
        )}
      </div>

      {isModalOpen && (
        <div className="image-preview-modal" onClick={closeModal}>
          <button className="modal-close-btn" onClick={closeModal}>
            ×
          </button>
          
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            {fileType === 'image' ? (
              <img src={previewUrl} alt={alt} className="modal-image" />
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
                  <div className="image-preview-pagination modal-pagination">
                    <button 
                      onClick={goToPrevPage}
                      disabled={pageNumber <= 1}
                      className="pagination-btn"
                    >
                      Previous
                    </button>
                    <span>Page {pageNumber} of {numPages}</span>
                    <button 
                      onClick={goToNextPage}
                      disabled={pageNumber >= numPages}
                      className="pagination-btn"
                    >
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