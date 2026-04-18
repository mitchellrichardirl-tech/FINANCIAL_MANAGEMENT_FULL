import { useState } from 'react';

export default function ProcessingWarningsPanel({
  warnings,
  heading = '⚠️ Completed with warnings',
  context = 'operation',
}) {
  if (!warnings?.length) return null;
  const parsed = warnings.map(normalizeWarning);

  return (
    <div
      role="status"
      className="mt-4 border border-[#f0c36d] bg-[#fef9e7] rounded-md p-4"
    >
      <div>
        <strong className="text-[1.05rem]">{heading}</strong>
        <p className="mt-1 text-[#6b5a2a] text-[0.9rem]">
          {parsed.length === 1
            ? `One issue was encountered during the ${context}. The affected rows were skipped.`
            : `${parsed.length} issues were encountered during the ${context}. Affected rows were skipped.`}
        </p>
      </div>
      <div className="mt-3">
        {parsed.map((w, i) => (
          <WarningItem key={`${w.code}-${i}`} warning={w} first={i === 0} />
        ))}
      </div>
    </div>
  );
}

function WarningItem({ warning, first }) {
  const [expanded, setExpanded] = useState(true);
  const { code, message, details = {} } = warning;

  return (
    <div className={first ? '' : 'border-t border-[#f0e0b0] pt-3 mt-3'}>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        className="flex items-start gap-2 w-full text-left bg-none border-0 p-0 cursor-pointer font-inherit"
      >
        <span className="shrink-0 w-4 text-[#9b7b2a]">{expanded ? '▾' : '▸'}</span>
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

function WarningDetails({ code, details }) {
  if (code === 'DATES_UNPARSEABLE') {
    return (
      <>
        <dl className="flex flex-wrap gap-6 m-0 mb-3">
          <div className="flex flex-col gap-[0.15rem]">
            <dt className="text-xs uppercase text-[#8a7a4a] tracking-wider">Column</dt>
            <dd className="m-0"><code>{details.column}</code></dd>
          </div>
          <div className="flex flex-col gap-[0.15rem]">
            <dt className="text-xs uppercase text-[#8a7a4a] tracking-wider">Rows dropped</dt>
            <dd className="m-0">{details.dropped} of {details.total}</dd>
          </div>
          <div className="flex flex-col gap-[0.15rem]">
            <dt className="text-xs uppercase text-[#8a7a4a] tracking-wider">Parser used</dt>
            <dd className="m-0"><code>{details.format_used}</code></dd>
          </div>
        </dl>
        {details.sample_values?.length > 0 && (
          <div>
            <p className="m-0 mb-1.5 font-medium">Sample values that couldn&apos;t be parsed:</p>
            <ul className="m-0 pl-5">
              {[...new Set(details.sample_values)].slice(0, 5).map((v, i) => (
                <li key={i} className="mb-[0.15rem]">
                  <code className="bg-white border border-[#e8d9a8] py-[0.1rem] px-[0.35rem] rounded text-[0.85em]">
                    {v}
                  </code>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[#6b5a2a] text-[0.85rem]">
              💡 If these look like valid dates, the format&apos;s date pattern may need adjusting.
            </p>
          </div>
        )}
      </>
    );
  }
  if (!details || Object.keys(details).length === 0) return null;
  return (
    <pre className="bg-white border border-[#e8d9a8] p-3 rounded text-[0.8rem] overflow-x-auto">
      {JSON.stringify(details, null, 2)}
    </pre>
  );
}

function normalizeWarning(w) {
  if (w && typeof w === 'object') return w;
  if (typeof w === 'string') {
    try { return JSON.parse(w); } catch { /* fall through */ }
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
