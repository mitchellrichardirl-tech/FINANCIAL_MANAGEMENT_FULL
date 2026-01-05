from flask import Blueprint, request
import logging

from src.database.repositories.categories import CategoryRepository
from src.api.utils.response_helpers import success_response, error_response
from src.api.utils.route_helpers import handle_exceptions, require_json, handle_database_errors
from src.api.utils.validators import RequestValidator, parse_int, validate_positive_int

bp = Blueprint('categories', __name__)
logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def validate_create_category(data: dict) -> tuple[bool, dict, str]:
    """Validate category creation data."""
    validator = RequestValidator(data)
    
    validator.validate_field('category',
        validator.field('category').required().strip_string())
    
    # Optional description
    description = data.get('description', '').strip() or None
    if description:
        validator.validated['description'] = description
    
    if not validator.is_valid():
        return False, {}, validator.first_error_message()
    
    return True, validator.validated, None


def validate_create_sub_category(data: dict) -> tuple[bool, dict, str]:
    """Validate sub-category creation data."""
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
        return False, {}, validator.first_error_message()
    
    return True, validator.validated, None


def validate_create_type(data: dict) -> tuple[bool, dict, str]:
    """Validate type creation data."""
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
        return False, {}, validator.first_error_message()
    
    return True, validator.validated, None


def validate_create_party(data: dict) -> tuple[bool, dict, str]:
    """Validate party creation data."""
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
        return False, {}, validator.first_error_message()
    
    return True, validator.validated, None


# ==================== Categories ====================

@bp.route('/categories', methods=['GET'])
@handle_exceptions(log_prefix="get_categories")
def get_categories():
    """
    Get all categories.
    
    Returns:
        List of category objects as JSON
    """
    repo = CategoryRepository()
    categories = repo.get_all_categories()
    return success_response(data=categories)


@bp.route('/categories', methods=['POST'])
@handle_database_errors()
@require_json
def create_category():
    """
    Create a new category.
    
    Request Body (JSON):
        - category: Category name (required)
        - description: Category description (optional)
        
    Returns:
        Created category object as JSON
    """
    data = request.get_json()
    
    if not data:
        return error_response('Request body is required', status_code=400)
    
    is_valid, validated_data, error_msg = validate_create_category(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    repo = CategoryRepository()
    category_id = repo.add_category(**validated_data)
    category = repo.get_category_by_id(category_id)
    
    return success_response(
        data=category,
        message='Category created successfully',
        status_code=201
    )


@bp.route('/categories/<int:category_id>', methods=['DELETE'])
@handle_database_errors()
def delete_category(category_id: int):
    """
    Delete a category.
    
    Path Parameters:
        - category_id: The category ID to delete
        
    Returns:
        Success message or error if category has sub-categories
    """
    repo = CategoryRepository()
    deleted = repo.delete_category(category_id)
    
    if not deleted:
        return error_response(f'Category {category_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_id': category_id},
        message=f'Category {category_id} deleted successfully'
    )


# ==================== Sub-categories ====================

@bp.route('/sub-categories', methods=['GET'])
@handle_exceptions(log_prefix="get_sub_categories")
def get_sub_categories():
    """
    Get all sub-categories, optionally filtered by category.
    
    Query Parameters:
        - category_id: Filter by category (optional)
        
    Returns:
        List of sub-category objects as JSON
    """
    repo = CategoryRepository()
    category_id = request.args.get('category_id', type=int)
    
    if category_id:
        sub_categories = repo.get_sub_categories_by_category(category_id)
    else:
        sub_categories = repo.get_all_sub_categories()
    
    return success_response(data=sub_categories)


@bp.route('/sub-categories', methods=['POST'])
@handle_database_errors()
@require_json
def create_sub_category():
    """
    Create a new sub-category.
    
    Request Body (JSON):
        - sub_category: Sub-category name (required)
        - category_id: Parent category ID (required)
        - description: Sub-category description (optional)
        
    Returns:
        Created sub-category object as JSON
    """
    data = request.get_json()
    
    if not data:
        return error_response('Request body is required', status_code=400)
    
    is_valid, validated_data, error_msg = validate_create_sub_category(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    repo = CategoryRepository()
    sub_category_id = repo.add_sub_category(**validated_data)
    sub_category = repo.get_sub_category_by_id(sub_category_id)
    
    return success_response(
        data=sub_category,
        message='Sub-category created successfully',
        status_code=201
    )


@bp.route('/sub-categories/<int:sub_category_id>', methods=['DELETE'])
@handle_database_errors()
def delete_sub_category(sub_category_id: int):
    """
    Delete a sub-category.
    
    Path Parameters:
        - sub_category_id: The sub-category ID to delete
        
    Returns:
        Success message or error if sub-category has types
    """
    repo = CategoryRepository()
    deleted = repo.delete_sub_category(sub_category_id)
    
    if not deleted:
        return error_response(f'Sub-category {sub_category_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_id': sub_category_id},
        message=f'Sub-category {sub_category_id} deleted successfully'
    )


# ==================== Types ====================

