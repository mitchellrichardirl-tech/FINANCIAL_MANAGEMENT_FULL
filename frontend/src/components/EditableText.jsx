import { useState } from 'react';

export default function EditableText({
  value,
  onChange,
  disabled = false,
  type = 'text',
  placeholder = '',
}) {
  const [localValue, setLocalValue] = useState(value || '');
  const [isEditing, setIsEditing] = useState(false);

  const handleBlur = () => {
    setIsEditing(false);
    if (localValue !== value) onChange(localValue);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur();
    } else if (e.key === 'Escape') {
      setLocalValue(value || '');
      e.target.blur();
    }
  };

  if (disabled) {
    return <span className="block py-[0.4em] px-[0.6em] text-[#888] text-[0.9em]">{value}</span>;
  }

  return (
    <input
      type={type}
      value={isEditing ? localValue : (value || '')}
      onChange={(e) => setLocalValue(e.target.value)}
      onFocus={() => setIsEditing(true)}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      className="py-[0.4em] px-[0.6em] border border-transparent rounded bg-transparent text-inherit text-[0.9em] w-full box-border transition-all duration-200 hover:bg-[rgba(100,108,255,0.1)] hover:border-[#646cff] focus:outline-none focus:bg-white focus:border-[#646cff]"
    />
  );
}
