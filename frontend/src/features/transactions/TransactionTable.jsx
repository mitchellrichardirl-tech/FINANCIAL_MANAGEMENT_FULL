import { useState, useMemo } from 'react';
import TransactionRow from './TransactionRow';
import CreateCategoryModal from './CreateCategoryModal';
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('TransactionTable');
/* ── Header cells ──────────────────────────────────────────────────── */
const TH =
  'sticky top-0 z-[11] whitespace-nowrap border-b-2 border-gray-300 bg-gray-50 ' +
  'px-2 py-3 font-semibold text-gray-600';
const TH_SORT = `${TH} cursor-pointer select-none hover:bg-gray-200`;
/* ── Filter row ────────────────────────────────────────────────────── */
/** `top-11` = 44px = the header row's computed height. See note. */
const FILTER_TD =
  'sticky top-11 z-10 border-b-2 border-gray-300 bg-gray-50 px-2 py-1.5 align-middle';
const FILTER_INPUT =
  'w-full rounded border border-gray-300 px-2 py-1.5 text-[13px] ' +
  'placeholder:text-[#adb5bd] focus:border-[#80bdff] ' +
  'focus:shadow-[0_0_0_2px_rgba(0,123,255,0.25)] focus:outline-none';
const FILTER_SELECT = `${FILTER_INPUT} cursor-pointer bg-white`;
/**
 * Main transaction listing.
 * (full docblock unchanged)
 */
