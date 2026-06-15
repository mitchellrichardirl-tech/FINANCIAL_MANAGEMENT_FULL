from flask import Blueprint, request, jsonify

from src.categorizer.party_matcher import PartyMatcherReadOnly
from src.database.repositories.categories import (
  CategoryRepository,
  RemapConflictError,
)
from src.api.utils.response_helpers import success_response
from src.api.utils.route_helpers import handle_errors, require_json
from src.api.utils.errors import required, invalid_value, not_found
from src.api.utils.validators import RequestValidator, parse_int
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('categories', __name__)
logger = ContextLogger(__name__)


# ==================== Helper Functions ====================

def validate_create_category(data: dict) -> tuple[bool, dict, str | None]:
    """Validate category creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('category',
        validator.field('category').required().strip_string())

    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_create_sub_category(data: dict) -> tuple[bool, dict, str | None]:
    """Validate sub-category creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('sub_category',
        validator.field('sub_category').required().strip_string())
    validator.validate_field('category_id',
        validator.field('category_id').required().transform(parse_int).in_range(min_val=1))

    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_create_type(data: dict) -> tuple[bool, dict, str | None]:
    """Validate type creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('type',
        validator.field('type').required().strip_string())
    validator.validate_field('sub_category_id',
        validator.field('sub_category_id').required().transform(parse_int).in_range(min_val=1))

    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_create_party(data: dict) -> tuple[bool, dict, str | None]:
    """Validate party creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('name',
        validator.field('name').required().strip_string())
    validator.validate_field('type_id',
        validator.field('type_id').optional().transform(parse_int).in_range(min_val=1))

    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None

def validate_update(data: dict, name_field: str) -> tuple[bool, dict, str | None]:
    """Validate an update payload for any hierarchy level.

    Extracts ``name_field`` and ``description`` from *data*.
    At least one must be present.  Unknown keys are ignored.

    Returns:
        (is_valid, validated_dict, error_message)
    """
    validated = {}

    if name_field in data:
        val = data[name_field]
        if val is None or not str(val).strip():
            return False, {}, f'{name_field} cannot be empty'
        validated[name_field] = str(val).strip()

    if 'description' in data:
        desc = data['description']
        if desc is not None:
            desc = str(desc).strip() or None
        validated['description'] = desc          # None ⇒ clear in DB

    if not validated:
        return False, {}, (
            f'No updatable fields provided. '
            f'Supply at least one of: {name_field}, description'
        )

    return True, validated, None


def validate_remap(data: dict, parent_field: str) -> tuple[bool, int, str | None]:
    """Validate a remap payload — a single required positive-integer
    parent id.

    Returns:
        (is_valid, parent_id, error_message)
    """
    if not data or parent_field not in data:
        return False, 0, f'{parent_field} is required'

    value = data[parent_field]
    if not isinstance(value, int) or value < 1:
        return False, 0, f'{parent_field} must be a positive integer'

    return True, value, None
# ==================== Categories ====================

@bp.route('/categories', methods=['GET'])
@handle_errors(entity='Category')
@log_route(logger)
def get_categories():
    """Get all categories."""
    repo = CategoryRepository()
    categories = repo.get_all_categories()

    logger.info(f"Retrieved {len(categories)} categories")
    return success_response(data=categories)


@bp.route('/categories', methods=['POST'])
@handle_errors(entity='Category')
@require_json
@log_route(logger)
def create_category():
    """Create a new category."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    is_valid, validated_data, error_msg = validate_create_category(data)
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    category_id = repo.add_category(**validated_data)
    category = repo.get_category_by_id(category_id)

    logger.info(f"Created category with id: {category_id}")
    return success_response(
        data=category,
        message='Category created successfully',
        status_code=201
    )


@bp.route('/categories/<int:category_id>', methods=['DELETE'])
@handle_errors(entity='Category')
@log_route(logger)
def delete_category(category_id: int):
    """Delete a category."""
    repo = CategoryRepository()
    deleted = repo.delete_category(category_id)

    if not deleted:
        raise not_found('Category', category_id)

    return success_response(
        data={'deleted_id': category_id},
        message=f'Category {category_id} deleted successfully'
    )


@bp.route('/categories/<int:category_id>', methods=['PUT'])
@handle_errors(entity='Category')
@require_json
@log_route(logger)
def update_category(category_id: int):
    """Update a category's name and/or description."""
    data = request.get_json()
    if not data:
        raise required('Request body')

    is_valid, validated, error_msg = validate_update(data, 'category')
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    updated = repo.update_category(category_id, **validated)

    if updated is None:
        raise not_found('Category', category_id)

    logger.info(f"Updated category {category_id}")
    return success_response(
        data=updated,
        message='Category updated successfully'
    )


