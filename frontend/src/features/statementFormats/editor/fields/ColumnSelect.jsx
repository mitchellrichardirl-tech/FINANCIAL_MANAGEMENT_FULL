/**
 * @file editor/fields/ColumnSelect.jsx
 * Column picker backed by the sample file's headers. Falls back to a
 * free-text input when no sample is loaded so the editor remains usable
 * in "no file" mode.
 *
 * When the current value exists but isn't in the sample columns (e.g.
 * editing a format with a different sample file), it's shown as an
 * extra option labelled "(not in sample)" so the user can see what's
 * configured.
 */

import { useMemo } from 'react';
import Dropdown from '@/components/Dropdown';
import TextInput from '@/components/TextInput';

/**
 * @component
 * @param {Object}   props
 * @param {string|null} props.value
 * @param {(v: string|null) => void} props.onChange
 * @param {string[]} props.columns          - From `editor.sampleColumns`.
 * @param {Object}   [props.columnTypes={}] - From `editor.sampleColumnTypes`.
 * @param {boolean}  [props.required=true]  - When false, adds a clearable "None" option.
 * @param {string}   [props.placeholder='Select column…']
 */
export default function ColumnSelect({
  value,
  onChange,
  columns,
  columnTypes = {},
  required = true,
  placeholder = 'Select column…',
}) {
  // No sample loaded — fall back to free text.
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

    // Preserve the current value even if the sample doesn't contain it
    // (editing with a different sample file).
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