export default function TransactionTable({
  transactions,
  accounts,
  categories,
  subCategories,
  types,
  parties,
  onUpdate,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
  selectedTransactions,
  onSelectionChange,
  filters,
  onFilterChange,
  onRemapParty,
  onFindOrCreateParty,
  sortField,
  sortDir,
  onSortChange,
  onReceiptChange,
}) {
  // ── Modal state ───────────────────────────────────────────────────
  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentId: null,
    parentName: '',
    onSuccess: null,
  });
  /** Defensive coercion — callers sometimes pass `null` or `undefined`. */
  const transactionArray = Array.isArray(transactions) ? transactions : [];
  // ── Derived / memoised option lists (sorted & filtered) ───────────
  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );
  const filteredSubCategories = useMemo(() => {
    let filtered = [...subCategories];
    if (filters.category_id) {
      filtered = filtered.filter((sc) => sc.category_id === filters.category_id);
    }
    return filtered.sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, filters.category_id]);
  const filteredTypes = useMemo(() => {
    let filtered = [...types];
    if (filters.sub_category_id) {
      filtered = filtered.filter((t) => t.sub_category_id === filters.sub_category_id);
    } else if (filters.category_id) {
      const subCatIds = subCategories
        .filter((sc) => sc.category_id === filters.category_id)
        .map((sc) => sc.id);
      filtered = filtered.filter((t) => subCatIds.includes(t.sub_category_id));
    }
    return filtered.sort((a, b) => a.type.localeCompare(b.type));
  }, [types, subCategories, filters.sub_category_id, filters.category_id]);
  const filteredParties = useMemo(() => {
    let filtered = [...parties];
    if (filters.type_id) {
      filtered = filtered.filter((p) => p.type_id === filters.type_id);
    } else if (filters.sub_category_id) {
      const typeIds = types
        .filter((t) => t.sub_category_id === filters.sub_category_id)
        .map((t) => t.id);
      filtered = filtered.filter((p) => typeIds.includes(p.type_id));
    } else if (filters.category_id) {
      const subCatIds = subCategories
        .filter((sc) => sc.category_id === filters.category_id)
        .map((sc) => sc.id);
      const typeIds = types
        .filter((t) => subCatIds.includes(t.sub_category_id))
        .map((t) => t.id);
      filtered = filtered.filter((p) => typeIds.includes(p.type_id));
    }
    return filtered.sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, types, subCategories, filters.type_id, filters.sub_category_id, filters.category_id]);
  // ── Sorting ───────────────────────────────────────────────────────
  const handleSort = (field) => {
    const newDir = sortField === field && sortDir === 'asc' ? 'desc' : 'asc';
    onSortChange(field, newDir);
  };
  // ── Selection ─────────────────────────────────────────────────────
  const handleSelectAll = (checked) => {
    if (checked) {
      onSelectionChange(transactionArray.map((t) => t.id));
    } else {
      onSelectionChange([]);
    }
  };
  const handleRowSelection = (transactionId, checked) => {
    if (checked) {
      onSelectionChange([...selectedTransactions, transactionId]);
    } else {
      onSelectionChange(selectedTransactions.filter((id) => id !== transactionId));
    }
  };
  // ── Filtering ─────────────────────────────────────────────────────
  const handleFilterFieldChange = (field, value) => {
    logger.debug('Filter change:', field, value, 'Current filters:', filters);
    const newFilters = { ...filters };
    if (value === undefined || value === '' || value === null) {
      delete newFilters[field];
    } else {
      const idFields = ['account_id', 'party_id', 'category_id', 'sub_category_id', 'type_id'];
      if (idFields.includes(field)) {
        newFilters[field] = parseInt(value, 10);
      } else {
        newFilters[field] = value;
      }
    }
    // Clear child filters when parent changes
    if (field === 'category_id') {
      delete newFilters.sub_category_id;
      delete newFilters.type_id;
      delete newFilters.party_id;
    } else if (field === 'sub_category_id') {
      delete newFilters.type_id;
      delete newFilters.party_id;
    } else if (field === 'type_id') {
      delete newFilters.party_id;
    }
    logger.debug('New filters:', newFilters);
    onFilterChange(newFilters);
  };
  const handleClearFilters = () => {
    logger.debug('Clearing all filters');
    onFilterChange({});
  };
  const hasActiveFilters =
    Object.keys(filters).length > 0 &&
    Object.values(filters).some((v) => v !== undefined && v !== '' && v !== null);
  // ── Create modal ──────────────────────────────────────────────────
  const handleOpenCreateModal = (type, parentId, parentName, onSuccess) => {
    logger.debug('Opening create modal:', { type, parentId, parentName });
    setCreateModalState({ isOpen: true, type, parentId, parentName, onSuccess });
  };
  const handleCloseModal = () => {
    setCreateModalState({
      isOpen: false,
      type: null,
      parentId: null,
      parentName: '',
      onSuccess: null,
    });
  };
  const handleSaveNewItem = async (name, parentId, description) => {
    const { type, onSuccess } = createModalState;
    try {
      let newItem;
      switch (type) {
        case 'category':
          newItem = await onCategoryCreated(name, description);
          break;
        case 'sub_category':
          newItem = await onSubCategoryCreated(name, parentId, description);
          break;
        case 'type':
          newItem = await onTypeCreated(name, parentId, description);
          break;
        case 'party':
          newItem = await onPartyCreated(name, parentId, description);
          break;
        default:
          throw new Error(`Unknown type: ${type}`);
      }
      logger.debug('Created new item:', newItem);
      if (onSuccess && newItem) {
        onSuccess(newItem);
      }
      handleCloseModal();
      return newItem;
    } catch (error) {
      logger.error('Error creating item:', error);
      throw error;
    }
  };
  const allSelected =
    transactionArray.length > 0 &&
    selectedTransactions.length === transactionArray.length;
  // ── Subcomponents ─────────────────────────────────────────────────
  /**
   * Sortable column header with indicator arrow.
   * @param {Object} props
   * @param {string} props.field - Sort key.
   * @param {React.ReactNode} props.children - Column label.
   * @param {string} [props.className] - Extra utilities (e.g. alignment/width).
   */
  const SortableHeader = ({ field, children, className = '' }) => (
    <th onClick={() => handleSort(field)} className={`${TH_SORT} ${className}`}>
      {children}
      {sortField === field && (
        <span className="ml-1 text-muted">{sortDir === 'asc' ? ' ↑' : ' ↓'}</span>
      )}
    </th>
  );
  return (
    <>
      <div className="relative max-h-[calc(100vh-200px)] w-full overflow-auto rounded-lg bg-white shadow-[0_1px_3px_rgba(0,0,0,0.1)]">
        <table className="w-full min-w-[1400px] font-sans text-sm">
          <thead>
            {/* Header row */}
            <tr>
              <th className={`${TH} w-10 text-center`}>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="mx-auto block"
                />
              </th>
              <SortableHeader field="description" className="text-left">
                Description
              </SortableHeader>
              <th className={`${TH} text-left`}>Cleaned Description</th>
              <SortableHeader field="transaction_date" className="text-left">
                Date
              </SortableHeader>
              <SortableHeader field="amount" className="text-right">
                Amount
              </SortableHeader>
              <SortableHeader field="is_credit" className="w-20 text-center">
                Lodgment
              </SortableHeader>
              <SortableHeader field="account_name" className="text-left">
                Account
              </SortableHeader>
              <SortableHeader field="party_name" className="text-left">
                Party
              </SortableHeader>
              <SortableHeader field="type_name" className="text-left">
                Type
              </SortableHeader>
              <SortableHeader field="sub_category_name" className="text-left">
                Sub-Category
              </SortableHeader>
              <SortableHeader field="category_name" className="text-left">
                Category
              </SortableHeader>
              <SortableHeader field="is_kids" className="w-20 text-center">
                Kid&apos;s
              </SortableHeader>
              <SortableHeader field="is_one_off" className="w-20 text-center">
                One-Off
              </SortableHeader>
              <SortableHeader field="has_receipt" className="w-[60px] text-center">
                Receipt
              </SortableHeader>
              <th className={`${TH} w-[60px] text-center`}>Actions</th>
            </tr>
            {/* Filter row */}
            <tr className="bg-gray-50">
              <td className={FILTER_TD}>
                {hasActiveFilters && (
                  <button
                    className="mx-auto flex h-6 w-6 cursor-pointer items-center justify-center rounded-full bg-[#dc3545] p-0 text-xs font-bold text-white transition-colors hover:bg-[#c82333]"
                    onClick={handleClearFilters}
                    title="Clear all filters"
                  >
                    ✕
                  </button>
                )}
              </td>
              <td className={FILTER_TD}>
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters.description || ''}
                  onChange={(e) => handleFilterFieldChange('description', e.target.value)}
                  className={FILTER_INPUT}
                />
              </td>
              <td className={FILTER_TD}>
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters.cleaned_description || ''}
                  onChange={(e) => handleFilterFieldChange('cleaned_description', e.target.value)}
                  className={FILTER_INPUT}
                />
              </td>
              <td className={FILTER_TD}>
                <input
                  type="date"
                  value={filters.start_date || ''}
                  onChange={(e) => handleFilterFieldChange('start_date', e.target.value)}
                  className={`${FILTER_INPUT} min-w-0`}
                  title="From date"
                  placeholder="From"
                />
                {/* mt-0.5 replaces `.filter-date + .filter-date { margin-top: 2px }` */}
                <input
                  type="date"
                  value={filters.end_date || ''}
                  onChange={(e) => handleFilterFieldChange('end_date', e.target.value)}
                  className={`${FILTER_INPUT} mt-0.5 min-w-0`}
                  title="To date"
                  placeholder="To"
                />
              </td>
              <td className={FILTER_TD}>{/* Amount filter — not implemented */}</td>
              <td className={`${FILTER_TD} text-center`}>
                <select
                  value={filters.is_credit === true ? 'true' : filters.is_credit === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_credit', val === '' ? undefined : val === 'true');
                  }}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={FILTER_TD}>
                <select
                  value={filters.account_id || ''}
                  onChange={(e) => handleFilterFieldChange('account_id', e.target.value)}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_name}
                    </option>
                  ))}
                </select>
              </td>
              <td className={FILTER_TD}>
                <select
                  value={filters.party_id || ''}
                  onChange={(e) => handleFilterFieldChange('party_id', e.target.value)}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  {filteredParties.map((party) => (
                    <option key={party.id} value={party.id}>
                      {party.name}
                    </option>
                  ))}
                </select>
              </td>
              <td className={FILTER_TD}>
                <select
                  value={filters.type_id || ''}
                  onChange={(e) => handleFilterFieldChange('type_id', e.target.value)}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  {filteredTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.type}
                    </option>
                  ))}
                </select>
              </td>
              <td className={FILTER_TD}>
                <select
                  value={filters.sub_category_id || ''}
                  onChange={(e) => handleFilterFieldChange('sub_category_id', e.target.value)}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  {filteredSubCategories.map((subCat) => (
                    <option key={subCat.id} value={subCat.id}>
                      {subCat.sub_category}
                    </option>
                  ))}
                </select>
              </td>
              <td className={FILTER_TD}>
                <select
                  value={filters.category_id || ''}
                  onChange={(e) => handleFilterFieldChange('category_id', e.target.value)}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  {sortedCategories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.category}
                    </option>
                  ))}
                </select>
              </td>
              <td className={`${FILTER_TD} text-center`}>
                <select
                  value={filters.is_kids === true ? 'true' : filters.is_kids === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_kids', val === '' ? undefined : val === 'true');
                  }}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={`${FILTER_TD} text-center`}>
                <select
                  value={filters.is_one_off === true ? 'true' : filters.is_one_off === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_one_off', val === '' ? undefined : val === 'true');
                  }}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={`${FILTER_TD} text-center`}>
                <select
                  value={
                    filters.has_receipt === true
                      ? 'true'
                      : filters.has_receipt === false
                      ? 'false'
                      : ''
                  }
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('has_receipt', val === '' ? undefined : val === 'true');
                  }}
                  className={FILTER_SELECT}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={FILTER_TD}>{/* Actions column — no filter */}</td>
            </tr>
          </thead>
          <tbody>
            {transactionArray.map((transaction) => (
              <TransactionRow
                key={transaction.id}
                transaction={transaction}
                accounts={accounts}
                allCategories={categories}
                allSubCategories={subCategories}
                allTypes={types}
                allParties={parties}
                onUpdate={onUpdate}
                onOpenCreateModal={handleOpenCreateModal}
                isSelected={selectedTransactions.includes(transaction.id)}
                onSelectionChange={(checked) => handleRowSelection(transaction.id, checked)}
                onRemapParty={onRemapParty}
                onFindOrCreateParty={onFindOrCreateParty}
                onReceiptChange={onReceiptChange}
              />
            ))}
          </tbody>
        </table>
        {transactionArray.length === 0 && (
          <div className="px-5 py-15 text-center text-base text-muted">
            No transactions found
          </div>
        )}
      </div>
      <CreateCategoryModal
        isOpen={createModalState.isOpen}
        onClose={handleCloseModal}
        onSave={handleSaveNewItem}
        type={createModalState.type}
        parentName={createModalState.parentName}
        parentId={createModalState.parentId}
      />
    </>
  );
}