import { useState } from 'react';

export default function ChipInput({
  value = [],
  onChange,
  placeholder = 'Add…',
  disabled = false,
  allowDuplicates = false,
}) {
  const [draft, setDraft] = useState('');

  const commit = () => {
    const v = draft.trim();
    if (!v) return;
    if (!allowDuplicates && value.includes(v)) {
      setDraft('');
      return;
    }
    onChange([...value, v]);
    setDraft('');
  };

  const removeAt = (idx) => onChange(value.filter((_, i) => i !== idx));

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Backspace' && draft === '' && value.length > 0) {
      removeAt(value.length - 1);
    }
  };

  return (
    <div
      className={`flex flex-wrap items-center gap-[6px] py-[6px] px-2 border border-[#ced4da] rounded bg-white min-h-[38px] box-border focus-within:border-[#4a90e2] focus-within:shadow-[0_0_0_2px_rgba(74,144,226,0.2)] ${disabled ? 'bg-[#f1f3f5]' : ''}`}
    >
      {value.map((chip, i) => (
        <span
          key={`${chip}-${i}`}
          className="inline-flex items-center gap-1 bg-[#e7f3ff] text-[#0b5ed7] rounded-xl py-[2px] pr-[6px] pl-[10px] text-[13px]"
        >
          {chip}
          <button
            type="button"
            onClick={() => removeAt(i)}
            disabled={disabled}
            aria-label={`Remove ${chip}`}
            className="border-0 bg-transparent text-current cursor-pointer text-[15px] leading-none px-[2px] disabled:cursor-not-allowed"
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commit}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 min-w-[80px] border-0 outline-none text-sm py-1 px-[2px] bg-transparent"
      />
    </div>
  );
}
