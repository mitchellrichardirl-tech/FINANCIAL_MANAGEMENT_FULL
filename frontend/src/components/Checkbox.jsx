/**
 * @file Checkbox.jsx
 * Styled controlled checkbox with an optional inline text label.
 */

export default function Checkbox({ checked, onChange, disabled = false, label = '' }) {
  return (
    <label className="inline-flex items-center cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="w-[18px] h-[18px] cursor-pointer m-0 disabled:cursor-not-allowed disabled:opacity-50"
      />
      {label && <span className="ml-2 text-[0.9em]">{label}</span>}
    </label>
  );
}