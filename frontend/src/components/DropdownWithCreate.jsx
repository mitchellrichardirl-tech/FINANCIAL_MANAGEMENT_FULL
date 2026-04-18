import Dropdown from './Dropdown';
import { createLogger } from '@/lib/logger';

const logger = createLogger('DropdownWithCreate');

export default function DropdownWithCreate({
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = 'Select...',
  valueKey = 'id',
  labelKey = 'name',
  includeEmpty = false,
  emptyLabel = 'Please Select',
  onCreateNew = null,
  createLabel = 'Create New...',
  className = '',
}) {
  const handleDropdownChange = (newValue) => {
    logger.debug('DropdownWithCreate: handleDropdownChange called with:', newValue);
    if (newValue === '__CREATE_NEW__') {
      if (onCreateNew) onCreateNew();
    } else {
      onChange(newValue);
    }
  };

  const optionsWithCreate = onCreateNew
    ? [...options, { [valueKey]: '__CREATE_NEW__', [labelKey]: createLabel }]
    : options;

  return (
    <div className={`w-full ${className}`}>
      <Dropdown
        value={value}
        onChange={handleDropdownChange}
        options={optionsWithCreate}
        disabled={disabled && !onCreateNew}
        placeholder={placeholder}
        valueKey={valueKey}
        labelKey={labelKey}
        includeEmpty={includeEmpty}
        emptyLabel={emptyLabel}
      />
    </div>
  );
}
