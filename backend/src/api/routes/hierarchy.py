"""
Blueprint for the category hierarchy manager.

Provides read and write endpoints for navigating and managing the
four-level category hierarchy (category → sub_category → type → party)
from a unified interface.

Routes are registered under ``/api/hierarchy``.

Level-specific column names (``category``, ``sub_category``, ``type``,
``name``) are normalised to a uniform response shape so the frontend
can treat every hierarchy level generically.
"""

from flask import Blueprint, request

from src.database.repositories.categories import CategoryRepository
from src.api.utils.response_helpers import success_response
from src.api.utils.route_helpers import handle_errors, require_json
from src.api.utils.errors import required, invalid_value, not_found
from src.api.utils.validators import RequestValidator, parse_int
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('hierarchy', __name__)
logger = ContextLogger(__name__)


# ==================== Level Configuration ====================

VALID_LEVELS = frozenset({'category', 'sub_category', 'type', 'party'})

LEVEL_DISPLAY_NAMES = {
    'category':     'Category',
    'sub_category': 'Sub-category',
    'type':         'Type',
    'party':        'Party',
}

LEVEL_CONFIG = {
    'category': {
        'name_col':        'category',
        'parent_fk':       None,
        'parent_level':    None,
        'parent_name_col': None,
        'child_level':     'sub_category',
    },
    'sub_category': {
        'name_col':        'sub_category',
        'parent_fk':       'category_id',
        'parent_level':    'category',
        'parent_name_col': 'category_name',
        'child_level':     'type',
    },
    'type': {
        'name_col':        'type',
        'parent_fk':       'sub_category_id',
        'parent_level':    'sub_category',
        'parent_name_col': 'sub_category_name',
        'child_level':     'party',
    },
    'party': {
        'name_col':        'name',
        'parent_fk':       'type_id',
        'parent_level':    'type',
        'parent_name_col': 'type_name',
        'child_level':     None,
    },
}


# ==================== Dispatch Tables ====================

_NODE_FETCHERS = {
    'category':     lambda repo, nid: repo.get_category_with_stats(nid),
    'sub_category': lambda repo, nid: repo.get_sub_category_with_stats(nid),
    'type':         lambda repo, nid: repo.get_type_with_stats(nid),
    'party':        lambda repo, nid: repo.get_party_with_stats(nid),
}

_CHILDREN_FETCHERS = {
    'category':     lambda repo, nid: repo.get_sub_categories_with_stats(nid),
    'sub_category': lambda repo, nid: repo.get_types_with_stats(nid),
    'type':         lambda repo, nid: repo.get_parties_with_stats(nid),
    'party':        lambda repo, nid: [],
}


# ==================== Validation Helpers ====================

def _validate_level(level):
    """Check that ``level`` is a recognised hierarchy level.

    Args:
        level: URL path parameter to validate.

    Raises:
        ApiError (via ``invalid_value``): If *level* is not in
            ``VALID_LEVELS``.
    """
    if level not in VALID_LEVELS:
        raise invalid_value(
            f"Invalid hierarchy level '{level}'. "
            f"Must be one of: {', '.join(sorted(VALID_LEVELS))}",
            field='level'
        )


# ==================== Normalisation Helpers ====================

def _normalise_node(row, level):
    """Map level-specific columns to a uniform node response shape.

    Produces a dict with consistent keys regardless of whether the
    source is a ``categories``, ``sub_categories``, ``types``, or
    ``parties`` row.

    Args:
        row: Dict returned by a ``get_*_with_stats()`` repository
            method.
        level: Hierarchy level of this node.

    Returns:
        Dict with keys: ``id``, ``level``, ``name``, ``description``,
        ``parent_id``, ``parent_level``, ``parent_name``,
        ``transaction_count``, ``total_value``, ``child_count``
        (when present in *row*), ``is_unknown``, ``breadcrumb``.
    """
    cfg = LEVEL_CONFIG[level]

    node = {
        'id':                row['id'],
        'level':             level,
        'name':              row[cfg['name_col']],
        'description':       row.get('description'),
        'transaction_count': row.get('transaction_count', 0),
        'total_value':       row.get('total_value', 0),
        'is_unknown':        row[cfg['name_col']] == 'Unknown',
    }

    # Parent info (None for root-level categories)
    if cfg['parent_fk']:
        node['parent_id']    = row.get(cfg['parent_fk'])
        node['parent_level'] = cfg['parent_level']
        node['parent_name']  = row.get(cfg['parent_name_col'])
    else:
        node['parent_id']    = None
        node['parent_level'] = None
        node['parent_name']  = None

    # child_count is only present on single-node stats queries
    if 'child_count' in row:
        node['child_count'] = row['child_count']

    # Ancestor chain for breadcrumb navigation (root → immediate parent)
    node['breadcrumb'] = _build_breadcrumb(row, level)

    return node


