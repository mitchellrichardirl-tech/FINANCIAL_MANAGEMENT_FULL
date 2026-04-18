export default function ColumnMismatchPanel({ error, onDismiss, actions = [] }) {
  const { message, formatName, missing, required, found } = error;
  const requiredSet = new Set(required);
  const missingSet = new Set(missing);
  const hasLookalike =
    missing.length === 1 &&
    found.some(
      (f) =>
        f.toLowerCase().includes(missing[0].toLowerCase()) ||
        missing[0].toLowerCase().includes(f.toLowerCase()),
    );

  return (
    <div
      role="alert"
      className="my-4 py-4 px-5 bg-[#fef2f2] border border-[#fca5a5] border-l-4 border-l-[#dc2626] rounded-md"
    >
      <div className="flex justify-between items-start mb-3">
        <div>
          <strong className="text-[#991b1b] text-[15px]">Column mismatch</strong>
          <p className="mt-1 text-[#7f1d1d] text-sm">{message}</p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="bg-none border-0 text-xl text-[#991b1b] cursor-pointer px-1 leading-none"
        >
          ×
        </button>
      </div>

      <div className="grid grid-cols-2 gap-6 my-4 p-3 bg-white rounded">
        <div>
          <h4 className="m-0 mb-2 text-[13px] uppercase tracking-wide text-[#6b7280]">
            Expected by <em>{formatName || 'this format'}</em>
          </h4>
          <ul className="list-none m-0 p-0 font-mono text-[13px]">
            {required.map((col) => {
              const isMissing = missingSet.has(col);
              return (
                <li
                  key={col}
                  className={`py-[3px] px-2 rounded-sm mb-0.5 ${isMissing ? 'text-[#991b1b] bg-[#fef2f2] font-semibold' : 'text-[#166534] bg-[#f0fdf4]'}`}
                >
                  {isMissing ? '✗' : '✓'} {col}
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <h4 className="m-0 mb-2 text-[13px] uppercase tracking-wide text-[#6b7280]">
            Found in file
          </h4>
          <ul className="list-none m-0 p-0 font-mono text-[13px]">
            {found.length === 0 && <li className="text-[#9ca3af] italic">(no columns)</li>}
            {found.map((col) => {
              const isPresent = requiredSet.has(col);
              return (
                <li
                  key={col}
                  className={`py-[3px] px-2 rounded-sm mb-0.5 ${isPresent ? 'text-[#166534] bg-[#f0fdf4]' : 'text-[#6b7280]'}`}
                >
                  {isPresent ? '✓' : '·'} {col}
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="text-[13px] text-[#78350f] mb-3 [&>p]:my-1">
        {hasLookalike && (
          <p>💡 The file has a column that looks similar — check if the header spelling matches exactly.</p>
        )}
        <p>This usually means either the wrong format was selected, or the file was exported differently than expected.</p>
      </div>

      {actions.length > 0 && (
        <div className="flex gap-2">
          {actions.map((a) => (
            <button
              key={a.label}
              type="button"
              onClick={a.onClick}
              className="py-1.5 px-3.5 text-[13px] bg-white border border-[#d1d5db] rounded cursor-pointer hover:bg-[#f9fafb] hover:border-[#9ca3af]"
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
