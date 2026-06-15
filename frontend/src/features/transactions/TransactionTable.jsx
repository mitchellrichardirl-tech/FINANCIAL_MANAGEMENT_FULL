/**
 * @file TransactionTable.jsx
 * Sortable, filterable, multi-select transaction table with inline
 * editing and taxonomy-aware cascading filters.
 *
 * The table owns **presentation state only** (sort column/direction,
 * filter inputs, modal visibility). Row data, selection set, and the
 * taxonomy lists are lifted to the parent, which also supplies
 * callbacks for mutation (`onUpdate`, `onCreate*`, `onRemapParty`, …).
 */

import { useState, useMemo } from 'react';
import TransactionRow from './TransactionRow';
import CreateCategoryModal from './CreateCategoryModal';
import './TransactionTable.css';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('TransactionTable');

/**
 * Main transaction listing.
 *
 * Features:
 *  - **Sortable headers** — click toggles asc ↔ desc; emits
 *    `onSortChange(field, dir)` for the parent to re-fetch/sort.
 *  - **Inline filter row** — each column renders an input/select whose
 *    changes bubble via `onFilterChange`. Child filters (sub-category,
 *    type, party) are automatically cleared when a parent filter
 *    changes.
 *  - **Bulk selection** — header checkbox selects/deselects all visible
 *    rows; individual row checkboxes toggle that row.
 *  - **Inline editing** — delegated to {@link TransactionRow}; this
 *    component opens a single {@link CreateCategoryModal} on demand
 *    for any taxonomy level.
 *
 * @component
 * @param {Object} props
 *
 * @param {Array<Object>} props.transactions
 *        Rows to display. The component guards against non-arrays.
 * @param {Array<Object>} props.accounts
 *        Account list for the Account filter dropdown.
 * @param {Array<Object>} props.categories
 *        Top-level categories.
 * @param {Array<Object>} props.subCategories
 *        Sub-categories (all; filtering done here).
 * @param {Array<Object>} props.types
 *        Types (all; filtering done here).
 * @param {Array<Object>} props.parties
 *        Parties (all; filtering done here).
 *
 * @param {(txnId: number, updates: Object) => Promise<void>} props.onUpdate
 *        Persist changes to a single transaction.
 * @param {(name: string, desc?: string) => Promise<Object>} props.onCategoryCreated
 *        Create a new category.
 * @param {(name: string, categoryId: number, desc?: string) => Promise<Object>} props.onSubCategoryCreated
 * @param {(name: string, subCategoryId: number, desc?: string) => Promise<Object>} props.onTypeCreated
 * @param {(name: string, typeId: number, desc?: string) => Promise<Object>} props.onPartyCreated
 *
 * @param {Array<number>} props.selectedTransactions
 *        Currently selected row ids.
 * @param {(ids: Array<number>) => void} props.onSelectionChange
 *        Replace the selection set.
 *
 * @param {Object} props.filters
 *        Current filter state (keyed by backend param names).
 * @param {(filters: Object) => void} props.onFilterChange
 *        Replace the filter object.
 *
 * @param {(partyId: number) => void} props.onRemapParty
 *        Open the remap-party modal for a given party.
 * @param {(partyName: string, typeId: number) => Promise<number>} props.onFindOrCreateParty
 *        Find or create a party by name under a type; returns the id.
 *
 * @param {string} props.sortField - Currently sorted column key.
 * @param {'asc'|'desc'} props.sortDir - Current sort direction.
 * @param {(field: string, dir: 'asc'|'desc') => void} props.onSortChange
 *        Called when the user clicks a sortable header.
 *
 * @returns {JSX.Element}
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
  /**
   * Controls the single shared "create taxonomy item" modal.
   * @type {[{isOpen: boolean, type: ?string, parentId: ?number, parentName: string, onSuccess: ?Function}, Function]}
   */
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
  /** Categories sorted alphabetically by name. */
  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  /**
   * Sub-categories scoped to `filters.category_id` (if set) and sorted.
   */
  const filteredSubCategories = useMemo(() => {
    let filtered = [...subCategories];

    if (filters.category_id) {
      filtered = filtered.filter((sc) => sc.category_id === filters.category_id);
    }

    return filtered.sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, filters.category_id]);

  /**
   * Types scoped to `filters.sub_category_id`, or to the full set of
   * sub-categories in `filters.category_id` if no sub-category is picked.
   */
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

  /**
   * Parties scoped to `filters.type_id`, or cascaded through
   * sub-category / category if those are set instead.
   */
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
  /**
   * Toggle sort direction or switch to a new column (defaults to `asc`).
   * @param {string} field - Column key.
   */
  const handleSort = (field) => {
    const newDir = sortField === field && sortDir === 'asc' ? 'desc' : 'asc';
    onSortChange(field, newDir);
  };

  // ── Selection ─────────────────────────────────────────────────────
  /**
   * Select or deselect all currently visible rows.
   * @param {boolean} checked
   */
  const handleSelectAll = (checked) => {
    if (checked) {
      onSelectionChange(transactionArray.map((t) => t.id));
    } else {
      onSelectionChange([]);
    }
  };

  /**
   * Add/remove a single transaction from the selection.
   * @param {number} transactionId
   * @param {boolean} checked
   */
  const handleRowSelection = (transactionId, checked) => {
    if (checked) {
      onSelectionChange([...selectedTransactions, transactionId]);
    } else {
      onSelectionChange(selectedTransactions.filter((id) => id !== transactionId));
    }
  };

  // ── Filtering ─────────────────────────────────────────────────────
  /**
   * Update a single filter field, coercing id fields to `number` and
   * clearing child filters when a parent changes.
   *
   * @param {string} field - Filter key.
   * @param {*} value - New value; falsy clears the field.
   */
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

  /** Reset all filters to the empty state. */
  const handleClearFilters = () => {
    logger.debug('Clearing all filters');
    onFilterChange({});
  };

  /** `true` when any filter is set. */
  const hasActiveFilters =
    Object.keys(filters).length > 0 &&
    Object.values(filters).some((v) => v !== undefined && v !== '' && v !== null);

  // ── Create modal ──────────────────────────────────────────────────
  /**
   * Open the shared create modal for a given taxonomy level.
   *
   * @param {'category'|'sub_category'|'type'|'party'} type
   * @param {?number} parentId - Required for non-root levels.
   * @param {string} parentName - Shown in the modal header.
   * @param {(newItem: Object) => void} onSuccess
   *        Called after creation with the new record (so the row can
   *        set the dropdown to the newly created id).
   */
  const handleOpenCreateModal = (type, parentId, parentName, onSuccess) => {
    logger.debug('Opening create modal:', { type, parentId, parentName });
    setCreateModalState({
      isOpen: true,
      type,
      parentId,
      parentName,
      onSuccess,
    });
  };

  /** Close the modal and reset its state. */
  const handleCloseModal = () => {
    setCreateModalState({
      isOpen: false,
      type: null,
      parentId: null,
      parentName: '',
      onSuccess: null,
    });
  };

  /**
   * Callback bound to the modal's "Save" action; delegates to the
   * appropriate `onXxxCreated` prop and then invokes `onSuccess`.
   *
   * @async
   * @param {string} name - User-entered name.
   * @param {?number} parentId - Passed through (may be `null` for categories).
   * @param {?string} description - Optional description.
   * @returns {Promise<Object>} The created record.
   */
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

  /** `true` when every visible row is selected. */
  const allSelected =
    transactionArray.length > 0 &&
    selectedTransactions.length === transactionArray.length;

  // ── Subcomponents ─────────────────────────────────────────────────
  /**
   * Sortable column header with indicator arrow.
   * @param {Object} props
   * @param {string} props.field - Sort key.
   * @param {React.ReactNode} props.children - Column label.
   * @param {string} [props.className]
   */
  const SortableHeader = ({ field, children, className = '' }) => (
    <th onClick={() => handleSort(field)} className={`sortable-header ${className}`}>
      {children}
      {sortField === field && (
        <span className="sort-indicator">{sortDir === 'asc' ? ' ↑' : ' ↓'}</span>
      )}
    </th>
  );

  return (
    <>
      <div className="transaction-table-container">
        <table className="transaction-table">
          <thead>
            {/* Header row */}
            <tr className="header-row">
              <th className="select-header">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                />
              </th>
              <SortableHeader field="description">Description</SortableHeader>
              <th>Cleaned Description</th>
              <SortableHeader field="transaction_date">Date</SortableHeader>
              <SortableHeader field="amount" className="amount-header">Amount</SortableHeader>
              <SortableHeader field="is_credit" className="lodgment-header">Lodgment</SortableHeader>
              <SortableHeader field="account_name">Account</SortableHeader>
              <SortableHeader field="party_name">Party</SortableHeader>
              <SortableHeader field="type_name">Type</SortableHeader>
              <SortableHeader field="sub_category_name">Sub-Category</SortableHeader>
              <SortableHeader field="category_name">Category</SortableHeader>
              <SortableHeader field="is_kids" className="kids-header">Kid's</SortableHeader>
              <SortableHeader field="is_one_off" className="one-off-header">One-Off</SortableHeader>
              <SortableHeader field="has_receipt" className="receipt-header">Receipt</SortableHeader>
              <th className="actions-header">Actions</th>
            </tr>

            {/* Filter row */}
            <tr className="filter-row">
              <td className="filter-cell">
                {hasActiveFilters && (
                  <button
                    className="clear-filters-btn"
                    onClick={handleClearFilters}
                    title="Clear all filters"
                  >
                    ✕
                  </button>
                )}
              </td>
              <td className="filter-cell">
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters.description || ''}
                  onChange={(e) => handleFilterFieldChange('description', e.target.value)}
                  className="filter-input"
                />
              </td>
              <td className="filter-cell">
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters.cleaned_description || ''}
                  onChange={(e) => handleFilterFieldChange('cleaned_description', e.target.value)}
                  className="filter-input"
                />
              </td>
              <td className="filter-cell">
                <input
                  type="date"
                  value={filters.start_date || ''}
                  onChange={(e) => handleFilterFieldChange('start_date', e.target.value)}
                  className="filter-input filter-date"
                  title="From date"
                  placeholder="From"
                />
                <input
                  type="date"
                  value={filters.end_date || ''}
                  onChange={(e) => handleFilterFieldChange('end_date', e.target.value)}
                  className="filter-input filter-date"
                  title="To date"
                  placeholder="To"
                />
              </td>
              <td className="filter-cell">{/* Amount filter — not implemented */}</td>
              <td className="filter-cell filter-cell-center">
                <select
                  value={filters.is_credit === true ? 'true' : filters.is_credit === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_credit', val === '' ? undefined : val === 'true');
                  }}
                  className="filter-select"
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className="filter-cell">
                <select
                  value={filters.account_id || ''}
                  onChange={(e) => handleFilterFieldChange('account_id', e.target.value)}
                  className="filter-select"
                >
                  <option value="">All</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_name}
                    </option>
                  ))}
                </select>
              </td>
              <td className="filter-cell">
                <select
                  value={filters.party_id || ''}
                  onChange={(e) => handleFilterFieldChange('party_id', e.target.value)}
                  className="filter-select"
                >
                  <option value="">All</option>
                  {filteredParties.map((party) => (
                    <option key={party.id} value={party.id}>
                      {party.name}
                    </option>
                  ))}
                </select>
              </td>
              <td className="filter-cell">
                <select
                  value={filters.type_id || ''}
                  onChange={(e) => handleFilterFieldChange('type_id', e.target.value)}
                  className="filter-select"
                >
                  <option value="">All</option>
                  {filteredTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.type}
                    </option>
                  ))}
                </select>
              </td>
              <td className="filter-cell">
                <select
                  value={filters.sub_category_id || ''}
                  onChange={(e) => handleFilterFieldChange('sub_category_id', e.target.value)}
                  className="filter-select"
                >
                  <option value="">All</option>
                  {filteredSubCategories.map((subCat) => (
                    <option key={subCat.id} value={subCat.id}>
                      {subCat.sub_category}
                    </option>
                  ))}
                </select>
              </td>
              <td className="filter-cell">
                <select
                  value={filters.category_id || ''}
                  onChange={(e) => handleFilterFieldChange('category_id', e.target.value)}
                  className="filter-select"
                >
                  <option value="">All</option>
                  {sortedCategories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.category}
                    </option>
                  ))}
                </select>
              </td>
              <td className="filter-cell filter-cell-center">
                <select
                  value={filters.is_kids === true ? 'true' : filters.is_kids === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_kids', val === '' ? undefined : val === 'true');
                  }}
                  className="filter-select"
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className="filter-cell filter-cell-center">
                <select
                  value={filters.is_one_off === true ? 'true' : filters.is_one_off === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_one_off', val === '' ? undefined : val === 'true');
                  }}
                  className="filter-select"
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className="filter-cell filter-cell-center">
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
                  className="filter-select"
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className="filter-cell">{/* Actions column — no filter */}</td>
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
          <div className="no-transactions">No transactions found</div>
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