import { useState, useEffect } from 'react';
import Dropdown from '@/components/Dropdown';
import Checkbox from '@/components/Checkbox';
import './FilterBar.css';

export default function FilterBar({ 
  accounts = [],
  parties = [],
  categories = [],  // NEW
  subCategories = [],  // NEW
  types = [],  // NEW
  onFilterChange 
}) {
  console.log('FilterBar props:', { 
    accounts: accounts.length, 
    parties: parties.length,
    categories: categories.length,
    subCategories: subCategories.length,
    types: types.length
  });
  const [filters, setFilters] = useState({
    account_id: null,
    party_id: null,
    category_id: null,  // NEW
    sub_category_id: null,  // NEW
    type_id: null,  // NEW
    start_date: '',
    end_date: '',
    description: '',
    cleaned_description: '',
    is_kids: null,
    is_one_off: null,
  });

  // Filtered options for cascading dropdowns
  const [filteredSubCategories, setFilteredSubCategories] = useState(subCategories);
  const [filteredTypes, setFilteredTypes] = useState(types);
  const [filteredParties, setFilteredParties] = useState(parties);

  // Temporary state for text inputs (to avoid filtering on every keystroke)
  const [descriptionInput, setDescriptionInput] = useState('');
  const [cleanedDescriptionInput, setCleanedDescriptionInput] = useState('');

  // Update filtered options when category selection changes
  useEffect(() => {
    if (filters.category_id) {
      const filtered = subCategories.filter(sc => sc.category_id === filters.category_id);
      setFilteredSubCategories(filtered);
      
      // If current sub_category is not in the filtered list, clear it
      if (filters.sub_category_id && !filtered.find(sc => sc.id === filters.sub_category_id)) {
        setFilters(prev => ({ ...prev, sub_category_id: null, type_id: null, party_id: null }));
      }
    } else {
      setFilteredSubCategories(subCategories);
    }
  }, [filters.category_id, subCategories]);

  // Update filtered types when sub-category selection changes
  useEffect(() => {
    if (filters.sub_category_id) {
      const filtered = types.filter(t => t.sub_category_id === filters.sub_category_id);
      setFilteredTypes(filtered);
      
      // If current type is not in the filtered list, clear it
      if (filters.type_id && !filtered.find(t => t.id === filters.type_id)) {
        setFilters(prev => ({ ...prev, type_id: null, party_id: null }));
      }
    } else if (filters.category_id) {
      // If only category is selected, show types that belong to selected category's sub-categories
      const subCatIds = filteredSubCategories.map(sc => sc.id);
      setFilteredTypes(types.filter(t => subCatIds.includes(t.sub_category_id)));
    } else {
      setFilteredTypes(types);
    }
  }, [filters.sub_category_id, filters.category_id, filteredSubCategories, types]);

  // Update filtered parties when type selection changes
  useEffect(() => {
    if (filters.type_id) {
      const filtered = parties.filter(p => p.type_id === filters.type_id);
      setFilteredParties(filtered);
      
      // If current party is not in the filtered list, clear it
      if (filters.party_id && !filtered.find(p => p.id === filters.party_id)) {
        setFilters(prev => ({ ...prev, party_id: null }));
      }
    } else if (filters.sub_category_id || filters.category_id) {
      // Show parties that belong to filtered types
      const typeIds = filteredTypes.map(t => t.id);
      setFilteredParties(parties.filter(p => typeIds.includes(p.type_id)));
    } else {
      setFilteredParties(parties);
    }
  }, [filters.type_id, filters.sub_category_id, filters.category_id, filteredTypes, parties]);

  useEffect(() => {
    onFilterChange(filters);
  }, [filters, onFilterChange]);

  const handleFilterChange = (key, value) => {
    // Convert value to appropriate type
    let processedValue = value;
    
    if (['account_id', 'party_id', 'category_id', 'sub_category_id', 'type_id'].includes(key)) {
      // Convert to number, or null if empty string
      if (value === '' || value === null || value === undefined) {
        processedValue = null;
      } else {
        processedValue = parseInt(value, 10);
      }
    }

    // Handle cascading clears
    if (key === 'category_id') {
      setFilters(prev => ({ 
        ...prev, 
        [key]: processedValue,
        sub_category_id: null,
        type_id: null,
        party_id: null
      }));
    } else if (key === 'sub_category_id') {
      setFilters(prev => ({ 
        ...prev, 
        [key]: processedValue,
        type_id: null,
        party_id: null
      }));
    } else if (key === 'type_id') {
      setFilters(prev => ({ 
        ...prev, 
        [key]: processedValue,
        party_id: null
      }));
    } else {
      setFilters(prev => ({ ...prev, [key]: processedValue }));
    }
  };

  const handleCheckboxFilter = (key, checked) => {
    setFilters(prev => ({ ...prev, [key]: checked ? true : null }));
  };

  // Handle description filter when user leaves the input
  const handleDescriptionBlur = () => {
    const trimmedValue = descriptionInput.trim();
    setFilters(prev => ({ 
      ...prev, 
      description: trimmedValue === '' ? null : trimmedValue 
    }));
  };

  // Handle cleaned description filter when user leaves the input
  const handleCleanedDescriptionBlur = () => {
    const trimmedValue = cleanedDescriptionInput.trim();
    setFilters(prev => ({ 
      ...prev, 
      cleaned_description: trimmedValue === '' ? null : trimmedValue 
    }));
  };

  // Allow Enter key to trigger filter
  const handleDescriptionKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur(); // This will trigger the onBlur event
    }
  };

  const clearFilters = () => {
    setFilters({
      account_id: null,
      party_id: null,
      category_id: null,
      sub_category_id: null,
      type_id: null,
      start_date: '',
      end_date: '',
      description: '',
      cleaned_description: '',
      is_kids: null,
      is_one_off: null,
    });
    setDescriptionInput('');
    setCleanedDescriptionInput('');
  };

  return (
    <div className="filter-bar">
      <h3>Filters</h3>
      
      <div className="filter-grid">
        <div className="filter-item">
          <label>Account</label>
          <Dropdown
            value={filters.account_id}
            onChange={(value) => handleFilterChange('account_id', value)}
            options={accounts}
            valueKey="id"
            labelKey="account_name"
            includeEmpty
            emptyLabel="All Accounts"
          />
        </div>

        <div className="filter-item">
          <label>Category</label>
          <Dropdown
            value={filters.category_id}
            onChange={(value) => handleFilterChange('category_id', value)}
            options={categories}
            valueKey="id"
            labelKey="category"
            includeEmpty
            emptyLabel="All Categories"
          />
        </div>

        <div className="filter-item">
          <label>Sub-Category</label>
          <Dropdown
            value={filters.sub_category_id}
            onChange={(value) => handleFilterChange('sub_category_id', value)}
            options={filteredSubCategories}
            valueKey="id"
            labelKey="sub_category"
            includeEmpty
            emptyLabel="All Sub-Categories"
            disabled={!filters.category_id && filteredSubCategories.length === 0}
          />
        </div>

        <div className="filter-item">
          <label>Type</label>
          <Dropdown
            value={filters.type_id}
            onChange={(value) => handleFilterChange('type_id', value)}
            options={filteredTypes}
            valueKey="id"
            labelKey="type"
            includeEmpty
            emptyLabel="All Types"
            disabled={!filters.sub_category_id && !filters.category_id && filteredTypes.length === 0}
          />
        </div>

        <div className="filter-item">
          <label>Party</label>
          <Dropdown
            value={filters.party_id}
            onChange={(value) => handleFilterChange('party_id', value)}
            options={filteredParties}
            valueKey="id"
            labelKey="name"
            includeEmpty
            emptyLabel="All Parties"
            disabled={!filters.type_id && !filters.sub_category_id && !filters.category_id && filteredParties.length === 0}
          />
        </div>

        <div className="filter-item">
          <label>Description</label>
          <input
            type="text"
            value={descriptionInput}
            onChange={(e) => setDescriptionInput(e.target.value)}
            onBlur={handleDescriptionBlur}
            onKeyDown={handleDescriptionKeyDown}
            placeholder="Filter by description..."
            className="text-input"
          />
        </div>

        <div className="filter-item">
          <label>Cleaned Description</label>
          <input
            type="text"
            value={cleanedDescriptionInput}
            onChange={(e) => setCleanedDescriptionInput(e.target.value)}
            onBlur={handleCleanedDescriptionBlur}
            onKeyDown={handleDescriptionKeyDown}
            placeholder="Filter by cleaned..."
            className="text-input"
          />
        </div>

        <div className="filter-item">
          <label>Start Date</label>
          <input
            type="date"
            value={filters.start_date}
            onChange={(e) => handleFilterChange('start_date', e.target.value)}
            className="date-input"
          />
        </div>

        <div className="filter-item">
          <label>End Date</label>
          <input
            type="date"
            value={filters.end_date}
            onChange={(e) => handleFilterChange('end_date', e.target.value)}
            className="date-input"
          />
        </div>

        <div className="filter-item filter-checkbox">
          <Checkbox
            checked={filters.is_kids === true}
            onChange={(checked) => handleCheckboxFilter('is_kids', checked)}
            label="Kids Only"
          />
        </div>

        <div className="filter-item filter-checkbox">
          <Checkbox
            checked={filters.is_one_off === true}
            onChange={(checked) => handleCheckboxFilter('is_one_off', checked)}
            label="One-Off Only"
          />
        </div>
      </div>

      <button onClick={clearFilters} className="clear-filters-button">
        Clear Filters
      </button>
    </div>
  );
}