/**
 * @file components/ProcessingWarningsPanel.jsx
 * Expandable panel listing `ProcessingWarning` entries from the backend.
 *
 * Used after a successful import (some rows were dropped) and after a
 * format-editor preview (same warnings, different context). Warning
 * shapes are defined in `src/statements/base.py → ProcessingWarning`.
 */
import { useState } from 'react';
/* Reused class strings */
const CODE_CHIP =
  'rounded-[3px] border border-[#e8d9a8] bg-white px-1.5 py-0.5 text-[0.85em]';
const DT = 'text-xs uppercase tracking-[0.03em] text-[#8a7a4a]';
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
    <div
      className="mt-4 rounded-md border border-[#f0c36d] bg-[#fef9e7] p-4"
      role="status"
    >
      <div>
        <strong className="text-[1.05rem]">{heading}</strong>
        <p className="mt-1 text-sm text-[#6b5a2a]">
          {parsed.length === 1
            ? `One issue was encountered during the ${context}. The affected rows were skipped.`
            : `${parsed.length} issues were encountered during the ${context}. Affected rows were skipped.`}
        </p>
      </div>
      <div className="mt-3">
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
    <div
      /* `first:` resets replace the old `.pwp-item:first-child` rule */
      className="mt-3 border-t border-[#f0e0b0] pt-3 first:mt-0 first:border-t-0 first:pt-0"
      data-warning-code={code?.toLowerCase() || 'unknown'}
    >
      <button
        type="button"
        className="flex w-full cursor-pointer items-start gap-2 text-left"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="w-[1em] shrink-0 text-[#9b7b2a]">
          {expanded ? '▾' : '▸'}
        </span>
        <span className="font-medium">{message}</span>
      </button>
      {expanded && (
        <div className="mt-3 ml-6 text-sm">
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
          <dl className="mb-3 flex flex-wrap gap-6">
            <div className="flex flex-col gap-0.5">
              <dt className={DT}>Column</dt>
              <dd><code>{details.column}</code></dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className={DT}>Rows dropped</dt>
              <dd>{details.dropped} of {details.total}</dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className={DT}>Parser used</dt>
              <dd><code>{details.format_used}</code></dd>
            </div>
          </dl>
          {details.sample_values?.length > 0 && (
            <div>
              <p className="mb-1.5 font-medium">
                Sample values that couldn&apos;t be parsed:
              </p>
              {/* list-disc + pl-5 restore what Preflight strips */}
              <ul className="list-disc pl-5">
                {[...new Set(details.sample_values)].slice(0, 5).map((v, i) => (
                  <li key={i} className="mb-0.5">
                    <code className={CODE_CHIP}>{v}</code>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[0.85rem] text-[#6b5a2a]">
                💡 If these look like valid dates, the format&apos;s date pattern
                may need adjusting.
              </p>
            </div>
          )}
        </>
      );
    default:
      if (!details || Object.keys(details).length === 0) return null;
      return (
        <pre className="overflow-x-auto rounded border border-[#e8d9a8] bg-white p-3 text-[0.8rem]">
          {JSON.stringify(details, null, 2)}
        </pre>
      );
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