# ==================== Sub-categories ====================

@bp.route('/sub-categories', methods=['GET'])
@handle_errors(entity='Sub-category')
@log_route(logger)
def get_sub_categories():
    """Get all sub-categories, optionally filtered by category."""
    repo = CategoryRepository()
    category_id = request.args.get('category_id', type=int)

    if category_id:
        logger.debug(f"Filtering by category_id: {category_id}")
        sub_categories = repo.get_sub_categories_by_category(category_id)
    else:
        sub_categories = repo.get_all_sub_categories()

    logger.info(f"Retrieved {len(sub_categories)} sub-categories")
    return success_response(data=sub_categories)


@bp.route('/sub-categories', methods=['POST'])
@handle_errors(entity='Sub-category')
@require_json
@log_route(logger)
def create_sub_category():
    """Create a new sub-category."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    is_valid, validated_data, error_msg = validate_create_sub_category(data)
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    sub_category_id = repo.add_sub_category(**validated_data)
    sub_category = repo.get_sub_category_by_id(sub_category_id)

    logger.info(
        f"Created sub-category with id: {sub_category_id} "
        f"under category_id: {validated_data['category_id']}"
    )
    return success_response(
        data=sub_category,
        message='Sub-category created successfully',
        status_code=201
    )


@bp.route('/sub-categories/<int:sub_category_id>', methods=['DELETE'])
@handle_errors(entity='Sub-category')
@log_route(logger)
def delete_sub_category(sub_category_id: int):
    """Delete a sub-category."""
    repo = CategoryRepository()
    deleted = repo.delete_sub_category(sub_category_id)

    if not deleted:
        raise not_found('Sub-category', sub_category_id)

    return success_response(
        data={'deleted_id': sub_category_id},
        message=f'Sub-category {sub_category_id} deleted successfully'
    )


@bp.route('/sub-categories/<int:sub_category_id>', methods=['PUT'])
@handle_errors(entity='Sub-category')
@require_json
@log_route(logger)
def update_sub_category(sub_category_id: int):
    """Update a sub-category's name and/or description."""
    data = request.get_json()
    if not data:
        raise required('Request body')

    if 'category_id' in data:
        raise invalid_value(
            'Cannot change category_id here. '
            'Use PUT /sub-categories/<id>/remap instead.',
            field='category_id'
        )

    is_valid, validated, error_msg = validate_update(data, 'sub_category')
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    updated = repo.update_sub_category(sub_category_id, **validated)

    if updated is None:
        raise not_found('Sub-category', sub_category_id)

    logger.info(f"Updated sub-category {sub_category_id}")
    return success_response(
        data=updated,
        message='Sub-category updated successfully'
    )


@bp.route('/sub-categories/<int:sub_category_id>/remap', methods=['PUT'])
@handle_errors(entity='Sub-category')
@require_json
@log_route(logger)
def remap_sub_category(sub_category_id: int):
    """Move a sub-category to a different category.

    Returns 409 if the target category already contains a sub-category
    with the same name.
    """
    data = request.get_json()
    if not data:
        raise required('Request body')

    is_valid, new_category_id, error_msg = validate_remap(data, 'category_id')
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    try:
        result = repo.remap_sub_category(sub_category_id, new_category_id)
    except RemapConflictError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': {'conflicting_id': e.conflicting_id},
        }), 409

    logger.info(
        f"Remap sub-category {sub_category_id}: {result['action']}"
    )
    return success_response(data=result)


