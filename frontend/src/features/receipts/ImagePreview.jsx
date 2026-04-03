/**
 * @file ImagePreview.jsx
 * Large image/PDF viewer for the selected receipt, with click-to-zoom
 * modal and multi-page PDF navigation.
 *
 * Similar to {@link module:components/Thumbnail~ReceiptThumbnail}, but:
 *  - Renders at full column size, not thumbnail size.
 *  - Opens a fullscreen lightbox on click when `enableZoom`.
 *  - Supports paging through multi-page PDFs in both inline and modal
 *    views.
 */

import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import './ImagePreview.css';
import { createLogger } from '@/lib/logger';
import { parseApiError, isNotFound } from '@/lib/apiErrors';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ImagePreview');

// Point pdf.js at a CDN-hosted worker matching the bundled version.
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

/**
 * Image/PDF preview with zoom modal.
 *
 * Lifecycle per `src`:
 *  1. `HEAD src` to discover `Content-Type`. 404 → "File not found";
 *     unsupported type → error string.
 *  2. Render:
 *     - `image/*` → `<img>` bounded by `maxHeight`.
 *     - `application/pdf` → `react-pdf` `<Document>` showing page
 *       `pageNumber`, with Previous/Next controls if multi-page.
 *  3. Clicking anywhere on the preview (when `enableZoom`) opens a
 *     fullscreen modal with the same content at larger dimensions.
 *
 * @component
 * @param {Object} props
 * @param {?string} props.src - URL of the file. Nothing rendered when falsy.
 * @param {string} [props.alt="File preview"] - Alt text for images.
 * @param {string} [props.maxWidth="100%"] - CSS max-width for the inline container.
 * @param {string} [props.maxHeight="400px"]
 *        CSS max-height for images, and (parsed as int) the
 *        rasterization height for the inline PDF page.
 * @param {boolean} [props.enableZoom=true]
 *        Whether clicking opens the fullscreen modal.
 * @returns {JSX.Element|null}
 */
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
  /** `'image' | 'pdf' | null` — discovered via `HEAD`. */
  const [fileType, setFileType] = useState(null);
  /** Total page count reported by `react-pdf` on load. */
  const [numPages, setNumPages] = useState(null);
  /** 1-based current page for multi-page PDFs. */
  const [pageNumber, setPageNumber] = useState(1);

  // ── Probe content type when `src` changes ────────────────────────
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
          setIsLoading(true); // will flip off on <img> onLoad
        }
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, [src]);

  // ── react-pdf callbacks ───────────────────────────────────────────

  /** @param {{numPages: number}} info */
  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
    setIsLoading(false);
  };

  const onDocumentLoadError = (error) => {
    logger.error('Error loading PDF:', error);
    setError('Failed to load PDF');
    setIsLoading(false);
  };

  // ── <img> callbacks ───────────────────────────────────────────────

  const handleImageLoad = () => setIsLoading(false);
  const handleImageError = () => {
    setIsLoading(false);
    setError('Failed to load image');
  };

  // ── Modal + paging ────────────────────────────────────────────────

  const openModal = () => enableZoom && setIsModalOpen(true);
  const closeModal = () => setIsModalOpen(false);

  /** Go to previous PDF page, clamped at 1. */
  const goToPrevPage = (e) => {
    e.stopPropagation();
    setPageNumber((prev) => Math.max(prev - 1, 1));
  };

  /** Go to next PDF page, clamped at `numPages`. */
  const goToNextPage = (e) => {
    e.stopPropagation();
    setPageNumber((prev) => Math.min(prev + 1, numPages));
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
      {/* ── Inline preview ── */}
      <div
        className={`image-preview-container ${enableZoom ? 'zoomable' : ''}`}
        style={{ maxWidth }}
      >
        {isLoading && <div className="image-preview-loading">Loading...</div>}

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
              <div className="image-preview-pagination">
                <button onClick={goToPrevPage} disabled={pageNumber <= 1} className="pagination-btn">
                  Previous
                </button>
                <span>
                  Page {pageNumber} of {numPages}
                </span>
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

      {/* ── Fullscreen modal ── */}
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
                    <span>
                      Page {pageNumber} of {numPages}
                    </span>
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