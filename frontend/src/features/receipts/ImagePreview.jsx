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
// ⚠️ Third-party stylesheets — NOT part of the Tailwind migration, keep.
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { createLogger } from '@/lib/logger';
import { parseApiError, isNotFound } from '@/lib/apiErrors';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ImagePreview');
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
const ZOOM_MIN = 1;
const ZOOM_MAX = 6;
const ZOOM_STEP = 0.25;
/** Fraction of the viewport the content fills at zoom = 1 ("Fit"). */
const MODAL_FIT = 0.92;
const clampZoom = (z) => Math.min(Math.max(z, ZOOM_MIN), ZOOM_MAX);
/* ── Reused class strings ──────────────────────────────────────────── */
const BTN_BASE =
  'cursor-pointer rounded border border-gray-300 bg-white transition-colors ' +
  'hover:bg-[#f0f0f0] disabled:cursor-not-allowed disabled:opacity-50';
/** Inline pagination + modal toolbar buttons. */
const BTN_SM = `${BTN_BASE} px-2.5 py-[5px]`;
/** Modal pagination buttons (larger hit area). */
const BTN_MD = `${BTN_BASE} px-4 py-2`;
const PAGINATION_ROW = 'mt-2.5 flex items-center justify-center gap-2.5';
/**
 * Safety net for react-pdf's canvas, which receives inline width/height.
 * `!important` is genuinely required to beat inline styles.
 * Targets the element rather than react-pdf's class names, which vary
 * by version.
 */