def _normalise_child(row, child_level):
    """Map a child row to a uniform shape for the children list.

    Lighter than ``_normalise_node`` — no parent/breadcrumb data since
    the parent is the currently selected node.

    Args:
        row: Dict from a children-with-stats repository query.
        child_level: Hierarchy level of this child.

    Returns:
        Dict with keys: ``id``, ``name``, ``description``,
        ``transaction_count``, ``total_value``.
    """
    cfg = LEVEL_CONFIG[child_level]
    return {
        'id':                row['id'],
        'name':              row[cfg['name_col']],
        'description':       row.get('description'),
        'transaction_count': row.get('transaction_count', 0),
        'total_value':       row.get('total_value', 0),
    }


def _build_breadcrumb(row, level):
    """Build an ancestor breadcrumb from a node's joined ancestor data.

    Args:
        row: Dict from a ``get_*_with_stats()`` query that includes
            ancestor columns from joins (e.g. ``category_id``,
            ``category_name``, ``sub_category_id``, etc.).
        level: The hierarchy level of the current node.

    Returns:
        List of ``{id, name, level}`` dicts ordered root-first.
        Empty for root-level categories.
    """
    crumbs = []

    if level in ('sub_category', 'type', 'party'):
        cat_id = row.get('category_id')
        if cat_id is not None:
            crumbs.append({
                'id':    cat_id,
                'name':  row.get('category_name'),
                'level': 'category',
            })

    if level in ('type', 'party'):
        sc_id = row.get('sub_category_id')
        if sc_id is not None:
            crumbs.append({
                'id':    sc_id,
                'name':  row.get('sub_category_name'),
                'level': 'sub_category',
            })

    if level == 'party':
        ty_id = row.get('type_id')
        if ty_id is not None:
            crumbs.append({
                'id':    ty_id,
                'name':  row.get('type_name'),
                'level': 'type',
            })

    return crumbs


# ==================== Routes: Read ====================

@bp.route('/tree', methods=['GET'])
@handle_errors(entity='Hierarchy')
@log_route(logger)
def get_tree():
    """Fetch the full hierarchy tree for the sidebar.

    Returns nested categories → sub_categories → types. Parties are
    excluded from the tree (thousands of rows) and loaded on demand
    via the node detail endpoint when a type is selected.

    Response::

        {
            "data": [
                {
                    "id": 1,
                    "name": "Housing",
                    "level": "category",
                    "children": [
                        {
                            "id": 5,
                            "name": "Bills",
                            "level": "sub_category",
                            "children": [
                                {"id": 12, "name": "Streaming", "level": "type", "children": []}
                            ]
                        }
                    ]
                }
            ]
        }
    """
    repo = CategoryRepository()
    tree = repo.get_hierarchy_tree()

    logger.info(f"Retrieved hierarchy tree: {len(tree)} root categories")
    return success_response(data=tree)


@bp.route('/<level>/<int:node_id>', methods=['GET'])
@handle_errors(entity='Hierarchy')
@log_route(logger)
def get_node_detail(level, node_id):
    """Fetch a node's detail with stats and direct children.

    The response provides everything the detail panel needs in one
    round-trip: the node's own properties and aggregate stats, the
    full ancestor breadcrumb, and the children list (each with their
    own rolled-up stats).

    URL params:
        level: One of ``category``, ``sub_category``, ``type``, ``party``.
        node_id: Primary key of the node at that level.

    Response::

        {
            "data": {
                "node": {
                    "id": 12,
                    "level": "type",
                    "name": "Streaming",
                    "description": "Video/music subscriptions",
                    "parent_id": 5,
                    "parent_level": "sub_category",
                    "parent_name": "Bills",
                    "transaction_count": 48,
                    "total_value": -527.88,
                    "child_count": 3,
                    "is_unknown": false,
                    "breadcrumb": [
                        {"id": 2, "name": "Housing", "level": "category"},
                        {"id": 5, "name": "Bills", "level": "sub_category"}
                    ]
                },
                "children": [
                    {"id": 101, "name": "Netflix", "description": null, "transaction_count": 24, "total_value": -263.76},
                    {"id": 102, "name": "Spotify", "description": null, "transaction_count": 24, "total_value": -264.12}
                ],
                "child_level": "party"
            }
        }
    """
    _validate_level(level)

    repo = CategoryRepository()
    display = LEVEL_DISPLAY_NAMES[level]
    cfg = LEVEL_CONFIG[level]

    # Fetch node with aggregate stats
    row = _NODE_FETCHERS[level](repo, node_id)
    if row is None:
        raise not_found(display, node_id)

    # Fetch direct children with their own stats
    child_level = cfg['child_level']
    children_rows = _CHILDREN_FETCHERS[level](repo, node_id)

    # Normalise to uniform response shape
    node = _normalise_node(row, level)
    children = (
        [_normalise_child(r, child_level) for r in children_rows]
        if child_level else []
    )

    logger.info(
        f"Retrieved {display} {node_id}: '{node['name']}' "
        f"({node['transaction_count']} txns, {len(children)} children)"
    )
    return success_response(data={
        'node': node,
        'children': children,
        'child_level': child_level,
    })