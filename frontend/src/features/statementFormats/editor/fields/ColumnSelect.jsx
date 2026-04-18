import { useMemo } from 'react';
import Dropdown from '@/components/Dropdown';
import TextInput from '@/components/TextInput';

export default function ColumnSelect({
  value,
  onChange,
  columns,
  columnTypes = {},
  required = true,
  placeholder = 'Select column…',
}) {
  if (!columns || columns.length === 0) {
    return (
      <TextInput
        value={value ?? ''}
        onChange={onChange}
        placeholder="Type column name…"
      />
    );
  }

  const options = useMemo(() => {
    const opts = columns.map((col) => ({
      value: col,
      label: columnTypes[col] ? `${col}  ·  ${columnTypes[col]}` : col,
    }));
    if (value && !columns.includes(value)) {
      opts.unshift({ value, label: `${value}  (not in sample)` });
    }
    return opts;
  }, [columns, columnTypes, value]);

  return (
    <Dropdown
      value={value}
      onChange={onChange}
      options={options}
      valueKey="value"
      labelKey="label"
      includeEmpty={!required}
      emptyLabel="None"
      placeholder={placeholder}
    />
  );
}