# ==================== Types ====================

@bp.route('/types', methods=['GET'])
@handle_errors(entity='Type')
@log_route(logger)
def get_types():
    """Get all types, optionally filtered by sub-category."""
    repo = CategoryRepository()
    sub_category_id = request.args.get('sub_category_id', type=int)

    if sub_category_id:
        logger.debug(f"Filtering by sub_category_id: {sub_category_id}")
        types = repo.get_types_by_sub_category(sub_category_id)
    else:
        types = repo.get_all_types()

    logger.info(f"Retrieved {len(types)} types")
    return success_response(data=types)


@bp.route('/types', methods=['POST'])
@handle_errors(entity='Type')
@require_json
@log_route(logger)
def create_type():
    """Create a new type."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    is_valid, validated_data, error_msg = validate_create_type(data)
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    type_name = validated_data.pop('type')
    type_id = repo.add_type(type_name=type_name, **validated_data)
    type_obj = repo.get_type_by_id(type_id)

    logger.info(
        f"Created type with id: {type_id} "
        f"under sub_category_id: {validated_data['sub_category_id']}"
    )
    return success_response(
        data=type_obj,
        message='Type created successfully',
        status_code=201
    )


@bp.route('/types/<int:type_id>', methods=['DELETE'])
@handle_errors(entity='Type')
@log_route(logger)
def delete_type(type_id: int):
    """Delete a type."""
    repo = CategoryRepository()
    deleted = repo.delete_type(type_id)

    if not deleted:
        raise not_found('Type', type_id)

    return success_response(
        data={'deleted_id': type_id},
        message=f'Type {type_id} deleted successfully'
    )


@bp.route('/types/<int:type_id>', methods=['PUT'])
@handle_errors(entity='Type')
@require_json
@log_route(logger)
def update_type(type_id: int):
    """Update a type's name and/or description."""
    data = request.get_json()
    if not data:
        raise required('Request body')

    if 'sub_category_id' in data:
        raise invalid_value(
            'Cannot change sub_category_id here. '
            'Use PUT /types/<id>/remap instead.',
            field='sub_category_id'
        )

    is_valid, validated, error_msg = validate_update(data, 'type')
    if not is_valid:
        raise invalid_value(error_msg)

    # DB column is "type" but Python param is "type_name"
    if 'type' in validated:
        validated['type_name'] = validated.pop('type')

    repo = CategoryRepository()
    updated = repo.update_type(type_id, **validated)

    if updated is None:
        raise not_found('Type', type_id)

    logger.info(f"Updated type {type_id}")
    return success_response(
        data=updated,
        message='Type updated successfully'
    )


@bp.route('/types/<int:type_id>/remap', methods=['PUT'])
@handle_errors(entity='Type')
@require_json
@log_route(logger)
def remap_type(type_id: int):
    """Move a type to a different sub-category.

    Returns 409 if the target sub-category already contains a type
    with the same name.
    """
    data = request.get_json()
    if not data:
        raise required('Request body')

    is_valid, new_sub_category_id, error_msg = validate_remap(data, 'sub_category_id')
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    try:
        result = repo.remap_type(type_id, new_sub_category_id)
    except RemapConflictError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': {'conflicting_id': e.conflicting_id},
        }), 409

    logger.info(f"Remap type {type_id}: {result['action']}")
    return success_response(data=result)


# ==================== Parties ====================

@bp.route('/parties', methods=['GET'])
@handle_errors(entity='Party')
@log_route(logger)
def get_parties():
    """Get all parties with transaction counts, optionally filtered by type."""
    repo = CategoryRepository()
    type_id = request.args.get('type_id', type=int)

    if type_id:
        logger.debug(f"Filtering by type_id: {type_id}")
        parties = repo.get_parties_by_type(type_id)
    else:
        parties = repo.get_all_parties_with_transaction_counts()

    logger.info(f"Retrieved {len(parties)} parties")
    return success_response(data=parties)


