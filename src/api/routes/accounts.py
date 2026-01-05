from flask import Blueprint, request
import logging

from src.database.repositories.accounts import AccountRepository
from src.api.utils.response_helpers import success_response, error_response
from src.api.utils.route_helpers import handle_exceptions, require_json, handle_database_errors
from src.api.utils.validators import RequestValidator, require_at_least_one

bp = Blueprint('accounts', __name__)
logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def validate_create_account(data: dict) -> tuple[bool, dict, str]:
    """Validate account creation data."""
    validator = RequestValidator(data)
    
    validator.validate_field('account_name',
        validator.field('account_name').required().strip_string())
    validator.validate_field('account_type',
        validator.field('account_type').required().strip_string())
    
    if not validator.is_valid():
        return False, {}, validator.first_error_message()
    
    return True, validator.validated, None


def validate_update_account(data: dict) -> tuple[bool, dict, str]:
    """Validate account update data."""
    # Check at least one field is provided
    error = require_at_least_one(
        data,
        ['account_name', 'account_type'],
        'At least one of account_name or account_type is required'
    )
    if error:
        return False, {}, error
    
    validator = RequestValidator(data)
    
    validator.validate_field('account_name',
        validator.field('account_name').optional().strip_string())
    validator.validate_field('account_type',
        validator.field('account_type').optional().strip_string())
    
    if not validator.is_valid():
        return False, {}, validator.first_error_message()
    
    return True, validator.validated, None


# ==================== Routes ====================

@bp.route('', methods=['GET'])
@handle_exceptions(log_prefix="get_accounts")
def get_accounts():
    """
    Get all accounts with optional filtering by type.
    
    Query Parameters:
        - account_type: Filter by account type (optional)
        
    Returns:
        List of account objects as JSON
    """
    account_repo = AccountRepository()
    account_type = request.args.get('account_type')
    
    if account_type:
        accounts = account_repo.get_accounts_by_type(account_type)
    else:
        accounts = account_repo.get_all_accounts()
    
    return success_response(data=accounts)


@bp.route('/<int:account_id>', methods=['GET'])
@handle_exceptions(log_prefix="get_account")
def get_account(account_id: int):
    """
    Get a single account by ID.
    
    Path Parameters:
        - account_id: The account ID
        
    Returns:
        Account object as JSON or 404 if not found
    """
    account_repo = AccountRepository()
    account = account_repo.get_account_by_id(account_id)
    
    if account is None:
        return error_response(f'Account {account_id} not found', status_code=404)
    
    return success_response(data=account)


@bp.route('', methods=['POST'])
@handle_database_errors()
@require_json
def create_account():
    """
    Create a new account.
    
    Request Body (JSON):
        - account_name: Name of the account (required)
        - account_type: Type of account (required)
        
    Returns:
        Created account object as JSON
    """
    data = request.get_json()
    
    if not data:
        return error_response('Request body is required', status_code=400)
    
    is_valid, validated_data, error_msg = validate_create_account(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    account_repo = AccountRepository()
    account_id = account_repo.add_account(**validated_data)
    
    # Fetch the created account to return full object
    account = account_repo.get_account_by_id(account_id)
    
    return success_response(
        data=account,
        message='Account created successfully',
        status_code=201
    )


@bp.route('/<int:account_id>', methods=['PUT'])
@handle_database_errors()
@require_json
def update_account(account_id: int):
    """
    Update an existing account.
    
    Path Parameters:
        - account_id: The account ID to update
        
    Request Body (JSON):
        - account_name: New name for the account (optional)
        - account_type: New type for the account (optional)
        
    Returns:
        Updated account object as JSON
    """
    data = request.get_json()
    
    if not data:
        return error_response('Request body is required', status_code=400)
    
    is_valid, validated_data, error_msg = validate_update_account(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    account_repo = AccountRepository()
    updated_account = account_repo.update_account(
        account_id=account_id,
        **validated_data
    )
    
    if updated_account is None:
        return error_response(f'Account {account_id} not found', status_code=404)
    
    return success_response(
        data=updated_account,
        message='Account updated successfully'
    )


@bp.route('/<int:account_id>', methods=['DELETE'])
@handle_database_errors()
def delete_account(account_id: int):
    """
    Delete an account.
    
    Path Parameters:
        - account_id: The account ID to delete
        
    Returns:
        Success message or error if account has transactions
    """
    account_repo = AccountRepository()
    deleted = account_repo.delete_account(account_id)
    
    if not deleted:
        return error_response(f'Account {account_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_id': account_id},
        message=f'Account {account_id} deleted successfully'
    )


@bp.route('/types', methods=['GET'])
@handle_exceptions(log_prefix="get_account_types")
def get_account_types():
    """
    Get all distinct account types.
    
    Returns:
        List of account type strings
    """
    account_repo = AccountRepository()
    account_types = account_repo.get_distinct_account_types()
    
    return success_response(data=account_types)


@bp.route('/<int:account_id>/transaction-count', methods=['GET'])
@handle_exceptions(log_prefix="get_transaction_count")
def get_transaction_count(account_id: int):
    """
    Get the number of transactions for an account.
    
    Path Parameters:
        - account_id: The account ID
        
    Returns:
        Transaction count
    """
    account_repo = AccountRepository()
    
    # Verify account exists
    account = account_repo.get_account_by_id(account_id)
    if account is None:
        return error_response(f'Account {account_id} not found', status_code=404)
    
    count = account_repo.get_account_transaction_count(account_id)
    
    return success_response(data={'account_id': account_id, 'transaction_count': count})