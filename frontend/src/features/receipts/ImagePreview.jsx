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
    return <div className="rounded-lg bg-[#f8d7da] p-5 text-center text-[#721c24]">{error}</div>;
  }

  if (!previewUrl && !isLoading) {
    return null;
  }

  const showPagination = fileType === 'pdf' && numPages > 1;

  return (
    <>
      {/* ── Inline preview ── */}
      <div
        className={`relative w-full ${enableZoom ? 'cursor-zoom-in' : ''}`}
        style={{ maxWidth }}
      >
        {isLoading && <div className="p-10 text-center text-text-muted">Loading...</div>}

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
              <div className="mt-2.5 flex items-center justify-center gap-2.5">
                <button
                  onClick={goToPrevPage}
                  disabled={pageNumber <= 1}
                  className="cursor-pointer rounded border border-[#ccc] bg-white px-2.5 py-[5px] transition-colors hover:enabled:bg-nav-bg disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <span>
                  Page {pageNumber} of {numPages}
                </span>
                <button
                  onClick={goToNextPage}
                  disabled={pageNumber >= numPages}
                  className="cursor-pointer rounded border border-[#ccc] bg-white px-2.5 py-[5px] transition-colors hover:enabled:bg-nav-bg disabled:cursor-not-allowed disabled:opacity-50"
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
            className={`absolute right-2 bg-black/60 text-white px-2 py-1 rounded text-xs cursor-pointer ${showPagination ? 'bottom-[50px]' : 'bottom-2'}`}
          >
            Click to enlarge
          </div>
        )}
      </div>

      {/* ── Fullscreen modal ── */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-[1000] flex cursor-zoom-out flex-col items-center justify-center bg-black/90 p-5"
          onClick={closeModal}
        >
          <button
            className="absolute right-5 top-5 z-[1001] border-none bg-transparent p-0 text-[32px] leading-none text-white cursor-pointer hover:text-[#ccc]"
            onClick={closeModal}
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
                  <div className="mt-5 flex items-center justify-center gap-2.5 text-white">
                    <button
                      onClick={goToPrevPage}
                      disabled={pageNumber <= 1}
                      className="cursor-pointer rounded border border-[#ccc] bg-white px-4 py-2 transition-colors hover:enabled:bg-nav-bg disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <span>
                      Page {pageNumber} of {numPages}
                    </span>
                    <button
                      onClick={goToNextPage}
                      disabled={pageNumber >= numPages}
                      className="cursor-pointer rounded border border-[#ccc] bg-white px-4 py-2 transition-colors hover:enabled:bg-nav-bg disabled:cursor-not-allowed disabled:opacity-50"
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
