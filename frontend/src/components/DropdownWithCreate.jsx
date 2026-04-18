/**
 * @file DropdownWithCreate.jsx
 * {@link Dropdown} variant that appends a "Create New…" row which
 * triggers a callback instead of selecting a value — used to open a
 * creation modal (e.g. `CreateCategoryModal`) inline from a picker.
 */

import Dropdown from './Dropdown';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('DropdownWithCreate');

/**
 * Dropdown with an appended "create new" action row.
 *
 * Wraps {@link Dropdown} and, when `onCreateNew` is provided, injects a
 * synthetic option with the sentinel value `'__CREATE_NEW__'` at the end
 * of the list. Selecting that row invokes `onCreateNew()` and does
 * **not** call `onChange`, so the current selection is preserved while
 * the caller opens a modal / prompt.
 *
 * All {@link Dropdown} props are accepted and forwarded.
 *
 * @component
 * @param {Object} props
 * @param {string|number|null|undefined} props.value - See {@link Dropdown}.
 * @param {(value: string|null) => void} props.onChange
 *        Called when a *real* option is selected. Not called for the
 *        create row.
 * @param {Object[]} [props.options=[]] - See {@link Dropdown}.
 * @param {boolean} [props.disabled=false]
 *        Disables the control. Ignored (control stays enabled) when
 *        `onCreateNew` is provided, so the create action remains
 *        reachable even if there are no selectable options yet.
 * @param {string} [props.placeholder='Select...'] - See {@link Dropdown}.
 * @param {string} [props.valueKey='id'] - See {@link Dropdown}.
 * @param {string} [props.labelKey='name'] - See {@link Dropdown}.
 * @param {boolean} [props.includeEmpty=false] - See {@link Dropdown}.
 * @param {string} [props.emptyLabel='Please Select'] - See {@link Dropdown}.
 * @param {?() => void} [props.onCreateNew=null]
 *        Invoked when the user picks the create row. When `null`, no
 *        create row is added and this behaves exactly like {@link Dropdown}.
 * @param {string} [props.createLabel='Create New...']
 *        Label for the injected create row.
 * @returns {JSX.Element}
 *
 * @example
 * <DropdownWithCreate
 *   value={txn.party_id}
 *   options={parties}
 *   onChange={(id) => updateTxn(txn.id, { party_id: id })}
 *   onCreateNew={() => setShowCreatePartyModal(true)}
 *   createLabel="＋ New party…"
 * />
 */
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
  createLabel = 'Create New...'
}) {
  const handleDropdownChange = (newValue) => {
    logger.debug('DropdownWithCreate: handleDropdownChange called with:', newValue);

    if (newValue === '__CREATE_NEW__') {
      logger.debug('DropdownWithCreate: Create new selected');
      if (onCreateNew) {
        onCreateNew();
      }
    } else {
      onChange(newValue);
    }
  };

  // Add create option to the list
  const optionsWithCreate = onCreateNew ? [
    ...options,
    { [valueKey]: '__CREATE_NEW__', [labelKey]: createLabel }
  ] : options;

  return (
    <div className="w-full">
      <Dropdown
        value={value}
        onChange={handleDropdownChange}
        options={optionsWithCreate}
        disabled={disabled && !onCreateNew} // Only disable if no create option
        placeholder={placeholder}
        valueKey={valueKey}
        labelKey={labelKey}
        includeEmpty={includeEmpty}
        emptyLabel={emptyLabel}
      />
    </div>
  );
}