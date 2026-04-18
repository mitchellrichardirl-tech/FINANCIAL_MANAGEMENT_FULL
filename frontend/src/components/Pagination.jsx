/**
 * @file Pagination.jsx
 * Minimal Previous/Next pager with an "X–Y of Z" summary.
 * Used under data tables (transactions, receipts, etc.).
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
    <div className="shrink-0 flex justify-center items-center gap-2 py-4 bg-bg">
      <button
        onClick={handlePrevious}
        disabled={currentPage === 1}
        className="py-[0.5em] px-[1em] disabled:opacity-50 disabled:cursor-not-allowed disabled:border-transparent"
      >
        Previous
      </button>

      <span className="text-[0.9em] text-text-light">
        Showing {startItem}-{endItem} of {totalItems}
      </span>

      <button
        onClick={handleNext}
        disabled={currentPage === totalPages}
        className="py-[0.5em] px-[1em] disabled:opacity-50 disabled:cursor-not-allowed disabled:border-transparent"
      >
        Next
      </button>
    </div>
  );
}