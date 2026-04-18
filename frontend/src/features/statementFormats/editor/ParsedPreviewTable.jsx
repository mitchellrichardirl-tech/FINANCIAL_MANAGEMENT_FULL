/**
 * @file editor/ParsedPreviewTable.jsx
 * Compact read-only table of `previewFormat()` output rows. Shows just
 * enough to verify the mapping worked: date parsed, amount has the right
 * sign, description came through.
 */

/**
 * @component
 * @param {Object} props
 * @param {Object[]} props.rows  - `preview_rows` from the preview endpoint.
 * @param {number}   props.total - `total_parsed` (rows may be a capped subset).
 */
export default function ParsedPreviewTable({ rows, total }) {
  if (!rows?.length) {
    return (
      <div className="p-6 text-center text-[#6c757d] bg-[#f8f9fa] border border-dashed border-[#dee2e6] rounded-[6px]">
        No transactions were produced. Check the column mapping and any exclude
        patterns.
      </div>
    );
  }

  const capped = total > rows.length;

  return (
    <div>
      <div className="text-sm mb-2.5 text-text-dark">
        <strong>{total}</strong> transaction{total === 1 ? '' : 's'} parsed
        {capped && <> — showing the first {rows.length}</>}.
      </div>

      <div className="max-h-[45vh] overflow-auto border border-[#dee2e6] rounded">
        <table className="w-full border-collapse text-[13px] bg-surface">
          <thead>
            <tr>
              <th className="sticky top-0 bg-[#f8f9fa] font-semibold border-b-2 border-[#dee2e6] px-3 py-2 text-left">Date</th>
              <th className="sticky top-0 bg-[#f8f9fa] font-semibold border-b-2 border-[#dee2e6] px-3 py-2 text-left">Description</th>
              <th className="sticky top-0 bg-[#f8f9fa] font-semibold border-b-2 border-[#dee2e6] px-3 py-2 text-right tabular-nums whitespace-nowrap">Amount</th>
              <th className="sticky top-0 bg-[#f8f9fa] font-semibold border-b-2 border-[#dee2e6] px-3 py-2 text-left"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="px-3 py-2 border-b border-[#f1f3f5] text-left whitespace-nowrap text-[#495057]">{fmtDate(r.transaction_date)}</td>
                <td className="px-3 py-2 border-b border-[#f1f3f5] text-left break-words">{r.description}</td>
                <td className={`px-3 py-2 border-b border-[#f1f3f5] text-right tabular-nums whitespace-nowrap ${r.is_credit ? 'text-[#166534]' : 'text-[#991b1b]'}`}>
                  {fmtAmount(r.amount)}
                </td>
                <td className="px-3 py-2 border-b border-[#f1f3f5] text-left">
                  <span className={`inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-[3px] tracking-[0.04em] ${
                    r.is_credit ? 'bg-[#f0fdf4] text-[#166534]' : 'bg-[#fef2f2] text-[#991b1b]'
                  }`}>
                    {r.is_credit ? 'CR' : 'DR'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function fmtDate(v) {
  if (!v) return '';
  // Backend may send ISO strings or already-formatted dates; be lenient.
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toISOString().slice(0, 10);
}

function fmtAmount(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v ?? '');
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
