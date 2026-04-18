import { AMOUNT_MODE, AMOUNT_MODE_LABELS } from '../../constants';

const DESCRIPTIONS = {
  [AMOUNT_MODE.SPLIT]:
    'Two columns — one for credits (money in), one for debits (money out). Values are always positive.',
  [AMOUNT_MODE.SIGNED]:
    'One column where the sign indicates direction — negative values are debits, positive are credits.',
  [AMOUNT_MODE.INDICATOR]:
    'One amount column (always positive) plus a separate column that says "CR" or "DR".',
};

export default function AmountModeRadio({ value, onChange }) {
  return (
    <fieldset className="border-0 p-0 m-0 mb-5">
      <legend className="font-semibold text-[13px] text-[#333] p-0 mb-2.5">
        How does this bank report amounts?
      </legend>
      {Object.values(AMOUNT_MODE).map((mode) => {
        const selected = value === mode;
        return (
          <label
            key={mode}
            className={`flex items-start gap-2.5 py-3 px-3.5 border rounded mb-2 cursor-pointer transition-[border-color,background] duration-[120ms] hover:border-[#adb5bd] ${selected ? 'border-[#007bff] bg-[#f0f8ff]' : 'border-[#dee2e6]'}`}
          >
            <input
              type="radio"
              name="amountMode"
              value={mode}
              checked={selected}
              onChange={() => onChange(mode)}
              className="mt-[3px] shrink-0"
            />
            <div>
              <div className="font-medium text-sm">{AMOUNT_MODE_LABELS[mode]}</div>
              <div className="text-xs text-[#6c757d] mt-0.5">{DESCRIPTIONS[mode]}</div>
            </div>
          </label>
        );
      })}
    </fieldset>
  );
}
