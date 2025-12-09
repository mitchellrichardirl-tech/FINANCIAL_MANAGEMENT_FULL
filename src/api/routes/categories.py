from flask import Blueprint, request
import logging

from src.database.connection import DatabaseError
from src.database.repositories.categories import CategoryRepository
from src.api.utils.response_helpers import success_response, error_response

bp = Blueprint('categories', __name__)

logger = logging.getLogger(__name__)


# ==================== Categories ====================

@bp.route('/categories', methods=['GET'])
def get_categories():
    """
    Get all categories.
    
    Returns:
        List of category objects as JSON
    """
    try:
        repo = CategoryRepository()
        categories = repo.get_all_categories()
        return success_response(data=categories)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get categories: {e}')
        return error_response(f'Failed to get categories: {str(e)}', status_code=500)


@bp.route('/categories', methods=['POST'])
def create_category():
    """
    Create a new category.
    
    Request Body (JSON):
        - category: Category name (required)
        - description: Category description (optional)
        
    Returns:
        Created category object as JSON
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        if 'category' not in data or not data['category']:
            return error_response('category is required', status_code=400)
        
        repo = CategoryRepository()
        category_id = repo.add_category(
            category=data['category'].strip(),
            description=data.get('description', '').strip() or None
        )
        
        category = repo.get_category_by_id(category_id)
        
        return success_response(
            data=category,
            message='Category created successfully',
            status_code=201
        )
    except DatabaseError as e:
        if 'already exists' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to create category: {e}')
        return error_response(f'Failed to create category: {str(e)}', status_code=500)


@bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id: int):
    """
    Delete a category.
    
    Path Parameters:
        - category_id: The category ID to delete
        
    Returns:
        Success message or error if category has sub-categories
    """
    try:
        repo = CategoryRepository()
        deleted = repo.delete_category(category_id)
        
        if not deleted:
            return error_response(f'Category {category_id} not found', status_code=404)
        
        return success_response(
            data={'deleted_id': category_id},
            message=f'Category {category_id} deleted successfully'
        )
    except DatabaseError as e:
        if 'associated sub-category' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to delete category {category_id}: {e}')
        return error_response(f'Failed to delete category: {str(e)}', status_code=500)


# ==================== Sub-categories ====================

@bp.route('/sub-categories', methods=['GET'])
def get_sub_categories():
    """
    Get all sub-categories, optionally filtered by category.
    
    Query Parameters:
        - category_id: Filter by category (optional)
        
    Returns:
        List of sub-category objects as JSON
    """
    try:
        repo = CategoryRepository()
        category_id = request.args.get('category_id', type=int)
        
        if category_id:
            sub_categories = repo.get_sub_categories_by_category(category_id)
        else:
            sub_categories = repo.get_all_sub_categories()
        
        return success_response(data=sub_categories)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get sub-categories: {e}')
        return error_response(f'Failed to get sub-categories: {str(e)}', status_code=500)


@bp.route('/sub-categories', methods=['POST'])
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
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        if 'sub_category' not in data or not data['sub_category']:
            return error_response('sub_category is required', status_code=400)
        
        if 'category_id' not in data:
            return error_response('category_id is required', status_code=400)
        
        repo = CategoryRepository()
        sub_category_id = repo.add_sub_category(
            sub_category=data['sub_category'].strip(),
            category_id=data['category_id'],
            description=data.get('description', '').strip() or None
        )
        
        sub_category = repo.get_sub_category_by_id(sub_category_id)
        
        return success_response(
            data=sub_category,
            message='Sub-category created successfully',
            status_code=201
        )
    except DatabaseError as e:
        if 'already exists' in str(e).lower():
            return error_response(str(e), status_code=409)
        if 'does not exist' in str(e).lower():
            return error_response(str(e), status_code=404)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to create sub-category: {e}')
        return error_response(f'Failed to create sub-category: {str(e)}', status_code=500)


@bp.route('/sub-categories/<int:sub_category_id>', methods=['DELETE'])
def delete_sub_category(sub_category_id: int):
    """
    Delete a sub-category.
    
    Path Parameters:
        - sub_category_id: The sub-category ID to delete
        
    Returns:
        Success message or error if sub-category has types
    """
    try:
        repo = CategoryRepository()
        deleted = repo.delete_sub_category(sub_category_id)
        
        if not deleted:
            return error_response(f'Sub-category {sub_category_id} not found', status_code=404)
        
        return success_response(
            data={'deleted_id': sub_category_id},
            message=f'Sub-category {sub_category_id} deleted successfully'
        )
    except DatabaseError as e:
        if 'associated type' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to delete sub-category {sub_category_id}: {e}')
        return error_response(f'Failed to delete sub-category: {str(e)}', status_code=500)


# ==================== Types ====================

@bp.route('/types', methods=['GET'])
def get_types():
    """
    Get all types, optionally filtered by sub-category.
    
    Query Parameters:
        - sub_category_id: Filter by sub-category (optional)
        
    Returns:
        List of type objects as JSON
    """
    try:
        repo = CategoryRepository()
        sub_category_id = request.args.get('sub_category_id', type=int)
        
        if sub_category_id:
            types = repo.get_types_by_sub_category(sub_category_id)
        else:
            types = repo.get_all_types()
        
        return success_response(data=types)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get types: {e}')
        return error_response(f'Failed to get types: {str(e)}', status_code=500)


@bp.route('/types', methods=['POST'])
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
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        if 'type' not in data or not data['type']:
            return error_response('type is required', status_code=400)
        
        if 'sub_category_id' not in data:
            return error_response('sub_category_id is required', status_code=400)
        
        repo = CategoryRepository()
        type_id = repo.add_type(
            type_name=data['type'].strip(),
            sub_category_id=data['sub_category_id'],
            description=data.get('description', '').strip() or None
        )
        
        type_obj = repo.get_type_by_id(type_id)
        
        return success_response(
            data=type_obj,
            message='Type created successfully',
            status_code=201
        )
    except DatabaseError as e:
        if 'already exists' in str(e).lower():
            return error_response(str(e), status_code=409)
        if 'does not exist' in str(e).lower():
            return error_response(str(e), status_code=404)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to create type: {e}')
        return error_response(f'Failed to create type: {str(e)}', status_code=500)


@bp.route('/types/<int:type_id>', methods=['DELETE'])
def delete_type(type_id: int):
    """
    Delete a type.
    
    Path Parameters:
        - type_id: The type ID to delete
        
    Returns:
        Success message or error if type has parties
    """
    try:
        repo = CategoryRepository()
        deleted = repo.delete_type(type_id)
        
        if not deleted:
            return error_response(f'Type {type_id} not found', status_code=404)
        
        return success_response(
            data={'deleted_id': type_id},
            message=f'Type {type_id} deleted successfully'
        )
    except DatabaseError as e:
        if 'associated party' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to delete type {type_id}: {e}')
        return error_response(f'Failed to delete type: {str(e)}', status_code=500)


# ==================== Parties ====================

@bp.route('/parties', methods=['GET'])
def get_parties():
    """
    Get all parties with transaction counts, optionally filtered by type.
    
    Query Parameters:
        - type_id: Filter by type (optional)
        
    Returns:
        List of party objects as JSON
    """
    try:
        repo = CategoryRepository()
        type_id = request.args.get('type_id', type=int)
        
        if type_id:
            parties = repo.get_parties_by_type(type_id)
        else:
            parties = repo.get_all_parties_with_transaction_counts()
        
        return success_response(data=parties)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get parties: {e}')
        return error_response(f'Failed to get parties: {str(e)}', status_code=500)


@bp.route('/parties', methods=['POST'])
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
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        if 'name' not in data or not data['name']:
            return error_response('name is required', status_code=400)
        
        repo = CategoryRepository()
        
        if 'type_id' in data and data['type_id']:
            party_id = repo.add_party(
                name=data['name'].strip(),
                type_id=data['type_id'],
                description=data.get('description', '').strip() or None
            )
        else:
            party_id = repo.add_party_unknown_type(
                name=data['name'].strip(),
                description=data.get('description', '').strip() or None
            )
        
        party = repo.get_party_by_id(party_id)
        
        return success_response(
            data=party,
            message='Party created successfully',
            status_code=201
        )
    except DatabaseError as e:
        if 'already exists' in str(e).lower():
            return error_response(str(e), status_code=409)
        if 'does not exist' in str(e).lower():
            return error_response(str(e), status_code=404)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to create party: {e}')
        return error_response(f'Failed to create party: {str(e)}', status_code=500)


@bp.route('/parties/<int:party_id>', methods=['DELETE'])
def delete_party(party_id: int):
    """
    Delete a party.
    
    Path Parameters:
        - party_id: The party ID to delete
        
    Returns:
        Success message or error if party has transactions
    """
    try:
        repo = CategoryRepository()
        deleted = repo.delete_party(party_id)
        
        if not deleted:
            return error_response(f'Party {party_id} not found', status_code=404)
        
        return success_response(
            data={'deleted_id': party_id},
            message=f'Party {party_id} deleted successfully'
        )
    except DatabaseError as e:
        if 'associated transaction' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to delete party {party_id}: {e}')
        return error_response(f'Failed to delete party: {str(e)}', status_code=500)


@bp.route('/parties/<int:party_id>/type', methods=['PUT'])
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
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        if 'type_id' not in data:
            return error_response('type_id is required', status_code=400)
        
        repo = CategoryRepository()
        updated_party = repo.update_party(
            party_id=party_id,
            type_id=data['type_id']
        )
        
        if updated_party is None:
            return error_response(f'Party {party_id} not found', status_code=404)
        
        return success_response(
            data=updated_party,
            message='Party type updated successfully'
        )
    except DatabaseError as e:
        if 'does not exist' in str(e).lower():
            return error_response(str(e), status_code=404)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to update party type {party_id}: {e}')
        return error_response(f'Failed to update party type: {str(e)}', status_code=500)


@bp.route('/parties/<int:party_id>/transactions', methods=['GET'])
def get_party_transactions(party_id: int):
    """
    Get all transactions for a specific party.
    
    Path Parameters:
        - party_id: The party ID
        
    Returns:
        List of transaction objects as JSON
    """
    try:
        repo = CategoryRepository()
        
        # Verify party exists
        party = repo.get_party_by_id(party_id)
        if party is None:
            return error_response(f'Party {party_id} not found', status_code=404)
        
        transactions = repo.get_transactions_by_party(party_id)
        
        return success_response(data=transactions)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get transactions for party {party_id}: {e}')
        return error_response(f'Failed to get transactions: {str(e)}', status_code=500)