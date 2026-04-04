/**
 * @file FilterBar.jsx
 * Sidebar filter panel with cascading taxonomy dropdowns.
 *
 * This component owns **its own local filter state** and syncs it to
 * the parent via `onFilterChange` (called inside a `useEffect`).
 *
 * Cascading behavior:
 *  - Picking a category narrows sub-categories / types / parties.
 *  - Picking a sub-category further narrows types / parties.
 *  - Clearing a parent clears all children.
 *
 * Text filters (description, cleaned description) are applied on
 * blur/Enter to avoid excessive re-renders while typing.
 */

import { useState, useEffect } from 'react';
import Dropdown from '@/components/Dropdown';
import Checkbox from '@/components/Checkbox';
import './FilterBar.css';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('FilterBar');

/**
 * Shape of the filter object emitted via `onFilterChange`.
 * Keys with `null` values are typically omitted or ignored by the API.
 *
 * @typedef {Object} Filters
 * @property {?number} account_id
 * @property {?number} party_id
 * @property {?number} category_id
 * @property {?number} sub_category_id
 * @property {?number} type_id
 * @property {string}  start_date - '' means unset.
 * @property {string}  end_date
 * @property {?string} description
 * @property {?string} cleaned_description
 * @property {?boolean} is_kids
 * @property {?boolean} is_one_off
 */

/**
 * Filter sidebar for the transactions view.
 *
 * @component
 * @param {Object} props
 * @param {Array<Object>} [props.accounts=[]]
 * @param {Array<Object>} [props.parties=[]]
 * @param {Array<Object>} [props.categories=[]]
 * @param {Array<Object>} [props.subCategories=[]]
 * @param {Array<Object>} [props.types=[]]
 * @param {(filters: Filters) => void} props.onFilterChange
 *        Called whenever the internal filter state changes (via
 *        `useEffect`), including on initial mount.
 * @returns {JSX.Element}
 */
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

  /** Local filter state. */
  const [filters, setFilters] = useState({
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

  // ── Cascading filtered options ────────────────────────────────────
  const [filteredSubCategories, setFilteredSubCategories] = useState(subCategories);
  const [filteredTypes, setFilteredTypes] = useState(types);
  const [filteredParties, setFilteredParties] = useState(parties);

  // ── Debounced text inputs ─────────────────────────────────────────
  const [descriptionInput, setDescriptionInput] = useState('');
  const [cleanedDescriptionInput, setCleanedDescriptionInput] = useState('');

  // ── Effects: cascade filters when a parent changes ────────────────

  /** Narrow sub-categories when category changes. */
  useEffect(() => {
    if (filters.category_id) {
      const filtered = subCategories.filter((sc) => sc.category_id === filters.category_id);
      setFilteredSubCategories(filtered);

      if (filters.sub_category_id && !filtered.find((sc) => sc.id === filters.sub_category_id)) {
        setFilters((prev) => ({ ...prev, sub_category_id: null, type_id: null, party_id: null }));
      }
    } else {
      setFilteredSubCategories(subCategories);
    }
  }, [filters.category_id, subCategories]);

  /** Narrow types when sub-category or category changes. */
  useEffect(() => {
    if (filters.sub_category_id) {
      const filtered = types.filter((t) => t.sub_category_id === filters.sub_category_id);
      setFilteredTypes(filtered);

      if (filters.type_id && !filtered.find((t) => t.id === filters.type_id)) {
        setFilters((prev) => ({ ...prev, type_id: null, party_id: null }));
      }
    } else if (filters.category_id) {
      const subCatIds = filteredSubCategories.map((sc) => sc.id);
      setFilteredTypes(types.filter((t) => subCatIds.includes(t.sub_category_id)));
    } else {
      setFilteredTypes(types);
    }
  }, [filters.sub_category_id, filters.category_id, filteredSubCategories, types]);

  /** Narrow parties when type / sub-category / category changes. */
  useEffect(() => {
    if (filters.type_id) {
      const filtered = parties.filter((p) => p.type_id === filters.type_id);
      setFilteredParties(filtered);

      if (filters.party_id && !filtered.find((p) => p.id === filters.party_id)) {
        setFilters((prev) => ({ ...prev, party_id: null }));
      }
    } else if (filters.sub_category_id || filters.category_id) {
      const typeIds = filteredTypes.map((t) => t.id);
      setFilteredParties(parties.filter((p) => typeIds.includes(p.type_id)));
    } else {
      setFilteredParties(parties);
    }
  }, [filters.type_id, filters.sub_category_id, filters.category_id, filteredTypes, parties]);

  /** Propagate filter changes to parent. */
  useEffect(() => {
    onFilterChange(filters);
  }, [filters, onFilterChange]);

  // ── Handlers ──────────────────────────────────────────────────────

  /**
   * Generic filter setter with id coercion and cascading clears.
   * @param {string} key
   * @param {*} value
   */
  const handleFilterChange = (key, value) => {
    let processedValue = value;

    if (['account_id', 'party_id', 'category_id', 'sub_category_id', 'type_id'].includes(key)) {
      if (value === '' || value === null || value === undefined) {
        processedValue = null;
      } else {
        processedValue = parseInt(value, 10);
      }
    }

    if (key === 'category_id') {
      setFilters((prev) => ({
        ...prev,
        [key]: processedValue,
        sub_category_id: null,
        type_id: null,
        party_id: null,
      }));
    } else if (key === 'sub_category_id') {
      setFilters((prev) => ({
        ...prev,
        [key]: processedValue,
        type_id: null,
        party_id: null,
      }));
    } else if (key === 'type_id') {
      setFilters((prev) => ({
        ...prev,
        [key]: processedValue,
        party_id: null,
      }));
    } else {
      setFilters((prev) => ({ ...prev, [key]: processedValue }));
    }
  };

  /**
   * Boolean checkbox handler — `true` or `null` (never `false`).
   */
  const handleCheckboxFilter = (key, checked) => {
    setFilters((prev) => ({ ...prev, [key]: checked ? true : null }));
  };

  /** Commit description filter on blur. */
  const handleDescriptionBlur = () => {
    const trimmedValue = descriptionInput.trim();
    setFilters((prev) => ({
      ...prev,
      description: trimmedValue === '' ? null : trimmedValue,
    }));
  };

  /** Commit cleaned description filter on blur. */
  const handleCleanedDescriptionBlur = () => {
    const trimmedValue = cleanedDescriptionInput.trim();
    setFilters((prev) => ({
      ...prev,
      cleaned_description: trimmedValue === '' ? null : trimmedValue,
    }));
  };

  /** Blur on Enter so the filter is applied immediately. */
  const handleDescriptionKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur();
    }
  };

  /** Reset all filters to default values. */
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
            disabled={
              !filters.type_id &&
              !filters.sub_category_id &&
              !filters.category_id &&
              filteredParties.length === 0
            }
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