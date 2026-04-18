/**
 * @file components/ProcessingWarningsPanel.jsx
 * Expandable panel listing `ProcessingWarning` entries from the backend.
 *
 * Used after a successful import (some rows were dropped) and after a
 * format-editor preview (same warnings, different context). Warning
 * shapes are defined in `src/statements/base.py → ProcessingWarning`.
 */

import { useState } from 'react';

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
    <div className="mt-4 border border-[#f0c36d] bg-[#fef9e7] rounded-[6px] p-4" role="status">
      <div>
        <strong className="text-[1.05rem]">{heading}</strong>
        <p className="mt-1 mb-0 text-[#6b5a2a] text-[0.9rem]">
          {parsed.length === 1
            ? `One issue was encountered during the ${context}. The affected rows were skipped.`
            : `${parsed.length} issues were encountered during the ${context}. Affected rows were skipped.`}
        </p>
      </div>

      <div className="mt-3">
        {parsed.map((w, i) => (
          <WarningItem key={`${w.code}-${i}`} warning={w} isFirst={i === 0} />
        ))}
      </div>
    </div>
  );
}

/**
 * Single expandable warning item.
 * @param {{warning: ProcessingWarning, isFirst: boolean}} props
 */
function WarningItem({ warning, isFirst }) {
  const [expanded, setExpanded] = useState(true);
  const { code, message, details = {} } = warning;

  return (
    <div
      className={`pt-3 mt-3 ${isFirst ? 'border-t-0 mt-0 pt-0' : 'border-t border-[#f0e0b0]'}`}
    >
      <button
        type="button"
        className="flex items-start gap-2 w-full text-left bg-none border-none p-0 cursor-pointer font-[inherit]"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="shrink-0 w-[1em] text-[#9b7b2a]">{expanded ? '▾' : '▸'}</span>
        <span className="font-medium">{message}</span>
      </button>

      {expanded && (
        <div className="mt-3 ml-6 text-[0.9rem]">
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
          <dl className="flex flex-wrap gap-6 m-[0_0_0.75rem]">
            <div className="flex flex-col gap-[0.15rem]">
              <dt className="text-[0.75rem] uppercase text-[#8a7a4a] tracking-[0.03em]">Column</dt>
              <dd className="m-0"><code>{details.column}</code></dd>
            </div>
            <div className="flex flex-col gap-[0.15rem]">
              <dt className="text-[0.75rem] uppercase text-[#8a7a4a] tracking-[0.03em]">Rows dropped</dt>
              <dd className="m-0">{details.dropped} of {details.total}</dd>
            </div>
            <div className="flex flex-col gap-[0.15rem]">
              <dt className="text-[0.75rem] uppercase text-[#8a7a4a] tracking-[0.03em]">Parser used</dt>
              <dd className="m-0"><code>{details.format_used}</code></dd>
            </div>
          </dl>

          {details.sample_values?.length > 0 && (
            <div>
              <p className="m-[0_0_0.35rem] font-medium">Sample values that couldn&apos;t be parsed:</p>
              <ul className="m-0 pl-5">
                {[...new Set(details.sample_values)].slice(0, 5).map((v, i) => (
                  <li key={i} className="mb-[0.15rem]"><code className="bg-white border border-[#e8d9a8] p-[0.1rem_0.35rem] rounded-[3px] text-[0.85em]">{v}</code></li>
                ))}
              </ul>
              <p className="mt-3 mb-0 text-[#6b5a2a] text-[0.85rem]">
                💡 If these look like valid dates, the format&apos;s date pattern
                may need adjusting.
              </p>
            </div>
          )}
        </>
      );

    default:
      if (!details || Object.keys(details).length === 0) return null;
      return <pre className="bg-white border border-[#e8d9a8] p-3 rounded-[4px] text-[0.8rem] overflow-x-auto">{JSON.stringify(details, null, 2)}</pre>;
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
