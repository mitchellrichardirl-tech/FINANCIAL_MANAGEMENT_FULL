import { useState, useEffect } from 'react';
import Dropdown from '@/components/Dropdown';
import Checkbox from '@/components/Checkbox';
import { createLogger } from '@/lib/logger';

const logger = createLogger('FilterBar');

const EMPTY_FILTERS = {
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
};

export default function FilterBar({
  accounts = [],
  parties = [],
  categories = [],
  subCategories = [],
  types = [],
  onFilterChange,
}) {
  logger.debug('FilterBar props:', {
    accounts: accounts.length,
    parties: parties.length,
    categories: categories.length,
    subCategories: subCategories.length,
    types: types.length,
  });

  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filteredSubCategories, setFilteredSubCategories] = useState(subCategories);
  const [filteredTypes, setFilteredTypes] = useState(types);
  const [filteredParties, setFilteredParties] = useState(parties);
  const [descriptionInput, setDescriptionInput] = useState('');
  const [cleanedDescriptionInput, setCleanedDescriptionInput] = useState('');

  useEffect(() => {
    if (filters.category_id) {
      const f = subCategories.filter((sc) => sc.category_id === filters.category_id);
      setFilteredSubCategories(f);
      if (filters.sub_category_id && !f.find((sc) => sc.id === filters.sub_category_id)) {
        setFilters((p) => ({ ...p, sub_category_id: null, type_id: null, party_id: null }));
      }
    } else {
      setFilteredSubCategories(subCategories);
    }
  }, [filters.category_id, subCategories]);

  useEffect(() => {
    if (filters.sub_category_id) {
      const f = types.filter((t) => t.sub_category_id === filters.sub_category_id);
      setFilteredTypes(f);
      if (filters.type_id && !f.find((t) => t.id === filters.type_id)) {
        setFilters((p) => ({ ...p, type_id: null, party_id: null }));
      }
    } else if (filters.category_id) {
      const ids = filteredSubCategories.map((sc) => sc.id);
      setFilteredTypes(types.filter((t) => ids.includes(t.sub_category_id)));
    } else {
      setFilteredTypes(types);
    }
  }, [filters.sub_category_id, filters.category_id, filteredSubCategories, types]);

  useEffect(() => {
    if (filters.type_id) {
      const f = parties.filter((p) => p.type_id === filters.type_id);
      setFilteredParties(f);
      if (filters.party_id && !f.find((p) => p.id === filters.party_id)) {
        setFilters((p) => ({ ...p, party_id: null }));
      }
    } else if (filters.sub_category_id || filters.category_id) {
      const ids = filteredTypes.map((t) => t.id);
      setFilteredParties(parties.filter((p) => ids.includes(p.type_id)));
    } else {
      setFilteredParties(parties);
    }
  }, [filters.type_id, filters.sub_category_id, filters.category_id, filteredTypes, parties]);

  useEffect(() => { onFilterChange(filters); }, [filters, onFilterChange]);

  const handleFilterChange = (key, value) => {
    let processed = value;
    if (['account_id', 'party_id', 'category_id', 'sub_category_id', 'type_id'].includes(key)) {
      processed = value === '' || value === null || value === undefined ? null : parseInt(value, 10);
    }
    if (key === 'category_id') {
      setFilters((p) => ({ ...p, [key]: processed, sub_category_id: null, type_id: null, party_id: null }));
    } else if (key === 'sub_category_id') {
      setFilters((p) => ({ ...p, [key]: processed, type_id: null, party_id: null }));
    } else if (key === 'type_id') {
      setFilters((p) => ({ ...p, [key]: processed, party_id: null }));
    } else {
      setFilters((p) => ({ ...p, [key]: processed }));
    }
  };

  const handleCheckboxFilter = (key, checked) =>
    setFilters((p) => ({ ...p, [key]: checked ? true : null }));

  const handleDescriptionBlur = () => {
    const t = descriptionInput.trim();
    setFilters((p) => ({ ...p, description: t === '' ? null : t }));
  };
  const handleCleanedDescriptionBlur = () => {
    const t = cleanedDescriptionInput.trim();
    setFilters((p) => ({ ...p, cleaned_description: t === '' ? null : t }));
  };
  const handleDescriptionKeyDown = (e) => {
    if (e.key === 'Enter') e.target.blur();
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setDescriptionInput('');
    setCleanedDescriptionInput('');
  };

  const dateInputCls =
    'py-[0.4em] px-[0.8em] border border-[#ddd] rounded bg-[#f9f9f9] text-[#213547] text-[0.9em] font-inherit hover:border-[#646cff] focus:outline-2 focus:outline-[#646cff] focus:outline-offset-1';
  const textInputCls = `${dateInputCls} placeholder:text-[#999] placeholder:italic`;

  return (
    <div className="bg-[rgba(100,108,255,0.05)] p-6 rounded-lg mb-8">
      <h3 className="mt-0 mb-4 text-[1.2em]">Filters</h3>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4 mb-4">
        {[
          ['Account', filters.account_id, (v) => handleFilterChange('account_id', v), accounts, 'account_name', 'All Accounts'],
          ['Category', filters.category_id, (v) => handleFilterChange('category_id', v), categories, 'category', 'All Categories'],
          ['Sub-Category', filters.sub_category_id, (v) => handleFilterChange('sub_category_id', v), filteredSubCategories, 'sub_category', 'All Sub-Categories'],
          ['Type', filters.type_id, (v) => handleFilterChange('type_id', v), filteredTypes, 'type', 'All Types'],
          ['Party', filters.party_id, (v) => handleFilterChange('party_id', v), filteredParties, 'name', 'All Parties'],
        ].map(([label, value, onChange, options, labelKey, emptyLabel]) => (
          <div key={label} className="flex flex-col gap-2">
            <label className="text-[0.9em] font-medium text-[#888]">{label}</label>
            <Dropdown
              value={value}
              onChange={onChange}
              options={options}
              valueKey="id"
              labelKey={labelKey}
              includeEmpty
              emptyLabel={emptyLabel}
            />
          </div>
        ))}

        <div className="flex flex-col gap-2">
          <label className="text-[0.9em] font-medium text-[#888]">Description</label>
          <input
            type="text"
            value={descriptionInput}
            onChange={(e) => setDescriptionInput(e.target.value)}
            onBlur={handleDescriptionBlur}
            onKeyDown={handleDescriptionKeyDown}
            placeholder="Filter by description..."
            className={textInputCls}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-[0.9em] font-medium text-[#888]">Cleaned Description</label>
          <input
            type="text"
            value={cleanedDescriptionInput}
            onChange={(e) => setCleanedDescriptionInput(e.target.value)}
            onBlur={handleCleanedDescriptionBlur}
            onKeyDown={handleDescriptionKeyDown}
            placeholder="Filter by cleaned..."
            className={textInputCls}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-[0.9em] font-medium text-[#888]">Start Date</label>
          <input
            type="date"
            value={filters.start_date}
            onChange={(e) => handleFilterChange('start_date', e.target.value)}
            className={dateInputCls}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-[0.9em] font-medium text-[#888]">End Date</label>
          <input
            type="date"
            value={filters.end_date}
            onChange={(e) => handleFilterChange('end_date', e.target.value)}
            className={dateInputCls}
          />
        </div>
        <div className="flex flex-col gap-2 justify-center pt-[1.4rem]">
          <Checkbox
            checked={filters.is_kids === true}
            onChange={(checked) => handleCheckboxFilter('is_kids', checked)}
            label="Kids Only"
          />
        </div>
        <div className="flex flex-col gap-2 justify-center pt-[1.4rem]">
          <Checkbox
            checked={filters.is_one_off === true}
            onChange={(checked) => handleCheckboxFilter('is_one_off', checked)}
            label="One-Off Only"
          />
        </div>
      </div>
      <button
        type="button"
        onClick={clearFilters}
        className="mt-2 py-[0.6em] px-[1.2em] border border-transparent rounded-lg bg-[#f9f9f9] text-base font-medium font-inherit cursor-pointer hover:border-[#646cff]"
      >
        Clear Filters
      </button>
    </div>
  );
}
