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
    <fieldset className="m-0 mb-5 border-none p-0">
      <legend className="mb-2.5 p-0 text-[13px] font-semibold text-gray-700">
        How does this bank report amounts?
      </legend>

      {Object.values(AMOUNT_MODE).map((mode) => {
        const selected = value === mode;
        return (
          <label
            key={mode}
            className={`mb-2 flex cursor-pointer items-start gap-2.5 rounded border px-3.5 py-3 transition-colors duration-[120ms] ${
              selected
                ? 'border-blue-500 bg-[#f0f8ff]'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input
              type="radio"
              name="amountMode"
              value={mode}
              checked={selected}
              onChange={() => onChange(mode)}
              className="mt-0.5 shrink-0"
            />
            <div>
              <div className="text-sm font-medium">
                {AMOUNT_MODE_LABELS[mode]}
              </div>
              <div className="mt-0.5 text-xs text-gray-500">
                {DESCRIPTIONS[mode]}
              </div>
            </div>
          </label>
        );
      })}
    </fieldset>
  );
}