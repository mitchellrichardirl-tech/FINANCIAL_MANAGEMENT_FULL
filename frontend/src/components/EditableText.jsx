import { useState } from 'react';
import './EditableText.css';

export default function EditableText({ 
  value, 
  onChange, 
  disabled = false,
  type = 'text',
  placeholder = ''
}) {
  const [localValue, setLocalValue] = useState(value || '');
  const [isEditing, setIsEditing] = useState(false);

  const handleBlur = () => {
    setIsEditing(false);
    if (localValue !== value) {
      onChange(localValue);
    }
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
    return <span className="editable-text-readonly">{value}</span>;
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
      className="editable-text-input"
    />
  );
}