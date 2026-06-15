/**
 * @file ChildrenTable.jsx
 * Sortable table of direct children with rolled-up transaction stats.
 * Click a column header to sort; double-click a row to drill down.
 */

import { useState, useMemo } from 'react';
import { LEVEL_LABELS, CHILD_LEVEL_LABELS } from '../constants';
import { formatCurrency, formatCount } from '../format';

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
        className="text-[0.7em] leading-none shrink-0 opacity-25 transition-opacity group-hover:opacity-50"
        aria-hidden="true"
      >
        ⇅
      </span>
    );
  }
  return (
    <span
      className="text-[0.7em] leading-none shrink-0 opacity-85 text-[#2563eb]"
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
  const [sortKey, setSortKey] = useState(null);
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

  /* ── Shared cell classes ─────────────────────────────────────────── */

  const thBase =
    'px-3 py-[0.6rem] border-b border-[#eee] font-semibold text-[#666] text-[0.8rem] uppercase tracking-[0.03em]';
  const tdBase = 'px-3 py-[0.6rem] border-b border-[#eee]';

  /* ── Render ──────────────────────────────────────────────────────── */

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[1.1rem]">
          {heading}{' '}
          <span className="text-[#888] font-normal">({children.length})</span>
        </h3>
        <button className="btn-secondary" onClick={onCreateChild}>
          + New {singular}
        </button>
      </div>

      {children.length === 0 ? (
        <div className="p-6 text-center text-[#888] bg-[#fafafa] border border-dashed border-[#ddd] rounded-md">
          No {heading.toLowerCase()} yet.
        </div>
      ) : (
        <table className="w-full border-collapse text-[0.9rem]">
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
                    className={[
                      thBase,
                      col.numeric ? 'text-right tabular-nums' : 'text-left',
                    ].join(' ')}
                    aria-sort={ariaSrt}
                  >
                    <button
                      type="button"
                      className={[
                        'group cursor-pointer inline-flex items-center gap-[0.35rem] w-full whitespace-nowrap',
                        'outline-none focus-visible:outline-[#2563eb] rounded-[2px]',
                        'hover:text-[#2563eb]',
                        col.numeric ? 'justify-end' : '',
                      ].join(' ')}
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
                className="cursor-pointer hover:bg-[#f5f8fc]"
                title="Double-click to open"
              >
                <td className={`${tdBase} font-medium`}>
                  {child.name}
                </td>
                <td className={`${tdBase} text-[#888] max-w-sm truncate`}>
                  {child.description || '—'}
                </td>
                <td className={`${tdBase} text-right tabular-nums`}>
                  {formatCount(child.transaction_count)}
                </td>
                <td
                  className={[
                    tdBase,
                    'text-right tabular-nums',
                    child.total_value < 0 ? 'text-[#c0392b]' : '',
                    child.total_value > 0 ? 'text-[#27ae60]' : '',
                  ].join(' ')}
                >
                  {formatCurrency(child.total_value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="mt-3 text-[0.8rem] text-[#999]">
        Double-click a row to drill down.
      </div>
    </div>
  );
}