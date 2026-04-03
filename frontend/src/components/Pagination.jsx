/**
 * @file Pagination.jsx
 * Minimal Previous/Next pager with an "X–Y of Z" summary.
 * Used under data tables (transactions, receipts, etc.).
 */

import './Pagination.css';

/**
 * Controlled Previous/Next pagination bar.
 *
 * Computes `totalPages` from `totalItems` / `itemsPerPage` and renders
 * nothing when the result set fits on a single page. The component only
 * emits intent via `onPageChange`; the parent owns `currentPage` and is
 * responsible for fetching/slicing data for that page.
 *
 * @component
 * @param {Object} props
 * @param {number} props.currentPage
 *        1-based index of the active page.
 * @param {number} props.totalItems
 *        Total number of items across all pages.
 * @param {number} props.itemsPerPage
 *        Page size used to compute page count and the "showing X–Y" range.
 * @param {(page: number) => void} props.onPageChange
 *        Called with the target page number (already bounds-checked;
 *        never `< 1` or `> totalPages`).
 * @returns {JSX.Element|null} `null` when `totalPages <= 1`.
 *
 * @example
 * <Pagination
 *   currentPage={page}
 *   totalItems={result.total}
 *   itemsPerPage={50}
 *   onPageChange={setPage}
 * />
 */
export default function Pagination({
  currentPage,
  totalItems,
  itemsPerPage,
  onPageChange
}) {
  const totalPages = Math.ceil(totalItems / itemsPerPage);

  if (totalPages <= 1) return null;

  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  return (
    <div className="pagination">
      <button
        onClick={handlePrevious}
        disabled={currentPage === 1}
        className="pagination-button"
      >
        Previous
      </button>

      <span className="pagination-info">
        Showing {startItem}-{endItem} of {totalItems}
      </span>

      <button
        onClick={handleNext}
        disabled={currentPage === totalPages}
        className="pagination-button"
      >
        Next
      </button>
    </div>
  );
}