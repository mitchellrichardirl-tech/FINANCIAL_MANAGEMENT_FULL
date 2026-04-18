/**
 * @file editor/fields/AmountModeRadio.jsx
 * Three-way radio for the amount configuration strategy, with a short
 * description per option so the user can self-diagnose which shape
 * their bank uses.
 */

import { AMOUNT_MODE, AMOUNT_MODE_LABELS } from '../../constants';

const DESCRIPTIONS = {
  [AMOUNT_MODE.SPLIT]:
    'Two columns — one for credits (money in), one for debits (money out). Values are always positive.',
  [AMOUNT_MODE.SIGNED]:
    'One column where the sign indicates direction — negative values are debits, positive are credits.',
  [AMOUNT_MODE.INDICATOR]:
    'One amount column (always positive) plus a separate column that says "CR" or "DR".',
};

/**
 * @component
 * @param {Object} props
 * @param {string} props.value    - Current `AMOUNT_MODE`.
 * @param {(mode: string) => void} props.onChange
 */
export default function AmountModeRadio({ value, onChange }) {
  return (
    <fieldset className="border-none p-0 m-0 mb-5">
      <legend className="font-semibold text-[13px] text-text-dark p-0 mb-2.5">
        How does this bank report amounts?
      </legend>
      {Object.values(AMOUNT_MODE).map((mode) => (
        <label
          key={mode}
          className={`flex items-start gap-2.5 px-3.5 py-3 border rounded mb-2 cursor-pointer transition-[border-color,background-color] duration-[120ms] ${
            value === mode
              ? 'border-primary bg-[#f0f8ff]'
              : 'border-[#dee2e6] hover:border-[#adb5bd]'
          }`}
        >
          <input
            type="radio"
            name="amountMode"
            value={mode}
            checked={value === mode}
            onChange={() => onChange(mode)}
            className="mt-[3px] shrink-0"
          />
          <div>
            <div className="font-medium text-sm">
              {AMOUNT_MODE_LABELS[mode]}
            </div>
            <div className="text-xs text-[#6c757d] mt-0.5">{DESCRIPTIONS[mode]}</div>
          </div>
        </label>
      ))}
    </fieldset>
  );
}
