from flask import Blueprint, request
from datetime import datetime
import logging

from src.database.connection import DatabaseError
from src.database.repositories.transactions import TransactionRepository
from src.api.utils.response_helpers import success_response, error_response

bp = Blueprint('transactions', __name__)

logger = logging.getLogger(__name__)


@bp.route('', methods=['GET'])
def get_transactions():
    """
    Get all transactions with full party hierarchy.
    
    Query Parameters:
        - limit: Maximum number of results (default: 50, max: 500)
        - offset: Pagination offset (default: 0)
        - start_date: Filter from date (YYYY-MM-DD)
        - end_date: Filter until date (YYYY-MM-DD)
        - party_id: Filter by party ID
        - account_id: Filter by account ID
        - upload_id: Filter by upload ID
        - description: Filter by description (substring match)
        - cleaned_description: Filter by cleaned description (substring match)
        
    Returns:
        List of transactions with full hierarchy information
    """
    try:
        print(request.args.keys())
        # Parse query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        party_id = request.args.get('party_id', type=int)
        account_id = request.args.get('account_id', type=int)
        upload_id = request.args.get('upload_id', type=int)
        description = request.args.get('description')
        cleaned_description = request.args.get('cleaned_description')
        
        # Validate parameters
        if limit < 1:
            return error_response('Limit must be at least 1', status_code=400)
        if limit > 500:
            return error_response('Limit cannot exceed 500', status_code=400)
        if offset < 0:
            return error_response('Offset must be non-negative', status_code=400)
        
        # Validate dates
        if start_date:
            try:
                datetime.fromisoformat(start_date)
            except ValueError:
                return error_response('Invalid start_date format. Use YYYY-MM-DD', status_code=400)
        
        if end_date:
            try:
                datetime.fromisoformat(end_date)
            except ValueError:
                return error_response('Invalid end_date format. Use YYYY-MM-DD', status_code=400)
            
        if request.args.get('is_kids') is not None:
            is_kids = request.args.get('is_kids')
            is_kids = is_kids.lower() == 'true'
        else:
            is_kids = None
        if request.args.get('is_one_off') is not None:
            is_one_off = request.args.get('is_one_off')
            is_one_off = is_one_off.lower() == 'true'
        else:
            is_one_off = None
        if request.args.get('is_credit') is not None:
            is_credit = request.args.get('is_credit')
            is_credit = is_credit.lower() == 'true'
        else:
            is_credit = None

        repo = TransactionRepository()
        transactions = repo.get_transactions_with_hierarchy(
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            party_id=party_id,
            account_id=account_id,
            upload_id=upload_id,
            description=description,
            cleaned_description=cleaned_description,
            is_kids=is_kids,
            is_one_off=is_one_off,
            is_credit=is_credit
        )
        
        return success_response(data={
            'transactions': transactions,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(transactions),
                'has_more': len(transactions) == limit
            }
        })
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get transactions: {e}')
        return error_response(f'Failed to get transactions: {str(e)}', status_code=500)


@bp.route('/<int:transaction_id>', methods=['GET'])
def get_transaction(transaction_id: int):
    """
    Get a specific transaction with full party hierarchy.
    
    Path Parameters:
        - transaction_id: The transaction ID
        
    Returns:
        Transaction with full hierarchy information or 404 if not found
    """
    try:
        repo = TransactionRepository()
        transaction = repo.get_transaction_with_hierarchy(transaction_id)
        
        if transaction is None:
            return error_response(f'Transaction {transaction_id} not found', status_code=404)
        
        return success_response(data=transaction)
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get transaction {transaction_id}: {e}')
        return error_response(f'Failed to get transaction: {str(e)}', status_code=500)


