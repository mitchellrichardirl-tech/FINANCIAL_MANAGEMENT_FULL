import './Checkbox.css';

export default function Checkbox({ checked, onChange, disabled = false, label = '' }) {
  return (
    <label className="checkbox-container">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="checkbox-input"
      />
      {label && <span className="checkbox-label">{label}</span>}
    </label>
  );
}