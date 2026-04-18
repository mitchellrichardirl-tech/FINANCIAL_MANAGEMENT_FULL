export default function ParsedPreviewTable({ rows, total }) {
  if (!rows?.length) {
    return (
      <div className="py-6 px-6 text-center text-[#6c757d] bg-[#f8f9fa] border border-dashed border-[#dee2e6] rounded-md">
        No transactions were produced. Check the column mapping and any exclude
        patterns.
      </div>
    );
  }

  const capped = total > rows.length;

  return (
    <div>
      <div className="text-sm mb-2.5 text-[#333]">
        <strong>{total}</strong> transaction{total === 1 ? '' : 's'} parsed
        {capped && <> — showing the first {rows.length}</>}.
      </div>
      <div className="max-h-[45vh] overflow-auto border border-[#dee2e6] rounded">
        <table className="w-full border-collapse text-[13px] bg-white">
          <thead>
            <tr>
              {['Date', 'Description', 'Amount', ''].map((h, i) => (
                <th
                  key={i}
                  className={`sticky top-0 bg-[#f8f9fa] font-semibold border-b-2 border-[#dee2e6] py-2 px-3 ${i === 2 ? 'text-right' : 'text-left'}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="py-2 px-3 border-b border-[#f1f3f5] whitespace-nowrap text-[#495057]">
                  {fmtDate(r.transaction_date)}
                </td>
                <td className="py-2 px-3 border-b border-[#f1f3f5] break-words">
                  {r.description}
                </td>
                <td
                  className={`py-2 px-3 border-b border-[#f1f3f5] text-right whitespace-nowrap tabular-nums ${r.is_credit ? 'text-[#166534]' : 'text-[#991b1b]'}`}
                >
                  {fmtAmount(r.amount)}
                </td>
                <td className="py-2 px-3 border-b border-[#f1f3f5]">
                  <span
                    className={`inline-block text-[10px] font-semibold py-0.5 px-1.5 rounded tracking-wide ${r.is_credit ? 'bg-[#f0fdf4] text-[#166534]' : 'bg-[#fef2f2] text-[#991b1b]'}`}
                  >
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
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toISOString().slice(0, 10);
}
function fmtAmount(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v ?? '');
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
