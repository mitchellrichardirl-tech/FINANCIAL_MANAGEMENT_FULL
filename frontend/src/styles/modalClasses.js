/**
 * @file styles/modalClasses.js
 * Canonical modal chrome, as Tailwind utility strings.
 *
 * Derived from the former RemapPartyModal.css, which was the best-specified
 * modal CSS in the codebase (all-Tailwind palette, light-only, correct
 * scroll contract, fully-styled buttons) AND — by stylesheet load order —
 * the design that was actually winning for both RemapPartyModal and
 * BulkEditModal.
 *
 * Usage:
 *   import * as M from '@/styles/modalClasses';
 *
 *   <div className={M.BACKDROP} onClick={onBackdrop}>
 *     <div className={`${M.PANEL} ${M.W_MD}`}>
 *       <div className={M.HEADER}>
 *         <h2 className={M.TITLE}>…</h2>
 *         <button className={M.CLOSE_BTN}>×</button>
 *       </div>
 *       <div className={M.BODY}>
 *         <section className={M.SECTION}>
 *           <h3 className={M.SECTION_TITLE}>…</h3>
 *           <p className={M.HINT}>…</p>
 *           <div className={M.FIELD}>
 *             <label className={M.FIELD_LABEL}>…</label>
 *             …
 *           </div>
 *         </section>
 *       </div>
 *       <div className={M.FOOTER}>
 *         <button className={M.BTN_SECONDARY}>Cancel</button>
 *         <button className={M.BTN_PRIMARY}>Save</button>
 *       </div>
 *     </div>
 *   </div>
 */
export const BACKDROP =
  'fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4';
/** Pair with exactly one `W_*` width constant. */
export const PANEL =
  'flex max-h-[90vh] w-full flex-col overflow-hidden rounded-lg bg-white ' +
  'shadow-[0_4px_24px_rgba(0,0,0,0.18)]';
/* Width variants — catalogued from the five modal implementations found. */
export const W_SM = 'max-w-[440px]'; // ReceiptUploadModal
export const W_MD = 'max-w-[520px]'; // RemapPartyModal
export const W_LG = 'max-w-[560px]'; // former shared default
export const W_XL = 'max-w-[640px]'; // ReceiptViewModal
export const HEADER =
  'flex shrink-0 items-center justify-between border-b border-gray-200 px-6 pt-5 pb-4';
/** Preflight strips heading size + weight — both explicit. */
export const TITLE = 'text-[1.2rem] font-semibold text-gray-900';
export const CLOSE_BTN =
  'cursor-pointer rounded px-1 text-2xl leading-none text-gray-500 ' +
  'transition-[color,background] hover:bg-gray-100 hover:text-gray-900 ' +
  'disabled:cursor-not-allowed disabled:opacity-40';
export const ERROR_BANNER =
  'mx-6 mt-3 flex shrink-0 items-center justify-between gap-2 rounded-md ' +
  'border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-600';
export const ERROR_DISMISS =
  'shrink-0 cursor-pointer text-[1.1rem] leading-none text-red-600';
/**
 * Scrollable body. `overflow-y-auto` already zeroes the flex automatic
 * minimum, but `min-h-0` is kept for explicitness.
 */
export const BODY =
  'flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-6 py-4';
export const SECTION = 'flex flex-col gap-3';
export const SECTION_TITLE =
  'text-[0.95rem] font-semibold uppercase tracking-wider text-gray-700';
export const HINT = 'text-[0.8rem] leading-[1.4] text-gray-500';
export const FIELD = 'flex flex-col gap-[0.3rem]';
export const FIELD_LABEL = 'text-[0.85rem] font-medium text-gray-700';
export const FOOTER =
  'flex shrink-0 justify-end gap-3 border-t border-gray-200 px-6 py-4';
export const BTN_SECONDARY =
  'cursor-pointer rounded-md border border-gray-300 bg-white px-[1.1rem] py-2 ' +
  'text-[0.9rem] text-gray-700 transition-[background,border-color] ' +
  'hover:border-gray-400 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
export const BTN_PRIMARY =
  'cursor-pointer rounded-md bg-blue-600 px-5 py-2 text-[0.9rem] font-medium text-white ' +
  'transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300';