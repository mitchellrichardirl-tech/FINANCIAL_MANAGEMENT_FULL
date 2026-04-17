/**
 * @file CategoryHierarchyPage.jsx
 * Top-level page for browsing and managing the four-level category
 * hierarchy (category → sub_category → type → party).
 *
 * Layout:
 *   ┌──────────────┬──────────────────────────────┐
 *   │ HierarchyTree │ HierarchyDetailPanel         │
 *   │ (sidebar)     │ (breadcrumb + stats + table) │
 *   └──────────────┴──────────────────────────────┘
 *
 * Responsibilities:
 *  - Load the tree on mount and own it as state.
 *  - Track the selected node (level + id).
 *  - Fetch node detail when selection changes.
 *  - Coordinate drill-down (double-click child) and drill-up
 *    (breadcrumb click).
 */

import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/components/ToastContext';
import { getHierarchyTree, getNodeDetail } from './api';
import HierarchyTree from './components/HierarchyTree';
import HierarchyDetailPanel from './components/HierarchyDetailPanel';
import { createLogger } from '@/lib/logger';
import './CategoryHierarchyPage.css';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CategoryHierarchyPage');

/**
 * Category hierarchy manager page.
 *
 * @component
 * @returns {JSX.Element}
 */
export default function CategoryHierarchyPage() {
  const { addToast } = useToast();

  // ── Tree state ────────────────────────────────────────────────────
  const [tree, setTree] = useState([]);
  const [treeLoading, setTreeLoading] = useState(true);

  // ── Selection state ───────────────────────────────────────────────
  /**
   * Currently selected node, or null for the empty/landing state.
   * @type {?{level: string, id: number}}
   */
  const [selected, setSelected] = useState(null);

  // ── Detail state ──────────────────────────────────────────────────
  /**
   * Detail payload for the selected node.
   * @type {?{node: Object, children: Object[], child_level: ?string}}
   */
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ── Effects ───────────────────────────────────────────────────────

  useEffect(() => {
    loadTree();
  }, []);

  useEffect(() => {
    if (selected) {
      loadDetail(selected.level, selected.id);
    } else {
      setDetail(null);
    }
  }, [selected]);

  // ── Loaders ───────────────────────────────────────────────────────

  /** Fetch the full tree for the sidebar. */
  const loadTree = async () => {
    setTreeLoading(true);
    try {
      const data = await getHierarchyTree();
      setTree(data);
      logger.debug(`Loaded tree: ${data.length} root categories`);
    } catch (err) {
      logger.error('Failed to load hierarchy tree', err);
      addToast({
        message: `Failed to load hierarchy: ${err.userMessage || err.message}`,
        type: 'error',
      });
      setTree([]);
    } finally {
      setTreeLoading(false);
    }
  };

  /** Fetch detail for a single node. */
  const loadDetail = async (level, id) => {
    setDetailLoading(true);
    try {
      const data = await getNodeDetail(level, id);
      setDetail(data);
      logger.debug(`Loaded ${level} ${id}: ${data.node.name}`);
    } catch (err) {
      logger.error(`Failed to load ${level} ${id}`, err);
      addToast({
        message: `Failed to load node: ${err.userMessage || err.message}`,
        type: 'error',
      });
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  // ── Navigation handlers ───────────────────────────────────────────

  /**
   * Select a node (from tree click, breadcrumb click, or child
   * double-click). Passing null clears the selection.
   *
   * @param {?string} level
   * @param {?number} id
   */
  const handleSelect = useCallback((level, id) => {
    if (level == null || id == null) {
      setSelected(null);
      return;
    }
    setSelected({ level, id });
  }, []);

  /**
   * Drill down into a child row (double-click in the children table).
   * The child's level is the current detail's `child_level`.
   *
   * @param {number} childId
   */
  const handleDrillDown = useCallback(
    (childId) => {
      if (!detail?.child_level) return; // party has no children
      handleSelect(detail.child_level, childId);
    },
    [detail, handleSelect]
  );

  /**
   * Navigate to an ancestor via breadcrumb click.
   *
   * @param {{level: string, id: number}} crumb
   */
  const handleBreadcrumbNav = useCallback(
    (crumb) => {
      handleSelect(crumb.level, crumb.id);
    },
    [handleSelect]
  );

  // ── Mutation placeholders (wired in Steps 5–10) ───────────────────

  const handleEdit = useCallback(() => {
    addToast({ message: 'Edit not implemented yet', type: 'info' });
  }, [addToast]);

  const handleDelete = useCallback(() => {
    addToast({ message: 'Delete not implemented yet', type: 'info' });
  }, [addToast]);

  const handleCreateChild = useCallback(() => {
    addToast({ message: 'Create not implemented yet', type: 'info' });
  }, [addToast]);

  return (
    <div className="hierarchy-page">
      <div className="hierarchy-page__header">
        <h1>Category Hierarchy</h1>
      </div>

      <div className="hierarchy-page__body">
        <aside className="hierarchy-page__sidebar">
          <HierarchyTree
            tree={tree}
            loading={treeLoading}
            selected={selected}
            onSelect={handleSelect}
          />
        </aside>

        <section className="hierarchy-page__detail">
          <HierarchyDetailPanel
            detail={detail}
            loading={detailLoading}
            onBreadcrumbNav={handleBreadcrumbNav}
            onDrillDown={handleDrillDown}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onCreateChild={handleCreateChild}
          />
        </section>
      </div>
    </div>
  );
}