@bp.route('/<int:transaction_id>', methods=['PUT'])
def update_transaction(transaction_id: int):
    """
    Update a transaction.
    
    Path Parameters:
        - transaction_id: The transaction ID
        
    Request Body (JSON):
        - amount: New amount (optional)
        - description: New description (optional)
        - cleaned_description: New cleaned description (optional)
        - transaction_date: New date YYYY-MM-DD (optional)
        - is_credit: Credit flag (optional)
        - is_kids: Kids flag (optional)
        - is_one_off: One-off flag (optional)
        - party_id: New party ID (optional)
        - receipt_id: New receipt ID (optional)
        
    Returns:
        Updated transaction with hierarchy
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        # Validate date if provided
        if 'transaction_date' in data:
            try:
                datetime.fromisoformat(data['transaction_date'])
            except (ValueError, TypeError):
                return error_response('Invalid transaction_date format. Use YYYY-MM-DD', status_code=400)
        
        # Validate amount if provided
        if 'amount' in data:
            try:
                float(data['amount'])
            except (ValueError, TypeError):
                return error_response('Invalid amount format', status_code=400)
        
        repo = TransactionRepository()
        updated_transaction = repo.update_transaction(transaction_id, **data)
        
        if updated_transaction is None:
            return error_response(f'Transaction {transaction_id} not found', status_code=404)
        
        return success_response(
            data=updated_transaction,
            message='Transaction updated successfully'
        )
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to update transaction {transaction_id}: {e}')
        return error_response(f'Failed to update transaction: {str(e)}', status_code=500)


@bp.route('/search', methods=['POST'])
def find_transactions():
    """
    Find transactions matching given parameters.
    
    Request Body (JSON):
        - amount: Amount to match (optional)
        - transaction_date: Date to match YYYY-MM-DD (optional)
        - party_name: Party/vendor name to match, partial match (optional)
        - amount_tolerance: Max difference in amount (default: 0.01)
        - date_tolerance_days: Max difference in days (default: 7)
        - include_matched: Include transactions with receipts (default: true)
        - limit: Maximum results (default: 50, max: 200)
        
    Note: At least one of amount, transaction_date, or party_name must be provided.
        
    Returns:
        List of matching transactions with hierarchy
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        # Extract search parameters
        amount = data.get('amount')
        transaction_date = data.get('transaction_date')
        party_name = data.get('party_name')
        
        # Validate at least one search parameter
        if amount is None and transaction_date is None and party_name is None:
            return error_response(
                'At least one of amount, transaction_date, or party_name is required',
                status_code=400
            )
        
        # Validate amount
        if amount is not None:
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return error_response('Invalid amount format', status_code=400)
        
        # Validate date
        if transaction_date:
            try:
                datetime.fromisoformat(transaction_date)
            except ValueError:
                return error_response('Invalid transaction_date format. Use YYYY-MM-DD', status_code=400)
        
        # Get optional parameters with defaults
        amount_tolerance = data.get('amount_tolerance', 0.01)
        date_tolerance_days = data.get('date_tolerance_days', 7)
        include_matched = data.get('include_matched', True)
        limit = data.get('limit', 50)
        
        # Validate optional parameters
        if not isinstance(amount_tolerance, (int, float)) or amount_tolerance < 0:
            return error_response('amount_tolerance must be a non-negative number', status_code=400)
        
        if not isinstance(date_tolerance_days, int) or date_tolerance_days < 0:
            return error_response('date_tolerance_days must be a non-negative integer', status_code=400)
        
        if limit < 1 or limit > 200:
            return error_response('limit must be between 1 and 200', status_code=400)
        
        repo = TransactionRepository()
        transactions = repo.find_matching_transactions(
            amount=amount,
            transaction_date=transaction_date,
            party_name=party_name,
            amount_tolerance=amount_tolerance,
            date_tolerance_days=date_tolerance_days,
            include_matched=include_matched,
            limit=limit
        )
        
        return success_response(data={
            'transactions': transactions,
            'search_parameters': {
                'amount': amount,
                'transaction_date': transaction_date,
                'party_name': party_name,
                'amount_tolerance': amount_tolerance,
                'date_tolerance_days': date_tolerance_days,
                'include_matched': include_matched
            },
            'count': len(transactions)
        })
        
    except ValueError as e:
        return error_response(str(e), status_code=400)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to find transactions: {e}')
        return error_response(f'Failed to find transactions: {str(e)}', status_code=500)


@bp.route('/<int:transaction_id>/link-receipt', methods=['POST'])
def link_receipt(transaction_id: int):
    """
    Link a receipt to a transaction.
    
    Path Parameters:
        - transaction_id: The transaction ID
        
    Request Body (JSON):
        - receipt_id: The receipt ID to link (required)
        
    Returns:
        Updated transaction with receipt linked
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', status_code=400)
        
        if 'receipt_id' not in data:
            return error_response('receipt_id is required', status_code=400)
        
        receipt_id = data['receipt_id']
        
        if not isinstance(receipt_id, int) or receipt_id < 1:
            return error_response('receipt_id must be a positive integer', status_code=400)
        
        repo = TransactionRepository()
        updated_transaction = repo.link_receipt_to_transaction(
            transaction_id=transaction_id,
            receipt_id=receipt_id
        )
        
        if updated_transaction is None:
            return error_response(f'Transaction {transaction_id} not found', status_code=404)
        
        return success_response(
            data=updated_transaction,
            message=f'Receipt {receipt_id} linked to transaction {transaction_id} successfully'
        )
        
    except ValueError as e:
        # Receipt doesn't exist
        return error_response(str(e), status_code=404)
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to link receipt to transaction {transaction_id}: {e}')
        return error_response(f'Failed to link receipt: {str(e)}', status_code=500)


@bp.route('/<int:transaction_id>/unlink-receipt', methods=['POST'])
def unlink_receipt(transaction_id: int):
    """
    Unlink a receipt from a transaction.
    
    Path Parameters:
        - transaction_id: The transaction ID
        
    Returns:
        Updated transaction with receipt unlinked
    """
    try:
        repo = TransactionRepository()
        
        # Set receipt_id to None to unlink
        updated_transaction = repo.update_transaction(
            transaction_id=transaction_id,
            receipt_id=None
        )
        
        if updated_transaction is None:
            return error_response(f'Transaction {transaction_id} not found', status_code=404)
        
        return success_response(
            data=updated_transaction,
            message=f'Receipt unlinked from transaction {transaction_id} successfully'
        )
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to unlink receipt from transaction {transaction_id}: {e}')
        return error_response(f'Failed to unlink receipt: {str(e)}', status_code=500)