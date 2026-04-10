/**
 * @file editor/Stepper.jsx
 * Horizontal step indicator. Visual only — navigation is delegated to
 * the `onStepClick` callback so the parent can enforce "no jumping past
 * the furthest step reached".
 */

import './Stepper.css';

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
    <ol className="stepper">
      {labels.map((label, i) => {
        const state =
          i < current ? 'done' : i === current ? 'current' : 'pending';
        const clickable = i <= maxReachable && i !== current;

        return (
          <li key={label} className={`stepper__item stepper__item--${state}`}>
            <button
              type="button"
              className="stepper__btn"
              onClick={() => clickable && onStepClick(i)}
              disabled={!clickable}
              aria-current={i === current ? 'step' : undefined}
            >
              <span className="stepper__index">
                {state === 'done' ? '✓' : i + 1}
              </span>
              <span className="stepper__label">{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}