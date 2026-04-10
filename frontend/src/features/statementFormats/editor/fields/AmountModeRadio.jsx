/**
 * @file editor/fields/AmountModeRadio.jsx
 * Three-way radio for the amount configuration strategy, with a short
 * description per option so the user can self-diagnose which shape
 * their bank uses.
 */

import { AMOUNT_MODE, AMOUNT_MODE_LABELS } from '../../constants';
import './AmountModeRadio.css';

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
    <fieldset className="amount-mode-radio">
      <legend className="amount-mode-radio__legend">
        How does this bank report amounts?
      </legend>
      {Object.values(AMOUNT_MODE).map((mode) => (
        <label
          key={mode}
          className={`amount-mode-radio__option ${
            value === mode ? 'amount-mode-radio__option--selected' : ''
          }`}
        >
          <input
            type="radio"
            name="amountMode"
            value={mode}
            checked={value === mode}
            onChange={() => onChange(mode)}
          />
          <div>
            <div className="amount-mode-radio__label">
              {AMOUNT_MODE_LABELS[mode]}
            </div>
            <div className="amount-mode-radio__desc">{DESCRIPTIONS[mode]}</div>
          </div>
        </label>
      ))}
    </fieldset>
  );
}