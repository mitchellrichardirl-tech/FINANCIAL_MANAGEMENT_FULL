from flask import Blueprint, request
import logging

from src.database.connection import DatabaseError
from src.database.repositories.accounts import AccountRepository
from src.api.utils.response_helpers import success_response, error_response

bp = Blueprint('accounts', __name__)

logger = logging.getLogger(__name__)


@bp.route('', methods=['GET'])
def get_accounts():
    """
    Get all accounts with optional filtering by type.
    
    Query Parameters:
        - account_type: Filter by account type (optional)
        
    Returns:
        List of account objects as JSON
    """
    try:
        account_repo = AccountRepository()
        account_type = request.args.get('account_type')
        
        if account_type:
            accounts = account_repo.get_accounts_by_type(account_type)
        else:
            accounts = account_repo.get_all_accounts()
        
        return success_response(data=accounts)
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get accounts: {e}')
        return error_response(f'Failed to get accounts: {str(e)}', status_code=500)


@bp.route('/<int:account_id>', methods=['GET'])
def get_account(account_id: int):
    """
    Get a single account by ID.
    
    Path Parameters:
        - account_id: The account ID
        
    Returns:
        Account object as JSON or 404 if not found
    """
    try:
        account_repo = AccountRepository()
        account = account_repo.get_account_by_id(account_id)
        
        if account is None:
            return error_response(f'Account {account_id} not found', status_code=404)
        
        return success_response(data=account)
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get account {account_id}: {e}')
        return error_response(f'Failed to get account: {str(e)}', status_code=500)


@bp.route('', methods=['POST'])
def create_account():
    """
    Create a new account.
    
    Request Body (JSON):
        - account_name: Name of the account (required)
        - account_type: Type of account (required)
        
    Returns:
        Created account object as JSON
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        # Validate required fields
        if 'account_name' not in data or not data['account_name']:
            return error_response('account_name is required', status_code=400)
        
        if 'account_type' not in data or not data['account_type']:
            return error_response('account_type is required', status_code=400)
        
        account_repo = AccountRepository()
        account_id = account_repo.add_account(
            account_name=data['account_name'].strip(),
            account_type=data['account_type'].strip()
        )
        
        # Fetch the created account to return full object
        account = account_repo.get_account_by_id(account_id)
        
        return success_response(
            data=account,
            message='Account created successfully',
            status_code=201
        )
        
    except DatabaseError as e:
        # Check for duplicate account error
        if 'already exists' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to create account: {e}')
        return error_response(f'Failed to create account: {str(e)}', status_code=500)


@bp.route('/<int:account_id>', methods=['PUT'])
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
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        # Check at least one field is provided
        if 'account_name' not in data and 'account_type' not in data:
            return error_response(
                'At least one of account_name or account_type is required',
                status_code=400
            )
        
        account_repo = AccountRepository()
        
        # Prepare update parameters
        account_name = data.get('account_name')
        account_type = data.get('account_type')
        
        if account_name is not None:
            account_name = account_name.strip()
        if account_type is not None:
            account_type = account_type.strip()
        
        updated_account = account_repo.update_account(
            account_id=account_id,
            account_name=account_name,
            account_type=account_type
        )
        
        if updated_account is None:
            return error_response(f'Account {account_id} not found', status_code=404)
        
        return success_response(
            data=updated_account,
            message='Account updated successfully'
        )
        
    except DatabaseError as e:
        if 'already exists' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to update account {account_id}: {e}')
        return error_response(f'Failed to update account: {str(e)}', status_code=500)


@bp.route('/<int:account_id>', methods=['DELETE'])
def delete_account(account_id: int):
    """
    Delete an account.
    
    Path Parameters:
        - account_id: The account ID to delete
        
    Returns:
        Success message or error if account has transactions
    """
    try:
        account_repo = AccountRepository()
        deleted = account_repo.delete_account(account_id)
        
        if not deleted:
            return error_response(f'Account {account_id} not found', status_code=404)
        
        return success_response(
            data={'deleted_id': account_id},
            message=f'Account {account_id} deleted successfully'
        )
        
    except DatabaseError as e:
        # Check for associated transactions error
        if 'associated transaction' in str(e).lower():
            return error_response(str(e), status_code=409)
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to delete account {account_id}: {e}')
        return error_response(f'Failed to delete account: {str(e)}', status_code=500)


@bp.route('/types', methods=['GET'])
def get_account_types():
    """
    Get all distinct account types.
    
    Returns:
        List of account type strings
    """
    try:
        account_repo = AccountRepository()
        account_types = account_repo.get_distinct_account_types()
        
        return success_response(data=account_types)
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get account types: {e}')
        return error_response(f'Failed to get account types: {str(e)}', status_code=500)


@bp.route('/<int:account_id>/transaction-count', methods=['GET'])
def get_transaction_count(account_id: int):
    """
    Get the number of transactions for an account.
    
    Path Parameters:
        - account_id: The account ID
        
    Returns:
        Transaction count
    """
    try:
        account_repo = AccountRepository()
        
        # Verify account exists
        account = account_repo.get_account_by_id(account_id)
        if account is None:
            return error_response(f'Account {account_id} not found', status_code=404)
        
        count = account_repo.get_account_transaction_count(account_id)
        
        return success_response(data={'account_id': account_id, 'transaction_count': count})
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get transaction count for account {account_id}: {e}')
        return error_response(f'Failed to get transaction count: {str(e)}', status_code=500)