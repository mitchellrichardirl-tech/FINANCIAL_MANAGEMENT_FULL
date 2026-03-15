from flask import Blueprint, request

from src.database.repositories.categories import CategoryRepository
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


@bp.route('/parties/<int:party_id>/type', methods=['PUT'])
@handle_errors(entity='Party')
@require_json
@log_route(logger)
def update_party_type(party_id: int):
    """Update a party's type."""
    data = request.get_json()
    type_id = data.get('type_id') if data else None

    if type_id is None:
        raise required('type_id')

    if not isinstance(type_id, int) or type_id < 1:
        raise invalid_value('type_id must be a positive integer', field='type_id')

    repo = CategoryRepository()
    logger.debug(f"Updating party {party_id} to type_id: {type_id}")
    updated_party = repo.update_party(party_id=party_id, type_id=type_id)

    if updated_party is None:
        raise not_found('Party', party_id)

    logger.info(f"Updated party {party_id} type to {type_id}")
    return success_response(
        data=updated_party,
        message='Party type updated successfully'
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