/**
 * @file NumberInput.jsx
 * Styled controlled numeric input that emits a `number` (or `null` when
 * cleared) instead of a string.
 */

export default function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  disabled = false,
  id,
}) {
  const handleChange = (e) => {
    const raw = e.target.value;
    if (raw === '') {
      onChange(null);
      return;
    }
    const n = Number(raw);
    if (Number.isNaN(n)) return; // ignore unparsable intermediate states
    onChange(n);
  };

  return (
    <input
      id={id}
      type="number"
      className="w-full box-border py-2 px-2.5 text-sm border border-border-input rounded bg-white text-[#212529] focus:outline-none focus:border-[#4a90e2] focus:shadow-[0_0_0_2px_rgba(74,144,226,0.2)] disabled:bg-[#f1f3f5] disabled:text-[#868e96] disabled:cursor-not-allowed"
      value={value ?? ''}
      onChange={handleChange}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
    />
  );
}