/**
 * @file api.js
 * API client functions for the category hierarchy manager.
 *
 * All endpoints are level-agnostic — `level` is one of:
 * `'category' | 'sub_category' | 'type' | 'party'`.
 */

import { apiCall, unwrap } from '@/lib/apiClient';

/** URL path fragment per level (pluralised, kebab-cased). */
const LEVEL_PATHS = {
  category: 'categories',
  sub_category: 'sub-categories',
  type: 'types',
  party: 'parties',
};

/**
 * Backend field name for the "name" column, per level.
 * The UI uses `name` uniformly; this maps it to the DB column name.
 */
const LEVEL_NAME_FIELDS = {
  category: 'category',
  sub_category: 'sub_category',
  type: 'type',
  party: 'name',
};

/**
 * Backend field name for the parent-FK, per level.
 * Categories have no parent.
 */
const LEVEL_PARENT_FIELDS = {
  sub_category: 'category_id',
  type: 'sub_category_id',
  party: 'type_id',
};

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

/**
 * Update a node's name and/or description.
 *
 * Only send the fields you want to change. Pass `description: null`
 * (not `undefined`) to explicitly clear a description.
 *
 * @param {string} level
 * @param {number} id
 * @param {{name?: string, description?: string|null}} fields
 * @returns {Promise<Object>} The updated node.
 */
export async function updateNode(level, id, { name, description } = {}) {
  const path = LEVEL_PATHS[level];
  if (!path) throw new Error(`Unknown level: ${level}`);

  const body = {};
  if (name !== undefined) body[LEVEL_NAME_FIELDS[level]] = name;
  if (description !== undefined) body.description = description;

  const response = await apiCall(`/${path}/${id}`, {
    method: 'PUT',
    body,
  });
  return unwrap(response, 'data');
}

/**
 * Move a node to a different parent.
 *
 * For sub-category/type this may reject with a 409 conflict if the
 * target parent already contains a same-named sibling. For party it
 * silently merges (see backend `remap_party`).
 *
 * @param {string} level  - `sub_category`, `type`, or `party`.
 * @param {number} id
 * @param {number} newParentId
 * @returns {Promise<Object>} `{ action: 'none'|'remapped'|'merged', ... }`
 */
export async function remapNode(level, id, newParentId) {
  const path = LEVEL_PATHS[level];
  const parentField = LEVEL_PARENT_FIELDS[level];
  if (!path) throw new Error(`Unknown level: ${level}`);
  if (!parentField) throw new Error(`Cannot remap a ${level} — no parent level`);

  const response = await apiCall(`/${path}/${id}/remap`, {
    method: 'PUT',
    body: { [parentField]: newParentId },
  });
  return unwrap(response, 'data');
}