/**
 * @file NodeStats.jsx
 * Compact stat cards: transaction count, total value, child count.
 */

import { CHILD_LEVEL_LABELS } from '../constants';
import { formatCurrency, formatCount } from '../format';
import './NodeStats.css';

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
    <div className="node-stats">
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
    <div className="node-stats__card">
      <div className="node-stats__label">{label}</div>
      <div
        className={
          'node-stats__value' + (modifier ? ` node-stats__value--${modifier}` : '')
        }
      >
        {value}
      </div>
    </div>
  );
}