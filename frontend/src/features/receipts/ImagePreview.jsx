/**
 * @file ImagePreview.jsx
 * Large image/PDF viewer for the selected receipt, with click-to-zoom
 * modal and multi-page PDF navigation.
 *
 * Sizing strategy (the important bit):
 *  - Both the inline frame and the modal size content from its *natural*
 *    dimensions (image pixels, or PDF page points), computing an explicit
 *    pixel width/height. `max-width`/`max-height` are deliberately NOT
 *    used for the modal: they can only shrink content, never scale it up,
 *    so they can't produce the overflow that makes scrolling possible.
 *  - The modal overlay is a plain block scroll container. Centring happens
 *    on an inner "stage" sized to max(viewport, content), so centring can
 *    never push content out of scroll reach.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
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
const ZOOM_MIN = 1;
const ZOOM_MAX = 6;
const ZOOM_STEP = 0.25;
/** Fraction of the viewport the content fills at zoom = 1 ("Fit"). */
const MODAL_FIT = 0.92;
const clampZoom = (z) => Math.min(Math.max(z, ZOOM_MIN), ZOOM_MAX);
/**
 * Image/PDF preview with a zooming, pannable fullscreen modal.
 *
 * @component
 * @param {Object} props
 * @param {?string} props.src - URL of the file. Nothing rendered when falsy.
 * @param {string} [props.alt="File preview"] - Alt text for images.
 * @param {string} [props.maxWidth="100%"] - CSS max-width for the inline container.
 * @param {string} [props.maxHeight="400px"] - Max height of the inline preview.
 * @param {boolean} [props.enableZoom=true] - Whether clicking opens the modal.
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
  /** Total page count reported by react-pdf on load. */
  const [numPages, setNumPages] = useState(null);
  /** 1-based current page for multi-page PDFs. */
  const [pageNumber, setPageNumber] = useState(1);
  /** Zoom multiplier in the modal. 1 = fit-to-screen. */
  const [zoom, setZoom] = useState(1);
  /**
   * Natural size of the current content — image pixels, or PDF page
   * points at scale 1 (rotation applied). Everything else is derived
   * from this, so if it's null we're flying blind and fall back to
   * width-binding.
   */
  const [natural, setNatural] = useState(null); // { w, h } | null
  /** The inline frame, measured so PDFs can be fitted into it. */
  const frameRef = useRef(null);
  const [frameWidth, setFrameWidth] = useState(0);
  /** The modal's scroll container — we drive scrollLeft/Top for panning. */
  const scrollRef = useRef(null);
  /** Held PDFDocumentProxy, so we can query page sizes ourselves. */
  const pdfRef = useRef(null);
  // ── Viewport size (modal fitting depends on it) ────────────────────
  const [viewport, setViewport] = useState(() => ({
    w: window.innerWidth,
    h: window.innerHeight,
  }));
  useEffect(() => {
    const onResize = () => setViewport({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  // ── Measure the inline frame ──────────────────────────────────────
  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setFrameWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [previewUrl]);
  // ── Probe content type when `src` changes ─────────────────────────
  useEffect(() => {
    if (!src) {
      setPreviewUrl(null);
      setIsLoading(false);
      return;
    }
    setError(null);
    setPageNumber(1);
    setNumPages(null);
    setFileType(null);
    setNatural(null);
    pdfRef.current = null;
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
        if (isImage) setIsLoading(true); // flips off on <img> onLoad
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, [src]);
  // ── PDF page measurement ──────────────────────────────────────────
  /**
   * Ask pdf.js directly for a page's size at scale 1. Doing this from
   * the PDFDocumentProxy rather than react-pdf's <Page onLoadSuccess>
   * keeps us independent of react-pdf's callback shape across versions.
   *
   * @param {Object} pdf - PDFDocumentProxy
   * @param {number} pageNum - 1-based page number
   */
  const measurePdfPage = useCallback(async (pdf, pageNum) => {
    try {
      const page = await pdf.getPage(pageNum);
      const vp = page.getViewport({ scale: 1 });
      console.log('[IP] measured', pageNum, vp.width, vp.height);   // TEMP
      setNatural({ w: vp.width, h: vp.height });
    } catch (err) {
      console.error('[IP] measure FAILED', err);                    // TEMP
      setNatural(null);
    }
  }, []);
  /** @param {Object} pdf - PDFDocumentProxy */
  const onDocumentLoadSuccess = useCallback(
    (pdf) => {
      pdfRef.current = pdf;
      setNumPages(pdf.numPages);
      setIsLoading(false);
      measurePdfPage(pdf, pageNumber);
    },
    [measurePdfPage, pageNumber]
  );
  const onDocumentLoadError = (err) => {
    logger.error('Error loading PDF:', err);
    setError('Failed to load PDF');
    setIsLoading(false);
  };
  // Re-measure when paging. Deliberately does NOT null `natural` first,
  // so the previous page's size is held until the new one resolves.
  useEffect(() => {
    if (fileType !== 'pdf') return;
    const pdf = pdfRef.current;
    if (!pdf) return;
    measurePdfPage(pdf, pageNumber);
  }, [pageNumber, fileType, measurePdfPage]);
  // ── <img> callbacks ───────────────────────────────────────────────
  const handleImageLoad = (e) => {
    setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
    setIsLoading(false);
  };
  const handleImageError = () => {
    setIsLoading(false);
    setError('Failed to load image');
  };
  // ── Modal + paging ────────────────────────────────────────────────
  const openModal = () => {
    if (!enableZoom) return;
    setZoom(1);
    setIsModalOpen(true);
  };
  const closeModal = () => setIsModalOpen(false);
  const goToPrevPage = (e) => {
    e.stopPropagation();
    setPageNumber((prev) => Math.max(prev - 1, 1));
  };
  const goToNextPage = (e) => {
    e.stopPropagation();
    setPageNumber((prev) => Math.min(prev + 1, numPages));
  };
  // ── Modal lifecycle: keys, body scroll lock ───────────────────────
  useEffect(() => {
    if (!isModalOpen) return;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setIsModalOpen(false);
      if (e.key === '+' || e.key === '=') setZoom((z) => clampZoom(z + ZOOM_STEP));
      if (e.key === '-') setZoom((z) => clampZoom(z - ZOOM_STEP));
      if (e.key === '0') setZoom(1);
    };
    window.addEventListener('keydown', onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [isModalOpen]);
  // ── Ctrl/⌘ + wheel to zoom ────────────────────────────────────────
  // React attaches `wheel` passively at the root, so preventDefault() in
  // an onWheel prop is ignored. This needs a native, non-passive listener.
  useEffect(() => {
    if (!isModalOpen) return;
    const el = scrollRef.current;
    if (!el) return;
    const onWheelNative = (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setZoom((z) => clampZoom(z + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP)));
    };
    el.addEventListener('wheel', onWheelNative, { passive: false });
    return () => el.removeEventListener('wheel', onWheelNative);
  }, [isModalOpen]);
  // ── Drag-to-pan (mouse only; touch scrolls natively) ──────────────
  const dragRef = useRef(null);
  const didDragRef = useRef(false);
  const [isDragging, setIsDragging] = useState(false);
  const onPointerDown = (e) => {
    if (e.button !== 0 || e.pointerType !== 'mouse') return;
    const el = scrollRef.current;
    if (!el) return;
    dragRef.current = {
      x: e.clientX,
      y: e.clientY,
      left: el.scrollLeft,
      top: el.scrollTop,
      pointerId: e.pointerId,
    };
    didDragRef.current = false;
    setIsDragging(true);
  };
  const onPointerMove = (e) => {
    const d = dragRef.current;
    const el = scrollRef.current;
    if (!d || !el) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    // Only treat it as a drag past a small threshold, so a sloppy click
    // still closes the modal.
    if (!didDragRef.current && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
      didDragRef.current = true;
      el.setPointerCapture?.(d.pointerId);
    }
    if (!didDragRef.current) return;
    el.scrollLeft = d.left - dx;
    el.scrollTop = d.top - dy;
  };
  const onPointerUp = (e) => {
    scrollRef.current?.releasePointerCapture?.(e.pointerId);
    dragRef.current = null;
    setIsDragging(false);
  };
  /** Backdrop click closes — unless the click concluded a pan gesture. */
  const onOverlayClick = () => {
    if (didDragRef.current) {
      didDragRef.current = false;
      return;
    }
    closeModal();
  };
  // ── Early returns ─────────────────────────────────────────────────
  if (error) {
    return <div className="image-preview-error">{error}</div>;
  }
  if (!previewUrl && !isLoading) {
    return null;
  }
  // ── Derived sizing ────────────────────────────────────────────────
  const showPagination = fileType === 'pdf' && numPages > 1;
  const maxH = parseInt(maxHeight, 10) || 400;
  /**
   * Inline: bind whichever axis runs out first, so content can never
   * exceed the frame in either direction. `null` = not measured yet.
   */
  const inlineFit = (() => {
    if (!frameWidth) return null;
    if (!natural) return { width: frameWidth };
    const aspect = natural.w / natural.h;
    return frameWidth / aspect <= maxH ? { width: frameWidth } : { height: maxH };
  })();
  /**
   * Modal: scale-to-fit at zoom 1, then multiply. These are explicit
   * pixel sizes, so content genuinely grows past the viewport — which is
   * what gives the scroll container something to scroll.
   */
  const fitScale = natural
    ? Math.min((viewport.w * MODAL_FIT) / natural.w, (viewport.h * MODAL_FIT) / natural.h)
    : 1;
  const displayW = natural
    ? Math.round(natural.w * fitScale * zoom)
    : Math.round(viewport.w * MODAL_FIT * zoom); // fallback: bind width only
  const displayH = natural ? Math.round(natural.h * fitScale * zoom) : 0;
  console.log('[IP] render', { fileType, zoom, natural, fitScale, displayW, displayH }); // TEMP
  /** Only size the <img> once we know its natural dimensions. */
  const modalImgStyle = natural
    ? { width: `${displayW}px`, height: `${displayH}px` }
    : undefined;
  return (
    <>
      {/* ── Inline preview ── */}
      <div
        ref={frameRef}
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
        {fileType === 'pdf' && previewUrl && inlineFit && (
          <div onClick={openModal} className={isLoading ? 'hidden' : ''}>
            <Document
              file={previewUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading=""
            >
              <Page
                pageNumber={pageNumber}
                {...inlineFit}
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
        <div
          ref={scrollRef}
          className={`image-preview-modal ${zoom > 1 ? 'is-zoomed' : ''} ${
            isDragging ? 'is-dragging' : ''
          }`}
          onClick={onOverlayClick}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <div className="ip-modal-toolbar" onClick={(e) => e.stopPropagation()}>
            <button
              className="pagination-btn"
              onClick={() => setZoom((z) => clampZoom(z - ZOOM_STEP))}
              disabled={zoom <= ZOOM_MIN}
              aria-label="Zoom out"
            >
              −
            </button>
            <button className="pagination-btn" onClick={() => setZoom(1)} disabled={zoom === 1}>
              Fit
            </button>
            <span className="ip-zoom-level">{Math.round(zoom * 100)}%</span>
            <button
              className="pagination-btn"
              onClick={() => setZoom((z) => clampZoom(z + ZOOM_STEP))}
              disabled={zoom >= ZOOM_MAX}
              aria-label="Zoom in"
            >
              +
            </button>
            <button className="ip-modal-close" onClick={closeModal} aria-label="Close">
              ×
            </button>
          </div>
          <div className="ip-modal-stage">
            <div className="ip-modal-figure" onClick={(e) => e.stopPropagation()}>
              {fileType === 'image' ? (
                <img
                  src={previewUrl}
                  alt={alt}
                  className="ip-modal-image"
                  onLoad={handleImageLoad}
                  onError={handleImageError}
                  style={modalImgStyle}
                  draggable={false}
                />
              ) : (
                <>
                  <Document
                    file={previewUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    onLoadError={onDocumentLoadError}
                    loading=""
                  >
                    <Page
                      pageNumber={pageNumber}
                      width={displayW}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                    />
                  </Document>
                  {showPagination && (
                    <div className="image-preview-pagination ip-modal-pagination">
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
        </div>
      )}
    </>
  );
}
export default ImagePreview;