@bp.route('/types', methods=['GET'])
@handle_exceptions(log_prefix="get_types")
def get_types():
    """
    Get all types, optionally filtered by sub-category.
    
    Query Parameters:
        - sub_category_id: Filter by sub-category (optional)
        
    Returns:
        List of type objects as JSON
    """
    repo = CategoryRepository()
    sub_category_id = request.args.get('sub_category_id', type=int)
    
    if sub_category_id:
        types = repo.get_types_by_sub_category(sub_category_id)
    else:
        types = repo.get_all_types()
    
    return success_response(data=types)


@bp.route('/types', methods=['POST'])
@handle_database_errors()
@require_json
def create_type():
    """
    Create a new type.
    
    Request Body (JSON):
        - type: Type name (required)
        - sub_category_id: Parent sub-category ID (required)
        - description: Type description (optional)
        
    Returns:
        Created type object as JSON
    """
    data = request.get_json()
    
    if not data:
        return error_response('Request body is required', status_code=400)
    
    is_valid, validated_data, error_msg = validate_create_type(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    repo = CategoryRepository()
    # Repository expects 'type_name' instead of 'type'
    type_name = validated_data.pop('type')
    type_id = repo.add_type(type_name=type_name, **validated_data)
    type_obj = repo.get_type_by_id(type_id)
    
    return success_response(
        data=type_obj,
        message='Type created successfully',
        status_code=201
    )


@bp.route('/types/<int:type_id>', methods=['DELETE'])
@handle_database_errors()
def delete_type(type_id: int):
    """
    Delete a type.
    
    Path Parameters:
        - type_id: The type ID to delete
        
    Returns:
        Success message or error if type has parties
    """
    repo = CategoryRepository()
    deleted = repo.delete_type(type_id)
    
    if not deleted:
        return error_response(f'Type {type_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_id': type_id},
        message=f'Type {type_id} deleted successfully'
    )


# ==================== Parties ====================

@bp.route('/parties', methods=['GET'])
@handle_exceptions(log_prefix="get_parties")
def get_parties():
    """
    Get all parties with transaction counts, optionally filtered by type.
    
    Query Parameters:
        - type_id: Filter by type (optional)
        
    Returns:
        List of party objects as JSON
    """
    repo = CategoryRepository()
    type_id = request.args.get('type_id', type=int)
    
    if type_id:
        parties = repo.get_parties_by_type(type_id)
    else:
        parties = repo.get_all_parties_with_transaction_counts()
    
    return success_response(data=parties)


@bp.route('/parties', methods=['POST'])
@handle_database_errors()
@require_json
def create_party():
    """
    Create a new party.
    
    Request Body (JSON):
        - name: Party name (required)
        - type_id: Parent type ID (optional - will use 'Unknown' if not provided)
        - description: Party description (optional)
        
    Returns:
        Created party object as JSON
    """
    data = request.get_json()
    
    if not data:
        return error_response('Request body is required', status_code=400)
    
    is_valid, validated_data, error_msg = validate_create_party(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    repo = CategoryRepository()
    
    if 'type_id' in validated_data:
        party_id = repo.add_party(**validated_data)
    else:
        # Remove type_id from validated_data if None
        validated_data.pop('type_id', None)
        party_id = repo.add_party_unknown_type(**validated_data)
    
    party = repo.get_party_by_id(party_id)
    
    return success_response(
        data=party,
        message='Party created successfully',
        status_code=201
    )


@bp.route('/parties/<int:party_id>', methods=['DELETE'])
@handle_database_errors()
def delete_party(party_id: int):
    """
    Delete a party.
    
    Path Parameters:
        - party_id: The party ID to delete
        
    Returns:
        Success message or error if party has transactions
    """
    repo = CategoryRepository()
    deleted = repo.delete_party(party_id)
    
    if not deleted:
        return error_response(f'Party {party_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_id': party_id},
        message=f'Party {party_id} deleted successfully'
    )


@bp.route('/parties/<int:party_id>/type', methods=['PUT'])
@handle_database_errors()
@require_json
def update_party_type(party_id: int):
    """
    Update a party's type.
    
    Path Parameters:
        - party_id: The party ID to update
        
    Request Body (JSON):
        - type_id: New type ID (required)
        
    Returns:
        Updated party object as JSON
    """
    result = validate_positive_int('type_id', request.get_json().get('type_id'))
    if not result.is_valid:
        error_msg = result.error.message if result.error else 'type_id is required'
        return error_response(error_msg, status_code=400)
    
    repo = CategoryRepository()
    updated_party = repo.update_party(party_id=party_id, type_id=result.value)
    
    if updated_party is None:
        return error_response(f'Party {party_id} not found', status_code=404)
    
    return success_response(
        data=updated_party,
        message='Party type updated successfully'
    )


@bp.route('/parties/<int:party_id>/transactions', methods=['GET'])
@handle_exceptions(log_prefix="get_party_transactions")
def get_party_transactions(party_id: int):
    """
    Get all transactions for a specific party.
    
    Path Parameters:
        - party_id: The party ID
        
    Returns:
        List of transaction objects as JSON
    """
    repo = CategoryRepository()
    
    # Verify party exists
    party = repo.get_party_by_id(party_id)
    if party is None:
        return error_response(f'Party {party_id} not found', status_code=404)
    
    transactions = repo.get_transactions_by_party(party_id)
    
    return success_response(data=transactions)