/**
 * @file HierarchyDetailPanel.jsx
 * Right-hand panel showing the selected node's breadcrumb, header,
 * aggregate stats, and children table.
 */

import BreadcrumbNav from './BreadcrumbNav';
import NodeStats from './NodeStats';
import ChildrenTable from './ChildrenTable';
import { LEVEL_LABELS, CHILD_LEVEL_LABELS } from '../constants';
import './HierarchyDetailPanel.css';

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
    return <div className="detail-panel__status">Loading…</div>;
  }

  if (!detail) {
    return (
      <div className="detail-panel__empty">
        <h2>Select a node</h2>
        <p>Choose a category, sub-category, or type from the tree to view its details.</p>
      </div>
    );
  }

  const { node, children, child_level } = detail;
  const isLocked = node.is_unknown;

  return (
    <div className="detail-panel">
      <BreadcrumbNav
        breadcrumb={node.breadcrumb}
        currentName={node.name}
        onNavigate={onBreadcrumbNav}
      />

      <header className="detail-panel__header">
        <div className="detail-panel__title">
          <span className="detail-panel__level-badge">
            {LEVEL_LABELS[node.level]}
          </span>
          <h2>{node.name}</h2>
          {isLocked && (
            <span
              className="detail-panel__lock"
              title="System-managed — cannot be edited or deleted"
            >
              🔒
            </span>
          )}
        </div>
        <div className="detail-panel__actions">
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
        <p className="detail-panel__description">{node.description}</p>
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
        <div className="detail-panel__leaf-note">
          Parties are the leaf level of the hierarchy and have no children.
        </div>
      )}
    </div>
  );
}