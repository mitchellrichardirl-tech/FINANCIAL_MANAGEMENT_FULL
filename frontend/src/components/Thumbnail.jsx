/**
 * @file Thumbnail.jsx
 * Small preview of a stored receipt file (image or PDF).
 *
 * Given a URL, issues a `HEAD` request to discover the file's
 * `Content-Type`, then renders either an `<img>` or the first page of a
 * PDF via `react-pdf`. Shows a loading placeholder while the type probe
 * and subsequent render are in flight, and a short error string if
 * anything fails.
 */

import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { parseApiError, getUserMessage, isNotFound } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ReceiptThumbnail');

// Point pdf.js at a CDN-hosted worker matching the bundled version.
// Set once at module load; required before any <Document> renders.
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

/**
 * Thumbnail preview for a receipt file served by the backend.
 *
 * Lifecycle per `src`:
 *  1. `HEAD src` to read `Content-Type` without downloading the body.
 *     Non-OK responses are run through {@link parseApiError} so the
 *     displayed message is user-friendly (e.g. "Image no longer
 *     available" for 404s).
 *  2. On success, renders:
 *     - `image/*` → `<img>` bounded by `maxHeight`.
 *     - `application/pdf` → page 1 via `react-pdf`, rasterized to
 *       `maxHeight` pixels, with text/annotation layers disabled for
 *       a lightweight render.
 *  3. A "Loading…" placeholder overlays the slot until the actual
 *     image/PDF finishes loading.
 *
 * @component
 * @param {Object} props
 * @param {?string} props.src
 *        URL of the file to preview. When falsy, the component renders
 *        nothing.
 * @param {string} [props.alt="File thumbnail"]
 *        `alt` text for image previews (ignored for PDFs).
 * @param {string} [props.maxWidth="50px"]
 *        CSS `max-width` applied to the outer container.
 * @param {string} [props.maxHeight="100px"]
 *        CSS `max-height` for images and, parsed to an integer, the
 *        rasterization height passed to `react-pdf`'s `<Page>`.
 * @returns {JSX.Element|null}
 *
 * @example
 * <ReceiptThumbnail
 *   src={`/api/receipts/${receipt.id}/file`}
 *   maxWidth="60px"
 *   maxHeight="80px"
 * />
 */
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

  /** `react-pdf` callback — document parsed, page about to paint. */
  const onDocumentLoadSuccess = () => {
    setIsLoading(false);
  };

  /**
   * `react-pdf` callback — document failed to load/parse.
   * @param {Error} error
   */
  const onDocumentLoadError = (error) => {
    logger.error('Error loading PDF:', error);
    setError('Failed to load PDF');
    setIsLoading(false);
  };

  /** `<img>` onLoad — reveal the image and drop the placeholder. */
  const handleImageLoad = () => setIsLoading(false);

  /**
   * `<img>` onError — network/decoding failure after the HEAD succeeded.
   * @param {import('react').SyntheticEvent<HTMLImageElement>} error
   */
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
        style={{ maxWidth }}
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
            style={{ maxHeight }}
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