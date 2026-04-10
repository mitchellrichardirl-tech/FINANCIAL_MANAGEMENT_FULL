/**
 * @file editor/ParsedPreviewTable.jsx
 * Compact read-only table of `previewFormat()` output rows. Shows just
 * enough to verify the mapping worked: date parsed, amount has the right
 * sign, description came through.
 */

import './ParsedPreviewTable.css';

/**
 * @component
 * @param {Object} props
 * @param {Object[]} props.rows  - `preview_rows` from the preview endpoint.
 * @param {number}   props.total - `total_parsed` (rows may be a capped subset).
 */
export default function ParsedPreviewTable({ rows, total }) {
  if (!rows?.length) {
    return (
      <div className="ppt-empty">
        No transactions were produced. Check the column mapping and any exclude
        patterns.
      </div>
    );
  }

  const capped = total > rows.length;

  return (
    <div className="ppt">
      <div className="ppt__summary">
        <strong>{total}</strong> transaction{total === 1 ? '' : 's'} parsed
        {capped && <> — showing the first {rows.length}</>}.
      </div>

      <div className="ppt__scroll">
        <table className="ppt__table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th className="ppt__num">Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="ppt__date">{fmtDate(r.transaction_date)}</td>
                <td className="ppt__desc">{r.description}</td>
                <td className={`ppt__num ${r.is_credit ? 'ppt__credit' : 'ppt__debit'}`}>
                  {fmtAmount(r.amount)}
                </td>
                <td>
                  <span className={`ppt__badge ${r.is_credit ? 'ppt__badge--cr' : 'ppt__badge--dr'}`}>
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