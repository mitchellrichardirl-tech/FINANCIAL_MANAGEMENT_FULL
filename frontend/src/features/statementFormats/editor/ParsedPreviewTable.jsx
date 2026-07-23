/**
 * @file editor/ParsedPreviewTable.jsx
 * Compact read-only table of `previewFormat()` output rows. Shows just
 * enough to verify the mapping worked: date parsed, amount has the right
 * sign, description came through.
 */

/* Cell bases deliberately omit text-align — each cell sets its own, so
   there's no same-property utility conflict to reason about. */
const TH = 'sticky top-0 border-b-2 border-gray-300 bg-gray-50 px-3 py-2 font-semibold';
const TD = 'border-b border-gray-100 px-3 py-2';
const NUM = 'text-right tabular-nums whitespace-nowrap';
/**
 * @component
 * @param {Object} props
 * @param {Object[]} props.rows  - `preview_rows` from the preview endpoint.
 * @param {number}   props.total - `total_parsed` (rows may be a capped subset).
 */
export default function ParsedPreviewTable({ rows, total }) {
  if (!rows?.length) {
    return (
      <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-muted">
        No transactions were produced. Check the column mapping and any exclude
        patterns.
      </div>
    );
  }
  const capped = total > rows.length;
  return (
    <div>
      <div className="mb-2.5 text-sm text-gray-700">
        <strong>{total}</strong> transaction{total === 1 ? '' : 's'} parsed
        {capped && <> — showing the first {rows.length}</>}.
      </div>
      <div className="max-h-[45vh] overflow-auto rounded border border-gray-300">
        <table className="w-full bg-white text-[13px]">
          <thead>
            <tr>
              <th className={`${TH} text-left`}>Date</th>
              <th className={`${TH} text-left`}>Description</th>
              <th className={`${TH} ${NUM}`}>Amount</th>
              <th className={`${TH} text-left`}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className={`${TD} text-left whitespace-nowrap text-gray-600`}>
                  {fmtDate(r.transaction_date)}
                </td>
                <td className={`${TD} text-left break-words`}>{r.description}</td>
                <td
                  className={`${TD} ${NUM} ${r.is_credit ? 'text-green-800' : 'text-red-800'}`}
                >
                  {fmtAmount(r.amount)}
                </td>
                <td className={`${TD} text-left`}>
                  <span
                    className={`inline-block rounded-[3px] px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.04em] ${
                      r.is_credit
                        ? 'bg-green-50 text-green-800'
                        : 'bg-red-50 text-red-800'
                    }`}
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
  // Backend may send ISO strings or already-formatted dates; be lenient.
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toISOString().slice(0, 10);
}
function fmtAmount(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v ?? '');
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}