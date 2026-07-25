/**
 * @file components/ColumnMismatchPanel.jsx
 * Inline error panel showing expected vs. found columns.
 *
 * Rendered when a statement-format operation fails with `INVALID_FORMAT`
 * and `missing_columns` in the details. Used by both the upload flow
 * and the format editor.
 */
/* ── Column-list item states ───────────────────────────────────────── */
const LI_BASE    = 'mb-0.5 rounded-[3px] px-2 py-[3px]';
const LI_PRESENT = `${LI_BASE} bg-green-50 text-green-800`;
const LI_MISSING = `${LI_BASE} bg-red-50 font-semibold text-red-800`;
const LI_EXTRA   = `${LI_BASE} text-gray-500`;
const LI_EMPTY   = `${LI_BASE} italic text-gray-400`;
const H4 = 'mb-2 text-[13px] uppercase tracking-[0.02em] text-gray-500';
const UL = 'font-mono text-[13px]';
/**
 * @typedef {Object} ColumnMismatch
 * @property {string}   message     - User-facing summary.
 * @property {string}   formatName  - Display name of the format that was tried.
 * @property {string[]} missing     - Required columns not found in the file.
 * @property {string[]} required    - All columns the format expects.
 * @property {string[]} found       - All columns actually present in the file.
 */
/**
 * @typedef {Object} MismatchAction
 * @property {string}     label   - Button text.
 * @property {() => void} onClick - Handler.
 */
/**
 * Inline column-mismatch error panel.
 *
 * @component
 * @param {Object} props
 * @param {ColumnMismatch}     props.error
 * @param {() => void}         props.onDismiss - Close the panel.
 * @param {MismatchAction[]}   [props.actions] - Recovery actions to offer.
 *        Defaults to none; callers supply context-appropriate buttons
 *        (e.g. "Try a different account" on the upload page vs.
 *        "Back to column mapping" in the format editor).
 */
export default function ColumnMismatchPanel({ error, onDismiss, actions = [] }) {
  const { message, formatName, missing, required, found } = error;
  const requiredSet = new Set(required);
  const missingSet = new Set(missing);
  // Heuristic: if exactly one column is missing and a near-match exists
  // in the file, hint that it's probably a spelling difference.
  const hasLookalike =
    missing.length === 1 &&
    found.some(
      (f) =>
        f.toLowerCase().includes(missing[0].toLowerCase()) ||
        missing[0].toLowerCase().includes(f.toLowerCase()),
    );
  return (
    <div
      className="my-4 rounded-md border border-red-300 border-l-4 border-l-red-600 bg-red-50 px-5 py-4"
      role="alert"
    >
      <div className="mb-3 flex items-start justify-between">
        <div>
          <strong className="text-[15px] text-red-800">Column mismatch</strong>
          <p className="mt-1 text-sm text-red-900">{message}</p>
        </div>
        <button
          className="cursor-pointer px-1 text-xl leading-none text-red-800"
          onClick={onDismiss}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
      <div className="my-4 grid grid-cols-1 gap-6 rounded bg-white p-3 sm:grid-cols-2">
        <div>
          <h4 className={H4}>
            Expected by <em>{formatName || 'this format'}</em>
          </h4>
          <ul className={UL}>
            {required.map((col) => (
              <li key={col} className={missingSet.has(col) ? LI_MISSING : LI_PRESENT}>
                {missingSet.has(col) ? '✗' : '✓'} {col}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className={H4}>Found in file</h4>
          <ul className={UL}>
            {found.length === 0 && <li className={LI_EMPTY}>(no columns)</li>}
            {found.map((col) => (
              <li key={col} className={requiredSet.has(col) ? LI_PRESENT : LI_EXTRA}>
                {requiredSet.has(col) ? '✓' : '·'} {col}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {/* space-y-1 replaces the collapsed `.cmp-hint p { margin: 4px 0 }` */}
      <div className="mb-3 space-y-1 text-[13px] text-amber-900">
        {hasLookalike && (
          <p>
            💡 The file has a column that looks similar — check if the header spelling
            matches exactly.
          </p>
        )}
        <p>
          This usually means either the wrong format was selected, or the file was
          exported differently than expected.
        </p>
      </div>
      {actions.length > 0 && (
        <div className="flex gap-2">
          {actions.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              className="cursor-pointer rounded border border-gray-300 bg-white px-3.5 py-1.5 text-[13px] hover:border-gray-400 hover:bg-gray-50"
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}