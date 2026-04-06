/**
 * @file components/ProcessingWarningsPanel.jsx
 * Expandable panel listing `ProcessingWarning` entries from the backend.
 *
 * Used after a successful import (some rows were dropped) and after a
 * format-editor preview (same warnings, different context). Warning
 * shapes are defined in `src/statements/base.py → ProcessingWarning`.
 */

import { useState } from 'react';
import './ProcessingWarningsPanel.css';

/**
 * @typedef {Object} ProcessingWarning
 * @property {string} code    - Machine-readable warning code.
 * @property {string} message - Human-readable summary.
 * @property {Object} details - Code-specific extra fields.
 */

/**
 * @component
 * @param {Object} props
 * @param {Array<ProcessingWarning|string>} props.warnings
 *        Raw warnings array from the API. Strings are tolerated and
 *        normalized for robustness.
 * @param {string} [props.heading]
 *        Panel heading. Defaults to generic wording.
 * @param {string} [props.context]
 *        Short noun describing what was processed (e.g. "import",
 *        "preview"), used in the subheader.
 */
export default function ProcessingWarningsPanel({
  warnings,
  heading = '⚠️ Completed with warnings',
  context = 'operation',
}) {
  if (!warnings?.length) return null;

  const parsed = warnings.map(normalizeWarning);

  return (
    <div className="processing-warnings-panel" role="status">
      <div className="pwp-header">
        <strong>{heading}</strong>
        <p className="pwp-subheader">
          {parsed.length === 1
            ? `One issue was encountered during the ${context}. The affected rows were skipped.`
            : `${parsed.length} issues were encountered during the ${context}. Affected rows were skipped.`}
        </p>
      </div>

      <div className="pwp-items">
        {parsed.map((w, i) => (
          <WarningItem key={`${w.code}-${i}`} warning={w} />
        ))}
      </div>
    </div>
  );
}

/**
 * Single expandable warning item.
 * @param {{warning: ProcessingWarning}} props
 */
function WarningItem({ warning }) {
  const [expanded, setExpanded] = useState(true);
  const { code, message, details = {} } = warning;

  return (
    <div className={`pwp-item pwp-code-${code?.toLowerCase() || 'unknown'}`}>
      <button
        type="button"
        className="pwp-toggle"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="pwp-chevron">{expanded ? '▾' : '▸'}</span>
        <span className="pwp-message">{message}</span>
      </button>

      {expanded && (
        <div className="pwp-details">
          <WarningDetails code={code} details={details} />
        </div>
      )}
    </div>
  );
}

/**
 * Render details for a specific warning code.
 * Extend the switch as the backend emits new warning types.
 *
 * @param {{code: string, details: Object}} props
 */
function WarningDetails({ code, details }) {
  switch (code) {
    case 'DATES_UNPARSEABLE':
      return (
        <>
          <dl className="pwp-dl">
            <div>
              <dt>Column</dt>
              <dd><code>{details.column}</code></dd>
            </div>
            <div>
              <dt>Rows dropped</dt>
              <dd>{details.dropped} of {details.total}</dd>
            </div>
            <div>
              <dt>Parser used</dt>
              <dd><code>{details.format_used}</code></dd>
            </div>
          </dl>

          {details.sample_values?.length > 0 && (
            <div className="pwp-samples">
              <p className="pwp-samples-label">Sample values that couldn&apos;t be parsed:</p>
              <ul>
                {[...new Set(details.sample_values)].slice(0, 5).map((v, i) => (
                  <li key={i}><code>{v}</code></li>
                ))}
              </ul>
              <p className="pwp-hint">
                💡 If these look like valid dates, the format&apos;s date pattern
                may need adjusting.
              </p>
            </div>
          )}
        </>
      );

    default:
      if (!details || Object.keys(details).length === 0) return null;
      return <pre className="pwp-raw-details">{JSON.stringify(details, null, 2)}</pre>;
  }
}

/**
 * Normalize a warning to `{ code, message, details }`.
 * Handles objects, JSON strings, and (legacy) Python repr strings.
 *
 * @param {Object|string} w
 * @returns {ProcessingWarning}
 */
function normalizeWarning(w) {
  if (w && typeof w === 'object') return w;

  if (typeof w === 'string') {
    try {
      return JSON.parse(w);
    } catch { /* fall through */ }

    // Last-ditch: Python repr → JSON. Delete once the backend is confirmed
    // to always send proper dicts.
    try {
      const jsonish = w
        .replace(/\bNone\b/g, 'null')
        .replace(/\bTrue\b/g, 'true')
        .replace(/\bFalse\b/g, 'false')
        .replace(/'((?:[^'\\]|\\.)*)'/g, (_, inner) => `"${inner.replace(/"/g, '\\"')}"`);
      return JSON.parse(jsonish);
    } catch {
      return { code: 'UNKNOWN', message: w, details: {} };
    }
  }

  return { code: 'UNKNOWN', message: String(w), details: {} };
}