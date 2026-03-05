from flask import Blueprint, request

from src.database.repositories.categories import CategoryRepository
from src.api.utils.response_helpers import success_response, error_response
from src.api.utils.route_helpers import handle_exceptions, require_json, handle_database_errors
from src.api.utils.validators import RequestValidator, parse_int, validate_positive_int
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('categories', __name__)
logger = ContextLogger(__name__)


# ==================== Helper Functions ====================

def validate_create_category(data: dict) -> tuple[bool, dict, str]:
    """Validate category creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('category',
        validator.field('category').required().strip_string())

    # Optional description
    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_create_sub_category(data: dict) -> tuple[bool, dict, str]:
    """Validate sub-category creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('sub_category',
        validator.field('sub_category').required().strip_string())
    validator.validate_field('category_id',
        validator.field('category_id').required().transform(parse_int).in_range(min_val=1))

    # Optional description
    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_create_type(data: dict) -> tuple[bool, dict, str]:
    """Validate type creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('type',
        validator.field('type').required().strip_string())
    validator.validate_field('sub_category_id',
        validator.field('sub_category_id').required().transform(parse_int).in_range(min_val=1))

    # Optional description
    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_create_party(data: dict) -> tuple[bool, dict, str]:
    """Validate party creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('name',
        validator.field('name').required().strip_string())
    validator.validate_field('type_id',
        validator.field('type_id').optional().transform(parse_int).in_range(min_val=1))

    # Optional description
    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


# ==================== Categories ====================

@bp.route('/categories', methods=['GET'])
@handle_exceptions(log_prefix="get_categories")
@log_route(logger)
def get_categories():
    """Get all categories."""
    repo = CategoryRepository()
    categories = repo.get_all_categories()

    logger.info(f"Retrieved {len(categories)} categories")
    return success_response(data=categories)


@bp.route('/categories', methods=['POST'])
@handle_database_errors()
@require_json
@log_route(logger)
def create_category():
    """Create a new category."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_create_category(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

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
@handle_database_errors()
@log_route(logger)
def delete_category(category_id: int):
    """Delete a category."""
    repo = CategoryRepository()
    deleted = repo.delete_category(category_id)

    if not deleted:
        logger.warning(f"Category {category_id} not found")
        return error_response(f'Category {category_id} not found', status_code=404)

    return success_response(
        data={'deleted_id': category_id},
        message=f'Category {category_id} deleted successfully'
    )


# ==================== Sub-categories ====================

@bp.route('/sub-categories', methods=['GET'])
@handle_exceptions(log_prefix="get_sub_categories")
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
@handle_database_errors()
@require_json
@log_route(logger)
def create_sub_category():
    """Create a new sub-category."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_create_sub_category(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

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
@handle_database_errors()
@log_route(logger)
def delete_sub_category(sub_category_id: int):
    """Delete a sub-category."""
    repo = CategoryRepository()
    deleted = repo.delete_sub_category(sub_category_id)

    if not deleted:
        logger.warning(f"Sub-category {sub_category_id} not found")
        return error_response(f'Sub-category {sub_category_id} not found', status_code=404)

    return success_response(
        data={'deleted_id': sub_category_id},
        message=f'Sub-category {sub_category_id} deleted successfully'
    )


# ==================== Types ====================

@bp.route('/types', methods=['GET'])
@handle_exceptions(log_prefix="get_types")
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
@handle_database_errors()
@require_json
@log_route(logger)
def create_type():
    """Create a new type."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_create_type(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

    repo = CategoryRepository()
    # Repository expects 'type_name' instead of 'type'
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
@handle_database_errors()
@log_route(logger)
def delete_type(type_id: int):
    """Delete a type."""
    repo = CategoryRepository()
    deleted = repo.delete_type(type_id)

    if not deleted:
        logger.warning(f"Type {type_id} not found")
        return error_response(f'Type {type_id} not found', status_code=404)

    return success_response(
        data={'deleted_id': type_id},
        message=f'Type {type_id} deleted successfully'
    )


# ==================== Parties ====================

@bp.route('/parties', methods=['GET'])
@handle_exceptions(log_prefix="get_parties")
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
@handle_database_errors()
@require_json
@log_route(logger)
def create_party():
    """Create a new party."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_create_party(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

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
@handle_database_errors()
@log_route(logger)
def delete_party(party_id: int):
    """Delete a party."""
    repo = CategoryRepository()
    deleted = repo.delete_party(party_id)

    if not deleted:
        logger.warning(f"Party {party_id} not found")
        return error_response(f'Party {party_id} not found', status_code=404)

    return success_response(
        data={'deleted_id': party_id},
        message=f'Party {party_id} deleted successfully'
    )


@bp.route('/parties/<int:party_id>/type', methods=['PUT'])
@handle_database_errors()
@require_json
@log_route(logger)
def update_party_type(party_id: int):
    """Update a party's type."""
    result = validate_positive_int('type_id', request.get_json().get('type_id'))
    if not result.is_valid:
        error_msg = result.error.message if result.error else 'type_id is required'
        logger.warning(f"Validation failed for party {party_id}: {error_msg}")
        return error_response(error_msg, status_code=400)

    repo = CategoryRepository()
    logger.debug(f"Updating party {party_id} to type_id: {result.value}")
    updated_party = repo.update_party(party_id=party_id, type_id=result.value)

    if updated_party is None:
        logger.warning(f"Party {party_id} not found")
        return error_response(f'Party {party_id} not found', status_code=404)

    logger.info(f"Updated party {party_id} type to {result.value}")
    return success_response(
        data=updated_party,
        message='Party type updated successfully'
    )


@bp.route('/parties/<int:party_id>/transactions', methods=['GET'])
@handle_exceptions(log_prefix="get_party_transactions")
@log_route(logger)
def get_party_transactions(party_id: int):
    """Get all transactions for a specific party."""
    repo = CategoryRepository()

    party = repo.get_party_by_id(party_id)
    if party is None:
        logger.warning(f"Party {party_id} not found")
        return error_response(f'Party {party_id} not found', status_code=404)

    transactions = repo.get_transactions_by_party(party_id)

    logger.info(f"Retrieved {len(transactions)} transactions for party {party_id}")
    return success_response(data=transactions)

@bp.route("/parties/<int:party_id>/remap", methods=['PUT'])
@handle_exceptions(log_prefix="remap_party")
@require_json
@log_route(logger)
def remap_party(party_id: int):
    """Remap a party to a different type in the category hierarchy."""
    try:
        data = request.get_json()

        if not data or 'type_id' not in data:
            return error_response({
                'error': 'type_id is required'
            }, status_code=400)

        new_type_id = data['type_id']

        if not isinstance(new_type_id, int) or new_type_id < 1:
            return error_response({
                'error': 'type_id must be a positive integer'
            }, status_code=400)

        repo = CategoryRepository()
        result = repo.remap_party(party_id, new_type_id)

        return success_response(data=result)

    except ValueError as e:
        return error_response({'error': str(e)}, status_code=404)
    except Exception as e:
        logger.error(f"Failed to remap party {party_id}: {e}")
        return error_response({'error': f'Failed to remap party: {str(e)}'}, status_code=500)