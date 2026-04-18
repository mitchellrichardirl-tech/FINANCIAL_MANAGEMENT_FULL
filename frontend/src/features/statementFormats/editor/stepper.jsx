export default function Stepper({ labels, current, maxReachable, onStepClick }) {
  return (
    <ol className="flex list-none m-0 mb-6 p-0 gap-2">
      {labels.map((label, i) => {
        const state = i < current ? 'done' : i === current ? 'current' : 'pending';
        const clickable = i <= maxReachable && i !== current;
        const isLast = i === labels.length - 1;

        let indexCls =
          'w-7 h-7 rounded-full inline-flex items-center justify-center text-[13px] font-semibold border-2';
        if (state === 'done') {
          indexCls += ' bg-[#28a745] border-[#28a745] text-white';
        } else if (state === 'current') {
          indexCls += ' bg-white border-[#007bff] text-[#007bff]';
        } else {
          indexCls += ' bg-white border-[#ced4da] text-[#6c757d]';
        }

        let labelCls = 'text-xs text-center';
        labelCls += state === 'current'
          ? ' text-[#212529] font-semibold'
          : ' text-[#6c757d]';

        const connectorBg = state === 'done' ? 'bg-[#28a745]' : 'bg-[#dee2e6]';

        return (
          <li key={label} className="flex-1 relative">
            {!isLast && (
              <span
                aria-hidden
                className={`absolute top-[14px] h-0.5 z-0 ${connectorBg}`}
                style={{ left: 'calc(50% + 18px)', right: 'calc(-50% + 18px)' }}
              />
            )}
            <button
              type="button"
              onClick={() => clickable && onStepClick(i)}
              disabled={!clickable}
              aria-current={i === current ? 'step' : undefined}
              className="relative z-[1] flex flex-col items-center gap-1.5 w-full bg-none border-0 p-0 cursor-pointer font-inherit disabled:cursor-default"
            >
              <span className={indexCls}>
                {state === 'done' ? '✓' : i + 1}
              </span>
              <span className={labelCls}>{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
