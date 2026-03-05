import { useState, useMemo } from 'react';
import TransactionRow from './TransactionRow';
import CreateCategoryModal from './CreateCategoryModal';
import './TransactionTable.css';

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
  
  // Modal state
  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentId: null,
    parentName: '',
    onSuccess: null,
  });

  const transactionArray = Array.isArray(transactions) ? transactions : [];

  const sortedAccounts = useMemo(() => 
    [...accounts]
      .sort((a, b) => a.account_name.localeCompare(b.account_name)),
    [accounts]
  );

  const sortedCategories = useMemo(() => 
    [...categories]
      .sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  const filteredSubCategories = useMemo(() => {
    let filtered = [...subCategories];
    
    if (filters.category_id) {
      filtered = filtered.filter(sc => sc.category_id === filters.category_id);
    }
    
    return filtered.sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, filters.category_id]);

  const filteredTypes = useMemo(() => {
    let filtered = [...types];
    
    if (filters.sub_category_id) {
      // Direct filter by sub-category
      filtered = filtered.filter(t => t.sub_category_id === filters.sub_category_id);
    } else if (filters.category_id) {
      // Filter by all sub-categories in the selected category
      const subCatIds = subCategories
        .filter(sc => sc.category_id === filters.category_id)
        .map(sc => sc.id);
      filtered = filtered.filter(t => subCatIds.includes(t.sub_category_id));
    }
    
    return filtered.sort((a, b) => a.type.localeCompare(b.type));
  }, [types, subCategories, filters.sub_category_id, filters.category_id]);

  const filteredParties = useMemo(() => {
    let filtered = [...parties];
    
    if (filters.type_id) {
      // Direct filter by type
      filtered = filtered.filter(p => p.type_id === filters.type_id);
    } else if (filters.sub_category_id) {
      // Filter by all types in the selected sub-category
      const typeIds = types
        .filter(t => t.sub_category_id === filters.sub_category_id)
        .map(t => t.id);
      filtered = filtered.filter(p => typeIds.includes(p.type_id));
    } else if (filters.category_id) {
      // Filter by all types in all sub-categories of the selected category
      const subCatIds = subCategories
        .filter(sc => sc.category_id === filters.category_id)
        .map(sc => sc.id);
      const typeIds = types
        .filter(t => subCatIds.includes(t.sub_category_id))
        .map(t => t.id);
      filtered = filtered.filter(p => typeIds.includes(p.type_id));
    }
    
    return filtered.sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, types, subCategories, filters.type_id, filters.sub_category_id, filters.category_id]);

  const handleSort = (field) => {
    const newDir =
      sortField === field && sortDir === 'asc' ? 'desc' : 'asc';
    onSortChange(field, newDir);
  };

  const handleSelectAll = (checked) => {
    if (checked) {
      onSelectionChange(transactionArray.map(t => t.id));
    } else {
      onSelectionChange([]);
    }
  };

  const handleRowSelection = (transactionId, checked) => {
    if (checked) {
      onSelectionChange([...selectedTransactions, transactionId]);
    } else {
      onSelectionChange(selectedTransactions.filter(id => id !== transactionId));
    }
  };

  // Filter change handler - properly preserves existing filters
  const handleFilterFieldChange = (field, value) => {
    console.log('Filter change:', field, value, 'Current filters:', filters);
    
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
    
    console.log('New filters:', newFilters);
    onFilterChange(newFilters);
  };

  // Clear all filters
  const handleClearFilters = () => {
    console.log('Clearing all filters');
    onFilterChange({});
  };

  // Check if any filters are active
  const hasActiveFilters = Object.keys(filters).length > 0 && 
    Object.values(filters).some(v => v !== undefined && v !== '' && v !== null);

  // Unified create handler - called by TransactionRow
  const handleOpenCreateModal = (type, parentId, parentName, onSuccess) => {
    console.log('Opening create modal:', { type, parentId, parentName });
    setCreateModalState({
      isOpen: true,
      type,
      parentId,
      parentName,
      onSuccess,
    });
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
      
      console.log('Created new item:', newItem);
      
      if (onSuccess && newItem) {
        onSuccess(newItem);
      }
      
      handleCloseModal();
      return newItem;
    } catch (error) {
      console.error('Error creating item:', error);
      throw error;
    }
  };

  const allSelected = transactionArray.length > 0 && 
    selectedTransactions.length === transactionArray.length;

  const SortableHeader = ({ field, children, className = '' }) => (
    <th 
      onClick={() => handleSort(field)} 
      className={`sortable-header ${className}`}
    >
      {children}
      {sortField === field && (
        <span className="sort-indicator">
          {sortDir === 'asc' ? ' ↑' : ' ↓'}
        </span>
      )}
    </th>
  );

  console.log('Current filters state:', filters);
  console.log('is_kids filter:', filters.is_kids, typeof filters.is_kids);
  console.log('is_one_off filter:', filters.is_one_off, typeof filters.is_one_off);

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
              <td className="filter-cell">
                {/* Amount filter - could add min/max */}
              </td>
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
                  {accounts.map(account => (
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
                  {filteredParties.map(party => (
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
                  {filteredTypes.map(type => (
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
                  {filteredSubCategories.map(subCat => (
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
                  {sortedCategories.map(cat => (
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
              <td className="filter-cell">
                {/* Actions column - no filter */}
              </td>
            </tr>
          </thead>
          <tbody>
            {transactions.map(transaction => (
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
          <div className="no-transactions">
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