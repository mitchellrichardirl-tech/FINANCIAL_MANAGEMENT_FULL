/**
 * @file components/ColumnMismatchPanel.jsx
 * Inline error panel showing expected vs. found columns.
 *
 * Rendered when a statement-format operation fails with `INVALID_FORMAT`
 * and `missing_columns` in the details. Used by both the upload flow
 * and the format editor.
 */

import './ColumnMismatchPanel.css';

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
    <div className="column-mismatch-panel" role="alert">
      <div className="cmp-header">
        <div>
          <strong>Column mismatch</strong>
          <p className="cmp-message">{message}</p>
        </div>
        <button className="cmp-close" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      </div>

      <div className="cmp-comparison">
        <div className="cmp-column">
          <h4>
            Expected by <em>{formatName || 'this format'}</em>
          </h4>
          <ul>
            {required.map((col) => (
              <li key={col} className={missingSet.has(col) ? 'cmp-missing' : 'cmp-present'}>
                {missingSet.has(col) ? '✗' : '✓'} {col}
              </li>
            ))}
          </ul>
        </div>

        <div className="cmp-column">
          <h4>Found in file</h4>
          <ul>
            {found.length === 0 && <li className="cmp-empty">(no columns)</li>}
            {found.map((col) => (
              <li key={col} className={requiredSet.has(col) ? 'cmp-present' : 'cmp-extra'}>
                {requiredSet.has(col) ? '✓' : '·'} {col}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="cmp-hint">
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
        <div className="cmp-actions">
          {actions.map((a) => (
            <button key={a.label} onClick={a.onClick} className="cmp-btn-secondary">
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}