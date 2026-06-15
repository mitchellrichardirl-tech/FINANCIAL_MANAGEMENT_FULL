/**
 * @file ChildrenTable.jsx
 * Sortable table of direct children with rolled-up transaction stats.
 * Click a column header to sort; double-click a row to drill down.
 */

import { useState, useMemo } from 'react';
import { LEVEL_LABELS, CHILD_LEVEL_LABELS } from '../constants';
import { formatCurrency, formatCount } from '../format';
import './ChildrenTable.css';

/* ── Column definitions ───────────────────────────────────────────── */

const COLUMNS = [
  { key: 'name',              label: 'Name',         numeric: false },
  { key: 'description',       label: 'Description',  numeric: false },
  { key: 'transaction_count', label: 'Transactions',  numeric: true  },
  { key: 'total_value',       label: 'Total value',   numeric: true  },
];

/* ── Sort helpers ─────────────────────────────────────────────────── */

/**
 * Compare two child rows by `key`.
 * Nulls / undefined always sort to the end regardless of direction.
 *
 * @param {Object} a
 * @param {Object} b
 * @param {string} key   - property to compare
 * @param {'asc'|'desc'} dir
 * @returns {number}
 */
function compare(a, b, key, dir) {
  let aVal = a[key];
  let bVal = b[key];

  // Nulls → end
  if (aVal == null && bVal == null) return 0;
  if (aVal == null) return 1;
  if (bVal == null) return -1;

  let cmp;
  if (typeof aVal === 'number' && typeof bVal === 'number') {
    cmp = aVal - bVal;
  } else {
    cmp = String(aVal).localeCompare(String(bVal), undefined, {
      sensitivity: 'base',
    });
  }

  return dir === 'asc' ? cmp : -cmp;
}

/* ── Sub-components ───────────────────────────────────────────────── */

/**
 * Small glyph indicating the current sort state of a column.
 *
 * @param {{ active: boolean, direction: 'asc'|'desc' }} props
 */
function SortIndicator({ active, direction }) {
  if (!active) {
    return (
      <span
        className="children-table__sort-icon children-table__sort-icon--idle"
        aria-hidden="true"
      >
        ⇅
      </span>
    );
  }
  return (
    <span
      className="children-table__sort-icon children-table__sort-icon--active"
      aria-hidden="true"
    >
      {direction === 'asc' ? '▲' : '▼'}
    </span>
  );
}

/* ── Main component ───────────────────────────────────────────────── */

/**
 * @component
 * @param {Object} props
 * @param {Array<{id, name, description, transaction_count, total_value}>} props.children
 * @param {string} props.childLevel
 * @param {(childId: number) => void} props.onDrillDown
 * @param {() => void} props.onCreateChild
 * @returns {JSX.Element}
 */
export default function ChildrenTable({
  children,
  childLevel,
  onDrillDown,
  onCreateChild,
}) {
  const heading  = CHILD_LEVEL_LABELS[childLevel] || 'Children';
  const singular = LEVEL_LABELS[childLevel] || 'item';

  /* ── Sort state ──────────────────────────────────────────────────── */

  /** @type {[string|null, Function]} */
  const [sortKey, setSortKey] = useState(null); // null → API order
  /** @type {['asc'|'desc', Function]} */
  const [sortDir, setSortDir] = useState('asc');

  /**
   * Toggle sort on `key`.
   * First click → ascending; second click on the same column → descending.
   * Clicking a different column resets to ascending.
   */
  const handleSort = (key) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  /** Sorted (or original-order) children for rendering. */
  const sortedChildren = useMemo(() => {
    if (!sortKey) return children;
    return [...children].sort((a, b) => compare(a, b, sortKey, sortDir));
  }, [children, sortKey, sortDir]);

  /* ── Render ──────────────────────────────────────────────────────── */

  return (
    <div className="children-table">
      <div className="children-table__header">
        <h3>
          {heading}{' '}
          <span className="children-table__count">({children.length})</span>
        </h3>
        <button className="btn-secondary" onClick={onCreateChild}>
          + New {singular}
        </button>
      </div>

      {children.length === 0 ? (
        <div className="children-table__empty">
          No {heading.toLowerCase()} yet.
        </div>
      ) : (
        <table className="children-table__table">
          <thead>
            <tr>
              {COLUMNS.map((col) => {
                const active  = sortKey === col.key;
                const ariaSrt = active
                  ? sortDir === 'asc'
                    ? 'ascending'
                    : 'descending'
                  : 'none';

                return (
                  <th
                    key={col.key}
                    className={col.numeric ? 'children-table__num' : undefined}
                    aria-sort={ariaSrt}
                  >
                    <button
                      type="button"
                      className="children-table__sort-btn"
                      onClick={() => handleSort(col.key)}
                      aria-label={`Sort by ${col.label}`}
                    >
                      {col.label}
                      <SortIndicator active={active} direction={sortDir} />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sortedChildren.map((child) => (
              <tr
                key={child.id}
                onDoubleClick={() => onDrillDown(child.id)}
                className="children-table__row"
                title="Double-click to open"
              >
                <td className="children-table__name">{child.name}</td>
                <td className="children-table__desc">
                  {child.description || '—'}
                </td>
                <td className="children-table__num">
                  {formatCount(child.transaction_count)}
                </td>
                <td
                  className={
                    'children-table__num' +
                    (child.total_value < 0
                      ? ' children-table__num--negative'
                      : '') +
                    (child.total_value > 0
                      ? ' children-table__num--positive'
                      : '')
                  }
                >
                  {formatCurrency(child.total_value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="children-table__hint">
        Double-click a row to drill down.
      </div>
    </div>
  );
}