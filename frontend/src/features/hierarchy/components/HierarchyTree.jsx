/**
 * @file HierarchyTree.jsx
 * Collapsible tree sidebar showing categories → sub_categories → types.
 *
 * Each node has an expand/collapse toggle and a clickable label.
 * Clicking the label selects the node; clicking the toggle (or the
 * label of a collapsed node with children) expands it without changing
 * selection.
 *
 * Auto-expands the path to the currently selected node so external
 * navigation (breadcrumb, drill-down) keeps the selection visible.
 */

import { useState, useEffect } from 'react';

/**
 * Build a stable key for a node so we can track expanded state across
 * levels (ids are only unique within a level).
 */
const nodeKey = (level, id) => `${level}:${id}`;

/**
 * Recursively search the tree for the path of node keys leading to the
 * target (level, id). Used to auto-expand ancestors when an external
 * selection (e.g. breadcrumb click) lands on a nested node.
 *
 * @param {Array} nodes
 * @param {string} level
 * @param {number} id
 * @param {string[]} [trail=[]]
 * @returns {?string[]} Array of nodeKeys from root to target, or null.
 */
function findPath(nodes, level, id, trail = []) {
  for (const node of nodes) {
    const key = nodeKey(node.level, node.id);
    const here = [...trail, key];
    if (node.level === level && node.id === id) {
      return here;
    }
    if (node.children?.length) {
      const found = findPath(node.children, level, id, here);
      if (found) return found;
    }
  }
  return null;
}

/**
 * @component
 * @param {Object} props
 * @param {Array} props.tree - Nested tree from the API.
 * @param {boolean} props.loading
 * @param {?{level: string, id: number}} props.selected
 * @param {(level: string, id: number) => void} props.onSelect
 * @returns {JSX.Element}
 */
export default function HierarchyTree({ tree, loading, selected, onSelect }) {
  /**
   * Set of nodeKeys that are currently expanded.
   * Categories start expanded; deeper levels start collapsed.
   */
  const [expanded, setExpanded] = useState(() => new Set());

  // Expand all root categories when the tree first loads / reloads.
  useEffect(() => {
    if (tree.length === 0) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      for (const cat of tree) {
        next.add(nodeKey(cat.level, cat.id));
      }
      return next;
    });
  }, [tree]);

  // Auto-expand ancestors of the selected node so it's visible.
  useEffect(() => {
    if (!selected || tree.length === 0) return;
    const path = findPath(tree, selected.level, selected.id);
    if (!path) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      for (const key of path) next.add(key);
      return next;
    });
  }, [selected, tree]);

  const toggle = (key) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (loading) {
    return <div className="p-4 text-[#888] text-[0.9rem]">Loading…</div>;
  }

  if (tree.length === 0) {
    return <div className="p-4 text-[#888] text-[0.9rem]">No categories yet.</div>;
  }

  return (
    <div className="text-[0.9rem] select-none py-2" role="tree">
      {tree.map((node) => (
        <TreeNode
          key={nodeKey(node.level, node.id)}
          node={node}
          depth={0}
          expanded={expanded}
          selected={selected}
          onToggle={toggle}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

/**
 * Single recursive tree node.
 *
 * @component
 * @param {Object} props
 * @param {{id: number, name: string, level: string, children: Array}} props.node
 * @param {number} props.depth - Nesting level (0-indexed) for indentation.
 * @param {Set<string>} props.expanded
 * @param {?{level: string, id: number}} props.selected
 * @param {(key: string) => void} props.onToggle
 * @param {(level: string, id: number) => void} props.onSelect
 */
function TreeNode({ node, depth, expanded, selected, onToggle, onSelect }) {
  const key = nodeKey(node.level, node.id);
  const hasChildren = node.children && node.children.length > 0;
  const isExpanded = expanded.has(key);
  const isSelected =
    selected && selected.level === node.level && selected.id === node.id;
  const isUnknown = node.name === 'Unknown';

  const handleToggleClick = (e) => {
    e.stopPropagation();
    if (hasChildren) onToggle(key);
  };

  const handleLabelClick = () => {
    onSelect(node.level, node.id);
  };

  return (
    <div role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className={[
          'flex items-center gap-[0.35rem] py-1 pr-3 cursor-pointer border-l-[3px] whitespace-nowrap',
          isSelected
            ? 'bg-[#dceaf9] border-l-[#2b7de9] font-medium hover:bg-[#dceaf9]'
            : 'border-transparent hover:bg-[#eef3f8]',
        ].join(' ')}
        style={{ paddingLeft: `${0.5 + depth * 1.25}rem` }}
        onClick={handleLabelClick}
      >
        <span
          className={[
            'inline-flex w-4 justify-center text-[#888] text-xs shrink-0',
            hasChildren ? 'hover:text-[#222]' : 'cursor-default opacity-40',
          ].join(' ')}
          onClick={handleToggleClick}
          aria-hidden="true"
        >
          {hasChildren ? (isExpanded ? '▾' : '▸') : '·'}
        </span>
        <span
          className={[
            'truncate',
            isUnknown ? 'text-[#888] italic' : '',
          ].join(' ')}
          title={node.name}
        >
          {node.name}
        </span>
      </div>

      {hasChildren && isExpanded && (
        <div role="group">
          {node.children.map((child) => (
            <TreeNode
              key={nodeKey(child.level, child.id)}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              selected={selected}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}