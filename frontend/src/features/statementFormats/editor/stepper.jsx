/**
 * @file editor/Stepper.jsx
 * Horizontal step indicator. Visual only — navigation is delegated to
 * the `onStepClick` callback so the parent can enforce "no jumping past
 * the furthest step reached".
 */

/**
 * @component
 * @param {Object} props
 * @param {string[]} props.labels
 * @param {number} props.current         - Active step index.
 * @param {number} props.maxReachable    - Furthest index the user may click.
 * @param {(index: number) => void} props.onStepClick
 */
export default function Stepper({ labels, current, maxReachable, onStepClick }) {
  return (
    <ol className="flex list-none m-0 mb-6 p-0 gap-2">
      {labels.map((label, i) => {
        const state =
          i < current ? 'done' : i === current ? 'current' : 'pending';
        const clickable = i <= maxReachable && i !== current;

        const isDone = state === 'done';
        const isCurrent = state === 'current';

        // Index circle classes
        const indexClasses = [
          'w-7 h-7 rounded-full inline-flex items-center justify-center text-[13px] font-semibold',
          isDone
            ? 'bg-success border-2 border-success text-white'
            : isCurrent
              ? 'bg-white border-2 border-primary text-primary'
              : 'bg-white border-2 border-border-input text-[#6c757d]',
        ].join(' ');

        // Label classes
        const labelClasses = [
          'text-xs text-center',
          isCurrent ? 'text-[#212529] font-semibold' : 'text-[#6c757d]',
        ].join(' ');

        return (
          <li key={label} className="flex-1 relative">
            {/* connector line */}
            {i < labels.length - 1 && (
              <span
                className={`absolute top-[14px] h-0.5 z-0 ${
                  isDone ? 'bg-success' : 'bg-[#dee2e6]'
                }`}
                style={{ left: 'calc(50% + 18px)', right: 'calc(-50% + 18px)' }}
              />
            )}
            <button
              type="button"
              className={`relative z-[1] flex flex-col items-center gap-1.5 w-full bg-transparent border-none p-0 font-inherit ${
                clickable ? 'cursor-pointer' : 'cursor-default'
              }`}
              onClick={() => clickable && onStepClick(i)}
              disabled={!clickable}
              aria-current={i === current ? 'step' : undefined}
            >
              <span className={indexClasses}>
                {state === 'done' ? '\u2713' : i + 1}
              </span>
              <span className={labelClasses}>{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
