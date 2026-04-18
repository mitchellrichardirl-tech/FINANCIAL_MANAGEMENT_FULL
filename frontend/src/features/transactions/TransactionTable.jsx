import { useState, useMemo } from 'react';
import TransactionRow from './TransactionRow';
import CreateCategoryModal from './CreateCategoryModal';
import { createLogger } from '@/lib/logger';

const logger = createLogger('TransactionTable');

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
}) {
  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentId: null,
    parentName: '',
    onSuccess: null,
  });

  const transactionArray = Array.isArray(transactions) ? transactions : [];

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

  const handleSort = (field) => {
    const newDir = sortField === field && sortDir === 'asc' ? 'desc' : 'asc';
    onSortChange(field, newDir);
  };

  const handleSelectAll = (checked) => {
    onSelectionChange(checked ? transactionArray.map((t) => t.id) : []);
  };

  const handleRowSelection = (transactionId, checked) => {
    if (checked) {
      onSelectionChange([...selectedTransactions, transactionId]);
    } else {
      onSelectionChange(selectedTransactions.filter((id) => id !== transactionId));
    }
  };

  const handleFilterFieldChange = (field, value) => {
    logger.debug('Filter change:', field, value, 'Current filters:', filters);
    const newFilters = { ...filters };

    if (value === undefined || value === '' || value === null) {
      delete newFilters[field];
    } else {
      const idFields = ['account_id', 'party_id', 'category_id', 'sub_category_id', 'type_id'];
      newFilters[field] = idFields.includes(field) ? parseInt(value, 10) : value;
    }

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

    onFilterChange(newFilters);
  };

  const handleClearFilters = () => onFilterChange({});

  const hasActiveFilters =
    Object.keys(filters).length > 0 &&
    Object.values(filters).some((v) => v !== undefined && v !== '' && v !== null);

  const handleOpenCreateModal = (type, parentId, parentName, onSuccess) => {
    setCreateModalState({ isOpen: true, type, parentId, parentName, onSuccess });
  };

  const handleCloseModal = () => {
    setCreateModalState({ isOpen: false, type: null, parentId: null, parentName: '', onSuccess: null });
  };

  const handleSaveNewItem = async (name, parentId, description) => {
    const { type, onSuccess } = createModalState;
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
    if (onSuccess && newItem) onSuccess(newItem);
    handleCloseModal();
    return newItem;
  };

  const allSelected =
    transactionArray.length > 0 &&
    selectedTransactions.length === transactionArray.length;

  const headerCls =
    'bg-[#f8f9fa] border-b-2 border-[#dee2e6] text-[#495057] font-semibold py-3 px-2 text-left whitespace-nowrap sticky top-0 z-[11]';
  const sortableCls = `${headerCls} cursor-pointer select-none hover:bg-[#e9ecef]`;
  const filterTdCls =
    'sticky top-[44px] z-10 bg-[#f8f9fa] py-1.5 px-2 border-b-2 border-[#dee2e6] align-middle';
  const filterInputCls =
    'w-full py-1.5 px-2 border border-[#ced4da] rounded text-[13px] font-inherit box-border focus:border-[#80bdff] focus:outline-none focus:shadow-[0_0_0_2px_rgba(0,123,255,0.25)] placeholder:text-[#adb5bd]';
  const filterSelectCls =
    'w-full py-1.5 px-2 border border-[#ced4da] rounded text-[13px] font-inherit bg-white box-border cursor-pointer focus:border-[#80bdff] focus:outline-none focus:shadow-[0_0_0_2px_rgba(0,123,255,0.25)]';

  const SortableHeader = ({ field, children, className = '' }) => (
    <th onClick={() => handleSort(field)} className={`${sortableCls} ${className}`}>
      {children}
      {sortField === field && (
        <span className="ml-1 text-[#6c757d]">{sortDir === 'asc' ? ' ↑' : ' ↓'}</span>
      )}
    </th>
  );

  return (
    <>
      <div className="w-full max-h-[calc(100vh-200px)] overflow-auto bg-white rounded-lg shadow-[0_1px_3px_rgba(0,0,0,0.1)] relative">
        <table className="w-full min-w-[1400px] border-collapse font-sans text-sm">
          <thead>
            <tr>
              <th className={`${headerCls} w-10 text-center`}>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="block mx-auto"
                />
              </th>
              <SortableHeader field="description">Description</SortableHeader>
              <th className={headerCls}>Cleaned Description</th>
              <SortableHeader field="transaction_date">Date</SortableHeader>
              <SortableHeader field="amount" className="!text-right">Amount</SortableHeader>
              <SortableHeader field="is_credit">Lodgment</SortableHeader>
              <SortableHeader field="account_name">Account</SortableHeader>
              <SortableHeader field="party_name">Party</SortableHeader>
              <SortableHeader field="type_name">Type</SortableHeader>
              <SortableHeader field="sub_category_name">Sub-Category</SortableHeader>
              <SortableHeader field="category_name">Category</SortableHeader>
              <SortableHeader field="is_kids">Kid&apos;s</SortableHeader>
              <SortableHeader field="is_one_off">One-Off</SortableHeader>
              <th className={`${headerCls} w-[60px] text-center`}>Actions</th>
            </tr>

            <tr className="bg-[#f8f9fa]">
              <td className={`${filterTdCls} text-center`}>
                {hasActiveFilters && (
                  <button
                    type="button"
                    onClick={handleClearFilters}
                    title="Clear all filters"
                    className="w-6 h-6 p-0 border-0 rounded-full bg-[#dc3545] text-white text-xs font-bold cursor-pointer flex items-center justify-center mx-auto hover:bg-[#c82333]"
                  >
                    ✕
                  </button>
                )}
              </td>
              <td className={filterTdCls}>
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters.description || ''}
                  onChange={(e) => handleFilterFieldChange('description', e.target.value)}
                  className={filterInputCls}
                />
              </td>
              <td className={filterTdCls}>
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters.cleaned_description || ''}
                  onChange={(e) => handleFilterFieldChange('cleaned_description', e.target.value)}
                  className={filterInputCls}
                />
              </td>
              <td className={filterTdCls}>
                <input
                  type="date"
                  value={filters.start_date || ''}
                  onChange={(e) => handleFilterFieldChange('start_date', e.target.value)}
                  className={`${filterInputCls} w-full min-w-0`}
                  title="From date"
                />
                <input
                  type="date"
                  value={filters.end_date || ''}
                  onChange={(e) => handleFilterFieldChange('end_date', e.target.value)}
                  className={`${filterInputCls} w-full min-w-0 mt-[2px]`}
                  title="To date"
                />
              </td>
              <td className={filterTdCls} />
              <td className={`${filterTdCls} text-center`}>
                <select
                  value={filters.is_credit === true ? 'true' : filters.is_credit === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_credit', val === '' ? undefined : val === 'true');
                  }}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={filterTdCls}>
                <select
                  value={filters.account_id || ''}
                  onChange={(e) => handleFilterFieldChange('account_id', e.target.value)}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_name}
                    </option>
                  ))}
                </select>
              </td>
              <td className={filterTdCls}>
                <select
                  value={filters.party_id || ''}
                  onChange={(e) => handleFilterFieldChange('party_id', e.target.value)}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  {filteredParties.map((party) => (
                    <option key={party.id} value={party.id}>
                      {party.name}
                    </option>
                  ))}
                </select>
              </td>
              <td className={filterTdCls}>
                <select
                  value={filters.type_id || ''}
                  onChange={(e) => handleFilterFieldChange('type_id', e.target.value)}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  {filteredTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.type}
                    </option>
                  ))}
                </select>
              </td>
              <td className={filterTdCls}>
                <select
                  value={filters.sub_category_id || ''}
                  onChange={(e) => handleFilterFieldChange('sub_category_id', e.target.value)}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  {filteredSubCategories.map((subCat) => (
                    <option key={subCat.id} value={subCat.id}>
                      {subCat.sub_category}
                    </option>
                  ))}
                </select>
              </td>
              <td className={filterTdCls}>
                <select
                  value={filters.category_id || ''}
                  onChange={(e) => handleFilterFieldChange('category_id', e.target.value)}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  {sortedCategories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.category}
                    </option>
                  ))}
                </select>
              </td>
              <td className={`${filterTdCls} text-center`}>
                <select
                  value={filters.is_kids === true ? 'true' : filters.is_kids === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_kids', val === '' ? undefined : val === 'true');
                  }}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={`${filterTdCls} text-center`}>
                <select
                  value={filters.is_one_off === true ? 'true' : filters.is_one_off === false ? 'false' : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleFilterFieldChange('is_one_off', val === '' ? undefined : val === 'true');
                  }}
                  className={filterSelectCls}
                >
                  <option value="">All</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </td>
              <td className={filterTdCls} />
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
              />
            ))}
          </tbody>
        </table>

        {transactionArray.length === 0 && (
          <div className="text-center py-16 px-5 text-[#6c757d] text-base">
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
