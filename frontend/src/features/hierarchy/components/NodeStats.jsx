/**
 * @file NodeStats.jsx
 * Compact stat cards: transaction count, total value, child count.
 */

import { CHILD_LEVEL_LABELS } from '../constants';
import { formatCurrency, formatCount } from '../format';

/**
 * @component
 * @param {Object} props
 * @param {number} props.transactionCount
 * @param {number} props.totalValue - Signed net (debits negative).
 * @param {?number} props.childCount
 * @param {?string} props.childLevel
 * @returns {JSX.Element}
 */
export default function NodeStats({ transactionCount, totalValue, childCount, childLevel }) {
  return (
    <div className="flex gap-4 mt-4 mb-6 flex-wrap">
      <StatCard label="Transactions" value={formatCount(transactionCount)} />
      <StatCard
        label="Total value"
        value={formatCurrency(totalValue)}
        modifier={totalValue < 0 ? 'negative' : totalValue > 0 ? 'positive' : undefined}
      />
      {childLevel && childCount != null && (
        <StatCard label={CHILD_LEVEL_LABELS[childLevel]} value={formatCount(childCount)} />
      )}
    </div>
  );
}

function StatCard({ label, value, modifier }) {
  return (
    <div className="flex-1 min-w-[140px] px-[1.1rem] py-[0.9rem] bg-white border border-[#e0e0e0] rounded-lg">
      <div className="text-xs uppercase tracking-[0.04em] text-[#888] mb-[0.35rem]">
        {label}
      </div>
      <div
        className={[
          'text-[1.4rem] font-semibold',
          modifier === 'negative' ? 'text-[#c0392b]' :
          modifier === 'positive' ? 'text-[#27ae60]' :
          'text-[#222]',
        ].join(' ')}
      >
        {value}
      </div>
    </div>
  );
}