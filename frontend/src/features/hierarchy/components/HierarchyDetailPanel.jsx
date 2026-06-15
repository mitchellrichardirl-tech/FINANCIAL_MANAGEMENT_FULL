/**
 * @file HierarchyDetailPanel.jsx
 * Right-hand panel showing the selected node's breadcrumb, header,
 * aggregate stats, and children table.
 */

import BreadcrumbNav from './BreadcrumbNav';
import NodeStats from './NodeStats';
import ChildrenTable from './ChildrenTable';
import { LEVEL_LABELS, CHILD_LEVEL_LABELS } from '../constants';

/**
 * @component
 * @param {Object} props
 * @param {?{node: Object, children: Object[], child_level: ?string}} props.detail
 * @param {boolean} props.loading
 * @param {(crumb: {level: string, id: number}) => void} props.onBreadcrumbNav
 * @param {(childId: number) => void} props.onDrillDown
 * @param {() => void} props.onEdit
 * @param {() => void} props.onDelete
 * @param {() => void} props.onCreateChild
 * @returns {JSX.Element}
 */
export default function HierarchyDetailPanel({
  detail,
  loading,
  onBreadcrumbNav,
  onDrillDown,
  onEdit,
  onDelete,
  onCreateChild,
}) {
  if (loading) {
    return <div className="py-8 text-[#888]">Loading…</div>;
  }

  if (!detail) {
    return (
      <div className="py-8 text-[#888]">
        <h2 className="text-[#333]">Select a node</h2>
        <p>Choose a category, sub-category, or type from the tree to view its details.</p>
      </div>
    );
  }

  const { node, children, child_level } = detail;
  const isLocked = node.is_unknown;

  return (
    <div>
      <BreadcrumbNav
        breadcrumb={node.breadcrumb}
        currentName={node.name}
        onNavigate={onBreadcrumbNav}
      />

      <header className="flex items-start justify-between gap-4 mt-3 mb-2">
        <div className="flex items-center gap-3 min-w-0">
          <span className="inline-block px-[0.6rem] py-[0.15rem] rounded-full bg-[#e8eef6] text-[#456] text-xs font-semibold uppercase tracking-[0.03em] shrink-0">
            {LEVEL_LABELS[node.level]}
          </span>
          <h2 className="text-2xl overflow-hidden text-ellipsis">
            {node.name}
          </h2>
          {isLocked && (
            <span
              className="text-base opacity-70"
              title="System-managed — cannot be edited or deleted"
            >
              🔒
            </span>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            className="btn-secondary"
            onClick={onEdit}
            disabled={isLocked}
            title={isLocked ? 'Cannot edit the Unknown node' : 'Edit name, description, or parent'}
          >
            Edit
          </button>
          <button
            className="btn-danger"
            onClick={onDelete}
            disabled={isLocked}
            title={isLocked ? 'Cannot delete the Unknown node' : 'Delete this node and all empty descendants'}
          >
            Delete
          </button>
        </div>
      </header>

      {node.description && (
        <p className="mb-5 text-[#666] max-w-[60ch]">{node.description}</p>
      )}

      <NodeStats
        transactionCount={node.transaction_count}
        totalValue={node.total_value}
        childCount={node.child_count}
        childLevel={child_level}
      />

      {child_level && (
        <ChildrenTable
          children={children}
          childLevel={child_level}
          onDrillDown={onDrillDown}
          onCreateChild={onCreateChild}
        />
      )}

      {!child_level && (
        <div className="mt-6 p-4 bg-[#f5f7fa] rounded-md text-[#666] text-[0.9rem]">
          Parties are the leaf level of the hierarchy and have no children.
        </div>
      )}
    </div>
  );
}