const CANVAS_GUARD = '[&_canvas]:max-w-full! [&_canvas]:h-auto!';
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
  const [fileType, setFileType] = useState(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [natural, setNatural] = useState(null); // { w, h } | null
  const frameRef = useRef(null);
  const [frameWidth, setFrameWidth] = useState(0);
  const scrollRef = useRef(null);
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
  const onOverlayClick = () => {
    if (didDragRef.current) {
      didDragRef.current = false;
      return;
    }
    closeModal();
  };
  // ── Early returns ─────────────────────────────────────────────────
  if (error) {
    return (
      <div className="rounded-lg bg-danger-bg p-5 text-center text-danger-text">
        {error}
      </div>
    );
  }
  if (!previewUrl && !isLoading) {
    return null;
  }
  // ── Derived sizing ────────────────────────────────────────────────
  const showPagination = fileType === 'pdf' && numPages > 1;
  const maxH = parseInt(maxHeight, 10) || 400;
  const inlineFit = (() => {
    if (!frameWidth) return null;
    if (!natural) return { width: frameWidth };
    const aspect = natural.w / natural.h;
    return frameWidth / aspect <= maxH ? { width: frameWidth } : { height: maxH };
  })();
  const fitScale = natural
    ? Math.min((viewport.w * MODAL_FIT) / natural.w, (viewport.h * MODAL_FIT) / natural.h)
    : 1;
  const displayW = natural
    ? Math.round(natural.w * fitScale * zoom)
    : Math.round(viewport.w * MODAL_FIT * zoom);
  const displayH = natural ? Math.round(natural.h * fitScale * zoom) : 0;
  console.log('[IP] render', { fileType, zoom, natural, fitScale, displayW, displayH }); // TEMP
  const modalImgStyle = natural
    ? { width: `${displayW}px`, height: `${displayH}px` }
    : undefined;
  // ── Derived cursors (replaces .is-zoomed / .is-dragging) ──────────
  const modalCursor = isDragging
    ? 'cursor-grabbing'
    : zoom > 1
      ? 'cursor-grab'
      : 'cursor-zoom-out';
  /** `.image-preview-modal.is-zoomed .ip-modal-figure { cursor: inherit }` */
  const figureCursor = zoom > 1 ? 'cursor-[inherit]' : 'cursor-default';
  const stopProp = (e) => e.stopPropagation();
  return (
    <>
      {/* ── Inline preview ── */}
      <div
        ref={frameRef}
        className={`relative w-full overflow-hidden ${CANVAS_GUARD} ${
          enableZoom ? 'cursor-zoom-in' : ''
        }`}
        style={{ maxWidth }}
      >
        {isLoading && <div className="p-10 text-center text-muted">Loading...</div>}
        {fileType === 'image' && previewUrl && (
          <img
            src={previewUrl}
            alt={alt}
            onLoad={handleImageLoad}
            onError={handleImageError}
            onClick={openModal}
            /* Explicit block/hidden — avoids relying on utility ordering.
               NOTE: the old CSS had `.image-preview-img { display: block }`
               overriding `.hidden`, so hiding-while-loading never worked. */
            className={`mx-auto h-auto max-w-full rounded-lg shadow-[0_2px_8px_rgba(0,0,0,0.1)] ${
              isLoading ? 'hidden' : 'block'
            }`}
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
              <div className={PAGINATION_ROW}>
                <button onClick={goToPrevPage} disabled={pageNumber <= 1} className={BTN_SM}>
                  Previous
                </button>
                <span>
                  Page {pageNumber} of {numPages}
                </span>
                <button
                  onClick={goToNextPage}
                  disabled={pageNumber >= numPages}
                  className={BTN_SM}
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
            className={`absolute right-2 cursor-pointer rounded bg-black/60 px-2 py-1 text-xs text-white ${
              showPagination ? 'bottom-[50px]' : 'bottom-2'
            }`}
          >
            Click to enlarge
          </div>
        )}
      </div>
      {/* ── Fullscreen modal ── */}
      {isModalOpen && (
        /* Scroll container. Plain block — NOT flex. Centring here would
           trap overflow past the top/left edge. */
        <div
          ref={scrollRef}
          className={`fixed inset-0 z-[1000] overflow-auto overscroll-contain bg-black/90 ${modalCursor}`}
          onClick={onOverlayClick}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <div
            className="fixed top-4 right-4 z-[1001] flex cursor-default items-center gap-2 rounded-md bg-black/55 px-2.5 py-1.5"
            onClick={stopProp}
          >
            <button
              className={BTN_SM}
              onClick={() => setZoom((z) => clampZoom(z - ZOOM_STEP))}
              disabled={zoom <= ZOOM_MIN}
              aria-label="Zoom out"
            >
              −
            </button>
            <button className={BTN_SM} onClick={() => setZoom(1)} disabled={zoom === 1}>
              Fit
            </button>
            <span className="min-w-12 text-center text-[13px] tabular-nums text-white">
              {Math.round(zoom * 100)}%
            </span>
            <button
              className={BTN_SM}
              onClick={() => setZoom((z) => clampZoom(z + ZOOM_STEP))}
              disabled={zoom >= ZOOM_MAX}
              aria-label="Zoom in"
            >
              +
            </button>
            <button
              className="cursor-pointer border-none bg-transparent px-1 text-[28px] leading-none text-white hover:text-gray-300"
              onClick={closeModal}
              aria-label="Close"
            >
              ×
            </button>
          </div>
          {/* max(viewport, content) in both axes. Because the stage is never
              smaller than its content, free space is never negative, so
              centring here cannot push anything out of scroll reach. */}
          <div className="flex min-h-full w-max min-w-full items-center justify-center">
            {/*
             * Explicit size/overflow resets are belt-and-braces against
             * app-wide styles leaking in (a generic `.modal-content` with
             * `width: 560px; overflow: hidden` previously clipped the
             * zoomed canvas and killed all scrolling). Nothing in this
             * subtree may be size-constrained or clipped.
             */}
            <div
              className={`flex h-auto max-h-none w-auto max-w-none flex-col items-center overflow-visible px-6 pt-18 pb-6 ${figureCursor}`}
              onClick={stopProp}
            >
              {fileType === 'image' ? (
                <img
                  src={previewUrl}
                  alt={alt}
                  /* Size comes from JS — see modalImgStyle. */
                  className="block max-h-none max-w-none select-none [-webkit-user-drag:none]"
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
                    <div className="mt-5 flex items-center justify-center gap-2.5 text-white">
                      <button
                        onClick={goToPrevPage}
                        disabled={pageNumber <= 1}
                        className={BTN_MD}
                      >
                        Previous
                      </button>
                      <span>
                        Page {pageNumber} of {numPages}
                      </span>
                      <button
                        onClick={goToNextPage}
                        disabled={pageNumber >= numPages}
                        className={BTN_MD}
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