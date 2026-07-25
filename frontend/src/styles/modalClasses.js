/**
 * @file styles/modalClasses.js
 * Shared modal chrome utility strings.
 *
 * Replaces @/styles/Modal.css. Import where needed:
 *
 *   import * as M from '@/styles/modalClasses';
 *
 *   <div className={M.BACKDROP} onClick={onBackdrop}>
 *     <div className={M.PANEL}>
 *       <div className={M.HEADER}>
 *         <h2 className={M.TITLE}>…</h2>
 *         <button className={M.CLOSE_BTN}>×</button>
 *       </div>
 *       <div className={M.BODY}>…</div>
 *       <div className={M.FOOTER}>
 *         <button className={M.BTN_SECONDARY}>Cancel</button>
 *         <button className={M.BTN_PRIMARY}>Save</button>
 *       </div>
 *     </div>
 *   </div>
 *
 * Modals that need custom widths or opacity can override inline:
 *   <div className={`${M.PANEL} max-w-[600px]`}>
 *   <div className={`${M.BACKDROP} bg-black/70`}>
 *   (omit the colliding default from the const, or layer it — the last
 *   class of the same property in the source wins in Tailwind v4.)
 *
 * When a <Modal> component is extracted, these constants fold into its
 * implementation and this file is deleted.
 */
/** Fixed overlay — click handler goes here for backdrop-close. */
export const BACKDROP =
  'fixed inset-0 z-[1000] flex items-center justify-center bg-black/50';
/**
 * Content panel — `max-w-[500px]` is the default; pass a different
 * `max-w-*` after this const to override per-modal.
 */
export const PANEL = [
  'flex max-h-[90vh] w-[90%] max-w-[500px] flex-col',
  'overflow-y-auto rounded-lg bg-white',
  'shadow-[0_10px_25px_rgba(0,0,0,0.2)]',
].join(' ');
export const HEADER =
  'flex items-center justify-between border-b border-gray-200 px-6 py-4';
/** Preflight strips heading size + weight — both must be explicit. */
export const TITLE = 'text-lg font-semibold text-gray-800';
export const CLOSE_BTN =
  'cursor-pointer text-2xl leading-none text-gray-500 transition-colors ' +
  'hover:text-gray-800 disabled:cursor-not-allowed disabled:opacity-50';
export const BODY = 'overflow-y-auto p-5';
export const FOOTER =
  'flex justify-end gap-3 border-t border-gray-200 px-6 py-4';
/** Inline error banner inside a modal body. */
export const ERROR_BANNER =
  'mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-600';
export const BTN_PRIMARY =
  'cursor-pointer rounded bg-[#2196f3] px-5 py-2.5 text-sm font-medium text-white ' +
  'transition-[background-color,opacity] hover:bg-[#1976d2] ' +
  'disabled:cursor-not-allowed disabled:opacity-50';
export const BTN_SECONDARY =
  'cursor-pointer rounded bg-[#e0e0e0] px-5 py-2.5 text-sm font-medium text-gray-800 ' +
  'transition-[background-color,opacity] hover:bg-[#d0d0d0] ' +
  'disabled:cursor-not-allowed disabled:opacity-50';