@bp.route('/parties', methods=['POST'])
@handle_errors(entity='Party')
@require_json
@log_route(logger)
def create_party():
    """Create a new party."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    is_valid, validated_data, error_msg = validate_create_party(data)
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()

    if 'type_id' in validated_data:
        logger.debug(f"Creating party with type_id: {validated_data['type_id']}")
        party_id = repo.add_party(**validated_data)
    else:
        logger.debug("No type_id provided, assigning unknown type")
        validated_data.pop('type_id', None)
        party_id = repo.add_party_unknown_type(**validated_data)

    party = repo.get_party_by_id(party_id)

    logger.info(f"Created party with id: {party_id}")
    return success_response(
        data=party,
        message='Party created successfully',
        status_code=201
    )


@bp.route('/parties/<int:party_id>', methods=['DELETE'])
@handle_errors(entity='Party')
@log_route(logger)
def delete_party(party_id: int):
    """Delete a party."""
    repo = CategoryRepository()
    deleted = repo.delete_party(party_id)

    if not deleted:
        raise not_found('Party', party_id)

    return success_response(
        data={'deleted_id': party_id},
        message=f'Party {party_id} deleted successfully'
    )


@bp.route('/parties/<int:party_id>', methods=['PUT'])
@handle_errors(entity='Party')
@require_json
@log_route(logger)
def update_party_details(party_id: int):
    """Update a party's name and/or description."""
    data = request.get_json()
    if not data:
        raise required('Request body')

    if 'type_id' in data:
        raise invalid_value(
            'Cannot change type_id here. '
            'Use PUT /parties/<id>/remap instead.',
            field='type_id'
        )

    is_valid, validated, error_msg = validate_update(data, 'name')
    if not is_valid:
        raise invalid_value(error_msg)

    repo = CategoryRepository()
    updated = repo.update_party(party_id, **validated)

    if updated is None:
        raise not_found('Party', party_id)

    logger.info(f"Updated party {party_id}")
    return success_response(
        data=updated,
        message='Party updated successfully'
    )


@bp.route('/parties/<int:party_id>/transactions', methods=['GET'])
@handle_errors(entity='Party')
@log_route(logger)
def get_party_transactions(party_id: int):
    """Get all transactions for a specific party."""
    repo = CategoryRepository()

    party = repo.get_party_by_id(party_id)
    if party is None:
        raise not_found('Party', party_id)

    transactions = repo.get_transactions_by_party(party_id)

    logger.info(f"Retrieved {len(transactions)} transactions for party {party_id}")
    return success_response(data=transactions)


@bp.route('/parties/<int:party_id>/remap', methods=['PUT'])
@handle_errors(entity='Party')
@require_json
@log_route(logger)
def remap_party(party_id: int):
    """Remap a party to a different type in the category hierarchy."""
    data = request.get_json()

    if not data or 'type_id' not in data:
        raise required('type_id')

    new_type_id = data['type_id']

    if not isinstance(new_type_id, int) or new_type_id < 1:
        raise invalid_value('type_id must be a positive integer', field='type_id')

    repo = CategoryRepository()
    result = repo.remap_party(party_id, new_type_id)

    return success_response(data=result)

@bp.route('/parties/match', methods=['GET'])
@handle_errors(entity='Party')
@log_route(logger)
def match_party():
    """Fuzzy-match a name to an existing party without side effects.

    Used by the receipt workflow to pre-select a party from the
    OCR-extracted vendor string. Unlike the statement-import path,
    this never creates new parties — it only reports the best
    existing match, if any.

    Query params:
        name: The vendor / party name to match. Required.

    Response::

        {
          "match": { "party_id": 42, "score": 87 } | null
        }
    """
    name = (request.args.get('name') or '').strip()
    if not name:
        raise required('name')

    result = PartyMatcherReadOnly().find_match(name)

    if result is None:
        return success_response(data={'match': None})

    party_id, score = result
    return success_response(
        data={'match': {'party_id': party_id, 'score': score}}
    )