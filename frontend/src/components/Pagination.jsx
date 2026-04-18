export default function Pagination({
  currentPage,
  totalItems,
  itemsPerPage,
  onPageChange,
}) {
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  if (totalPages <= 1) return null;

  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  const btn =
    'py-2 px-4 rounded border border-[#ddd] bg-[#f9f9f9] text-[#213547] text-sm cursor-pointer hover:enabled:border-[#646cff] disabled:opacity-50 disabled:cursor-not-allowed disabled:border-transparent';

  return (
    <div className="shrink-0 flex justify-center items-center gap-2 py-4 bg-[#f5f6fa]">
      <button
        type="button"
        onClick={() => currentPage > 1 && onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className={btn}
      >
        Previous
      </button>
      <span className="text-[0.9em] text-[#888]">
        Showing {startItem}-{endItem} of {totalItems}
      </span>
      <button
        type="button"
        onClick={() => currentPage < totalPages && onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className={btn}
      >
        Next
      </button>
    </div>
  );
}
