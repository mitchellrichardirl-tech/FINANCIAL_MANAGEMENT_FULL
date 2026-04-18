/**
 * @file components/ColumnMismatchPanel.jsx
 * Inline error panel showing expected vs. found columns.
 *
 * Rendered when a statement-format operation fails with `INVALID_FORMAT`
 * and `missing_columns` in the details. Used by both the upload flow
 * and the format editor.
 */

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
    <div className="my-[16px] p-[16px_20px] bg-[#fef2f2] border border-[#fca5a5] border-l-[4px] border-l-[#dc2626] rounded-[6px]" role="alert">
      <div className="flex justify-between items-start mb-[12px]">
        <div>
          <strong className="text-[#991b1b] text-[15px]">Column mismatch</strong>
          <p className="m-[4px_0_0] text-[#7f1d1d] text-[14px]">{message}</p>
        </div>
        <button
          className="bg-none border-none text-[20px] text-[#991b1b] cursor-pointer p-[0_4px] leading-none"
          onClick={onDismiss}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>

      <div className="grid grid-cols-2 gap-[24px] my-[16px] p-[12px] bg-white rounded-[4px]">
        <div>
          <h4 className="m-[0_0_8px] text-[13px] uppercase tracking-[0.02em] text-[#6b7280]">
            Expected by <em>{formatName || 'this format'}</em>
          </h4>
          <ul className="list-none m-0 p-0 font-mono text-[13px]">
            {required.map((col) => (
              <li
                key={col}
                className={
                  missingSet.has(col)
                    ? 'p-[3px_8px] rounded-[3px] mb-[2px] text-[#991b1b] bg-[#fef2f2] font-semibold'
                    : 'p-[3px_8px] rounded-[3px] mb-[2px] text-[#166534] bg-[#f0fdf4]'
                }
              >
                {missingSet.has(col) ? '✗' : '✓'} {col}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="m-[0_0_8px] text-[13px] uppercase tracking-[0.02em] text-[#6b7280]">Found in file</h4>
          <ul className="list-none m-0 p-0 font-mono text-[13px]">
            {found.length === 0 && <li className="p-[3px_8px] rounded-[3px] mb-[2px] text-[#9ca3af] italic">(no columns)</li>}
            {found.map((col) => (
              <li
                key={col}
                className={
                  requiredSet.has(col)
                    ? 'p-[3px_8px] rounded-[3px] mb-[2px] text-[#166534] bg-[#f0fdf4]'
                    : 'p-[3px_8px] rounded-[3px] mb-[2px] text-[#6b7280]'
                }
              >
                {requiredSet.has(col) ? '✓' : '·'} {col}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="text-[13px] text-[#78350f] mb-[12px] [&_p]:m-[4px_0]">
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
        <div className="flex gap-[8px]">
          {actions.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              className="p-[6px_14px] text-[13px] bg-white border border-[#d1d5db] rounded-[4px] cursor-pointer hover:bg-[#f9fafb] hover:border-[#9ca3af]"
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
