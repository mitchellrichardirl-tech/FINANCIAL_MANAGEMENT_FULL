/**
 * @file editor/Stepper.jsx
 * Horizontal step indicator. Visual only — navigation is delegated to
 * the `onStepClick` callback so the parent can enforce "no jumping past
 * the furthest step reached".
 */

/* Connector line between items. Geometry matches the 28px index circle:
   18px = half the circle (14px) + 4px breathing room; top-3.5 (14px)
   centres it on the circle. */
const CONNECTOR =
  "after:absolute after:top-3.5 after:left-[calc(50%+18px)] after:right-[calc(-50%+18px)] " +
  "after:h-0.5 after:z-0 after:content-['']";
const INDEX_BASE =
  'inline-flex h-7 w-7 items-center justify-center rounded-full border-2 ' +
  'text-[13px] font-semibold';
const INDEX_STATE = {
  done: 'border-green-800 bg-green-800 text-white',
  current: 'border-[#007bff] bg-white text-[#007bff]',
  pending: 'border-gray-300 bg-white text-muted',
};
const LABEL_STATE = {
  done: 'text-muted',
  current: 'font-semibold text-gray-900',
  pending: 'text-muted',
};
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
    <ol className="flex shrink-0 gap-2 mb-6">
      {labels.map((label, i) => {
        const state =
          i < current ? 'done' : i === current ? 'current' : 'pending';
        const clickable = i <= maxReachable && i !== current;
        const isLast = i === labels.length - 1;
        return (
          <li
            key={label}
            className={[
              'relative flex-1',
              // connector is suppressed on the last item
              isLast ? '' : CONNECTOR,
              isLast ? '' : state === 'done' ? 'after:bg-green-800' : 'after:bg-gray-300',
            ].join(' ')}
          >
            <button
              type="button"
              className="relative z-[1] flex w-full cursor-pointer flex-col items-center gap-1.5 disabled:cursor-default"
              onClick={() => clickable && onStepClick(i)}
              disabled={!clickable}
              aria-current={i === current ? 'step' : undefined}
            >
              <span className={`${INDEX_BASE} ${INDEX_STATE[state]}`}>
                {state === 'done' ? '✓' : i + 1}
              </span>
              <span className={`text-center text-xs ${LABEL_STATE[state]}`}>
                {label}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}