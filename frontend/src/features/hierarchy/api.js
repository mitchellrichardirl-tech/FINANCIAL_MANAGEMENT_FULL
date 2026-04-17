/**
 * @file api.js
 * API client functions for the category hierarchy manager.
 *
 * All endpoints are level-agnostic — `level` is one of:
 * `'category' | 'sub_category' | 'type' | 'party'`.
 */

import { apiCall, unwrap } from '@/lib/apiClient';

/**
 * Fetch the full hierarchy tree (categories → sub_categories → types).
 * Parties are excluded — they load via {@link getNodeDetail} when a
 * type node is selected.
 *
 * @returns {Promise<Array>} Array of category nodes with nested children.
 */
export async function getHierarchyTree() {
  const response = await apiCall('/hierarchy/tree');
  return unwrap(response, 'data');
}

/**
 * Fetch a single node's detail, stats, breadcrumb, and children.
 *
 * @param {string} level - Hierarchy level.
 * @param {number} id - Node primary key.
 * @returns {Promise<{node: Object, children: Object[], child_level: ?string}>}
 */
export async function getNodeDetail(level, id) {
  const response = await apiCall(`/hierarchy/${level}/${id}`);
  return unwrap(response, 'data');
}