from flask import Blueprint, request

from src.database.repositories.transactions import TransactionRepository
from src.database.errors import DELETED_REASON_USER

from src.api.utils.response_helpers import (
    success_response, paginated_response, search_response,
)
from src.api.utils.route_helpers import handle_errors, require_json
from src.api.utils.errors import required, invalid_value, not_found
from src.api.utils.validators import (
    RequestValidator,
    parse_date,
    parse_float,
    parse_int,
    validate_pagination,
    validate_date_range_filters,
    validate_id_filters,
    validate_boolean_fields,
    validate_sort_params,
    add_string_filters,
    require_at_least_one,
    apply_defaults,
    parse_bool_from_string,
)
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('transactions', __name__)
logger = ContextLogger(__name__)

TRANSACTION_SORT_FIELDS = {
    'transaction_date',
    'amount',
    'description',
    'cleaned_description',
    'is_credit',
    'is_kids',
    'is_one_off',
    'account_name',
    'party_name',
    'type_name',
    'sub_category_name',
    'category_name',
    'has_receipt',
}


# =============================================================================
# Validation Helpers
# =============================================================================

def validate_transaction_filters(args: dict) -> dict:
    """
    Validate transaction query filters.
    Raises AppError on invalid input.
    """
    logger.debug(f"Validating transaction filters: {list(args.keys())}")

    is_valid, pagination, error = validate_pagination(args)
    if not is_valid:
        logger.warning(f"Pagination validation failed: {error}")
        raise invalid_value(error)

    is_valid, sort_params, error = validate_sort_params(
        args,
        allowed_fields=TRANSACTION_SORT_FIELDS,
        default_field='transaction_date',
        default_dir='desc',
    )
    if not is_valid:
        logger.warning(f"Sort validation failed: {error}")
        raise invalid_value(error)

    is_valid, date_filters, error = validate_date_range_filters(args)
    if not is_valid:
        logger.warning(f"Date range validation failed: {error}")
        raise invalid_value(error)

    validator = RequestValidator(args)
    validator.validated.update(date_filters)

    validate_id_filters(
        validator,
        args,
        ['party_id', 'account_id', 'upload_id', 'category_id', 'sub_category_id', 'type_id'],
    )

    add_string_filters(
        validator.validated,
        args,
        ['description', 'cleaned_description']
        )

    validate_boolean_fields(
        validator,
        args,
        ['is_kids', 'is_one_off', 'is_credit', 'has_receipt', 'include_deleted', 'deleted_only']
        )

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        raise invalid_value(validator.first_error_message())

    return {**pagination, **sort_params, **validator.validated}


def validate_transaction_update(data: dict) -> dict:
    """
    Validate transaction update data.
    Raises AppError on invalid input.
    """
    logger.debug(f"Validating update data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('transaction_date',
        validator.field('transaction_date').optional().transform(
            parse_date, 'Invalid transaction_date format. Use YYYY-MM-DD'))
    validator.validate_field('amount',
        validator.field('amount').optional().transform(parse_float, 'Invalid amount format'))

    validate_id_filters(validator, data, ['party_id'])
    validator.validate_field('receipt_id',
        validator.field('receipt_id').optional().transform(parse_int).in_range(min_val=0))

    add_string_filters(validator.validated, data, ['description', 'cleaned_description'])
    validate_boolean_fields(validator, data, ['is_credit', 'is_kids', 'is_one_off', 'has_receipt'])

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        raise invalid_value(validator.first_error_message())

    return validator.validated


def validate_transaction_search(data: dict) -> dict:
    """
    Validate transaction search parameters.
    Raises AppError on invalid input.
    """
    logger.debug(f"Validating search params with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('amount',
        validator.field('amount').optional().transform(parse_float, 'Invalid amount format'))
    validator.validate_field('transaction_date',
        validator.field('transaction_date').optional().transform(
            parse_date, 'Invalid transaction_date format. Use YYYY-MM-DD'))

    add_string_filters(validator.validated, data, ['party_name'])

    validator.validate_field('amount_tolerance',
        validator.field('amount_tolerance').optional().transform(parse_float).in_range(min_val=0))
    validator.validate_field('date_tolerance_days',
        validator.field('date_tolerance_days').optional().transform(parse_int).in_range(min_val=0))
    validator.validate_field('limit',
        validator.field('limit').optional().transform(parse_int).in_range(1, 200))

    if 'include_matched' in data:
        validator.validated['include_matched'] = parse_bool_from_string(data['include_matched'])

    apply_defaults(validator.validated, {
        'amount_tolerance': 0.01,
        'date_tolerance_days': 7,
        'include_matched': True,
        'limit': 50,
    })

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        raise invalid_value(validator.first_error_message())

    return validator.validated

def parse_transaction_ids(data: dict) -> list[int]:
    """Extract and validate a `transaction_ids` array from a request body.
    Raises AppError on a missing, non-list, empty, or non-integer value.
    """
    transaction_ids = data.get('transaction_ids', [])
    if not transaction_ids or not isinstance(transaction_ids, list):
        raise invalid_value(
            'transaction_ids must be a non-empty array',
            field='transaction_ids',
        )
    try:
        return [int(tid) for tid in transaction_ids]
    except (ValueError, TypeError):
        raise invalid_value(
            'All transaction_ids must be integers',
            field='transaction_ids',
        )

# =============================================================================
# Routes
# =============================================================================

@bp.route('', methods=['GET'])
@handle_errors(entity='Transaction')
@log_route(logger)
def get_transactions():
    """Get all transactions with full party hierarchy."""
    filters = validate_transaction_filters(request.args.to_dict())

    limit = filters.pop('limit')
    offset = filters.pop('offset')
    sort_by = filters.pop('sort_by', None)
    sort_dir = filters.pop('sort_dir', None)

    active_filters = {k: v for k, v in filters.items() if v is not None}
    if active_filters:
        logger.debug(f"Active filters: {active_filters}")

    repo = TransactionRepository()
    transactions = repo.get_transactions_with_hierarchy(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        **filters,
    )
    total = repo.count_transactions_with_hierarchy(**filters)

    logger.info(
        f"Retrieved {len(transactions)} transactions "
        f"(offset={offset}, limit={limit}, total={total}, sort={sort_by} {sort_dir})"
    )
    return paginated_response(transactions, limit, offset, total=total, data_key='transactions')


@bp.route('/<int:transaction_id>', methods=['GET'])
@handle_errors(entity='Transaction')
@log_route(logger)
def get_transaction(transaction_id: int):
    """Get a specific transaction with full party hierarchy."""
    repo = TransactionRepository()
    transaction = repo.get_transaction_with_hierarchy(transaction_id)

    if transaction is None:
        raise not_found('Transaction', transaction_id)

    return success_response(data=transaction)


@bp.route('/<int:transaction_id>', methods=['PUT'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def update_transaction(transaction_id: int):
    """Update a transaction."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    validated_data = validate_transaction_update(data)

    if not validated_data:
        raise invalid_value('No valid fields to update')

    repo = TransactionRepository()
    updated_transaction = repo.update_transaction(transaction_id, **validated_data)

    if updated_transaction is None:
        raise not_found('Transaction', transaction_id)

    logger.info(f"Updated transaction {transaction_id}: {list(validated_data.keys())}")
    return success_response(
        data=updated_transaction,
        message='Transaction updated successfully',
    )


@bp.route('/bulk', methods=['PUT'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def bulk_update_transactions():
    """Bulk update multiple transactions with the same values."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    transaction_ids = parse_transaction_ids(data)

    updates = data.get('updates', {})
    if not updates:
        raise required('updates')

    validated_data = validate_transaction_update(updates)

    if not validated_data:
        raise invalid_value('No valid fields in updates object', field='updates')

    repo = TransactionRepository()
    result = repo.bulk_update_transactions(transaction_ids, **validated_data)

    logger.info(
        f"Bulk updated {result['updated_count']} transactions: "
        f"{list(validated_data.keys())}"
    )
    return success_response(
        data=result,
        message=f"Successfully updated {result['updated_count']} transactions",
    )


@bp.route('/search', methods=['POST'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def find_transactions():
    """Find transactions matching given parameters."""
    data = request.get_json() or {}

    error = require_at_least_one(
        data,
        ['amount', 'transaction_date', 'party_name'],
        'At least one of amount, transaction_date, or party_name is required',
    )
    if error:
        logger.warning(f"Search validation failed: {error}")
        raise invalid_value(error)

    search_params = validate_transaction_search(data)
    limit = search_params.pop('limit')

    logger.debug(f"Searching transactions: {search_params} | limit={limit}")

    repo = TransactionRepository()
    transactions = repo.find_matching_transactions(limit=limit, **search_params)

    logger.info(f"Search returned {len(transactions)} matches")

    search_params['limit'] = limit
    return search_response(transactions, search_params, results_key='transactions')


@bp.route('/<int:transaction_id>/link-receipt', methods=['POST'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def link_receipt(transaction_id: int):
    """Link a receipt to a transaction."""
    data = request.get_json()
    receipt_id = data.get('receipt_id') if data else None

    if receipt_id is None:
        raise required('receipt_id')

    if not isinstance(receipt_id, int) or receipt_id < 1:
        raise invalid_value(
            'receipt_id must be a positive integer',
            field='receipt_id',
        )

    repo = TransactionRepository()
    # ValueError from repo (e.g. receipt doesn't exist) is caught by
    # @handle_errors and mapped to INVALID_VALUE / 400.
    updated_transaction = repo.link_receipt_to_transaction(
        transaction_id=transaction_id,
        receipt_id=receipt_id,
    )

    if updated_transaction is None:
        raise not_found('Transaction', transaction_id)

    logger.info(f"Linked receipt {receipt_id} to transaction {transaction_id}")
    return success_response(
        data=updated_transaction,
        message=f'Receipt {receipt_id} linked to transaction {transaction_id} successfully',
    )


@bp.route('/<int:transaction_id>/unlink-receipt', methods=['POST'])
@handle_errors(entity='Transaction')
@log_route(logger)
def unlink_receipt(transaction_id: int):
    """Unlink a receipt from a transaction."""
    repo = TransactionRepository()
    updated_transaction = repo.update_transaction(
        transaction_id=transaction_id,
        receipt_id=None,
    )

    if updated_transaction is None:
        raise not_found('Transaction', transaction_id)

    logger.info(f"Unlinked receipt from transaction {transaction_id}")
    return success_response(
        data=updated_transaction,
        message=f'Receipt unlinked from transaction {transaction_id} successfully',
    )

@bp.route('/generate-cash', methods=['POST'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def generate_cash_transactions():
    """Generate cash-account counterpart transactions.

    Accepts a list of source transaction IDs and creates mirror
    transactions on the Cash account with negated amounts. Transactions
    already on the Cash account are rejected; transactions that already
    have a counterpart are silently skipped.

    Request body::

        {
            "transaction_ids": [12, 34, 56]
        }

    Response includes counts of created, skipped, and rejected
    transactions for clear user feedback.
    """
    data = request.get_json()

    if not data:
        raise required('Request body')

    transaction_ids = parse_transaction_ids(data)

    from src.services.cash_transactions import CashTransactionService

    service = CashTransactionService()
    result = service.generate_cash_transactions(transaction_ids)

    return success_response(
        data=result,
        message=(
            f"Generated {result['created_count']} cash transaction(s) "
            f"({result['skipped_count']} skipped, "
            f"{result['rejected_count']} rejected)"
        ),
    )

@bp.route('/from-receipt', methods=['POST'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def create_cash_transaction_from_receipt():
    """Create a Cash-account transaction from a confirmed receipt.

    Request body::

        {
            "receipt_id": 123,
            "party_id": 456,
            "is_withdrawal": true,
            "is_credit": false,
            "is_kids": false,
            "is_one_off": false
        }

    ``is_withdrawal`` defaults to True; ``is_credit``, ``is_kids`` and
    ``is_one_off`` default to False. Rejects if the receipt is missing,
    incomplete, or already linked to a transaction.
    """
    data = request.get_json()
    if not data:
        raise required('Request body')

    receipt_id = data.get('receipt_id')
    if receipt_id is None:
        raise required('receipt_id')
    try:
        receipt_id = int(receipt_id)
    except (ValueError, TypeError):
        raise invalid_value('receipt_id must be an integer', field='receipt_id')

    party_id = data.get('party_id')
    if party_id is None:
        raise required('party_id')
    try:
        party_id = int(party_id)
    except (ValueError, TypeError):
        raise invalid_value('party_id must be an integer', field='party_id')

    is_withdrawal = bool(data.get('is_withdrawal', True))
    is_credit     = bool(data.get('is_credit', False))
    is_kids       = bool(data.get('is_kids', False))
    is_one_off    = bool(data.get('is_one_off', False))

    from src.services.cash_transactions import CashTransactionService
    service = CashTransactionService()
    result = service.generate_cash_transaction_from_receipt(
        receipt_id=receipt_id,
        party_id=party_id,
        is_withdrawal=is_withdrawal,
        is_credit=is_credit,
        is_kids=is_kids,
        is_one_off=is_one_off,
    )

    return success_response(
        data=result,
        message='Cash transaction created from receipt',
        status_code=201,
    )

@bp.route('/cash', methods=['POST'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def create_cash_transaction():
    """Create a Cash-account transaction from manually entered data.

    Request body::

        {
            "transaction_date": "2024-01-15",
            "amount": 12.50,
            "description": "Coffee at Bewley's",
            "party_id": 456,
            "is_withdrawal": true,
            "is_credit": false,
            "is_kids": false,
            "is_one_off": false
        }

    ``amount`` must be positive; its sign in the database is derived
    from ``is_withdrawal``. ``is_withdrawal`` defaults to True;
    ``is_credit``, ``is_kids``, ``is_one_off`` default to False.
    """
    data = request.get_json()
    if not data:
        raise required('Request body')

    transaction_date = data.get('transaction_date')
    if not transaction_date:
        raise required('transaction_date')

    description = data.get('description')
    if not description or not str(description).strip():
        raise required('description')

    amount_raw = data.get('amount')
    if amount_raw is None:
        raise required('amount')
    try:
        amount = float(amount_raw)
    except (ValueError, TypeError):
        raise invalid_value('amount must be a number', field='amount')
    if amount <= 0:
        raise invalid_value('amount must be positive', field='amount')

    party_id = data.get('party_id')
    if party_id is None:
        raise required('party_id')
    try:
        party_id = int(party_id)
    except (ValueError, TypeError):
        raise invalid_value('party_id must be an integer', field='party_id')

    is_withdrawal = bool(data.get('is_withdrawal', True))
    is_credit     = bool(data.get('is_credit', False))
    is_kids       = bool(data.get('is_kids', False))
    is_one_off    = bool(data.get('is_one_off', False))

    from src.services.cash_transactions import CashTransactionService
    service = CashTransactionService()
    result = service.create_cash_transaction(
        transaction_date=transaction_date,
        amount=amount,
        description=str(description).strip(),
        party_id=party_id,
        is_withdrawal=is_withdrawal,
        is_credit=is_credit,
        is_kids=is_kids,
        is_one_off=is_one_off,
    )

    return success_response(
        data=result,
        message='Cash transaction created',
        status_code=201,
    )

@bp.route('/<int:transaction_id>', methods=['DELETE'])
@handle_errors(entity='Transaction')
@log_route(logger)
def delete_transaction(transaction_id: int):
    """Soft-delete a transaction.
    The row is retained with `deleted_at` stamped; it simply stops
    appearing in every read path. Reversible via POST /<id>/restore.
    Cascades to any generated cash transactions derived from this one —
    their IDs come back in `cascaded_ids` so the client can remove them
    from the table too.
    Returns 404 if the transaction doesn't exist or was already deleted,
    409 if it is one line of a split (unsplit the source instead).
    """
    repo = TransactionRepository()
    result = repo.delete_transaction(transaction_id)
    if not result['deleted']:
        raise not_found('Transaction', transaction_id)
    cascaded = result['cascaded_ids']
    message = f'Transaction {transaction_id} deleted'
    if cascaded:
        message += (
            f' ({len(cascaded)} generated cash transaction(s) also deleted)'
        )
    logger.info(message)
    return success_response(data=result, message=message)

@bp.route('/bulk', methods=['DELETE'])
@handle_errors(entity='Transaction')
@require_json
@log_route(logger)
def bulk_delete_transactions():
    """Soft-delete multiple transactions.
    Request body::
        {
            "transaction_ids": [12, 34, 56]
        }
    Atomic. If any requested ID is a line of a split, nothing is deleted
    and the response is 409. IDs that don't exist or are already deleted
    are reported in `skipped_ids` rather than failing the batch.
    """
    data = request.get_json()
    if not data:
        raise required('Request body')
    transaction_ids = parse_transaction_ids(data)
    repo = TransactionRepository()
    result = repo.bulk_delete_transactions(transaction_ids)
    message = f"Deleted {result['deleted_count']} transaction(s)"
    if result['cascaded_ids']:
        message += f" ({len(result['cascaded_ids'])} cascaded)"
    if result['skipped_ids']:
        message += f" ({len(result['skipped_ids'])} skipped)"
    logger.info(
        f"{message} | requested={len(transaction_ids)}"
    )
    return success_response(data=result, message=message)

@bp.route('/<int:transaction_id>/restore', methods=['POST'])
@handle_errors(entity='Transaction')
@log_route(logger)
def restore_transaction(transaction_id: int):
    """Restore a soft-deleted transaction.
    Only transactions the user deleted themselves can be restored here.
    Cascade-deleted children are restored alongside their source. Rows
    hidden by a split ('superseded') or discarded by an unsplit return
    409 with a message pointing at the right operation.
    Returns the restored transaction with full hierarchy so the client
    can drop it straight back into the list.
    """
    repo = TransactionRepository()
    result = repo.restore_transaction(transaction_id)
    if not result['restored']:
        raise not_found('Transaction', transaction_id)
    transaction = repo.get_transaction_with_hierarchy(transaction_id)
    restored_children = result['restored_ids']
    message = f'Transaction {transaction_id} restored'
    if restored_children:
        message += (
            f' ({len(restored_children)} generated cash transaction(s) '
            f'also restored)'
        )
    logger.info(message)
    return success_response(
        data={
            'transaction': transaction,
            'restored_ids': restored_children,
        },
        message=message,
    )

@bp.route('/deleted', methods=['GET'])
@handle_errors(entity='Transaction')
@log_route(logger)
def get_deleted_transactions():
    """Recycle bin — transactions the user deleted, newest first.
    Deliberately filtered to `deleted_reason = 'user'`. Transactions
    hidden by a split ('superseded') or by a cascade were never deleted
    by the user and must not be restorable from here — restoring a
    superseded parent would silently destroy its split children.
    Supports the same filters, sorting and pagination as GET /.
    """
    filters = validate_transaction_filters(request.args.to_dict())
    limit = filters.pop('limit')
    offset = filters.pop('offset')
    sort_by = filters.pop('sort_by', None)
    sort_dir = filters.pop('sort_dir', None)
    # The bin controls its own visibility rules.
    filters.pop('include_deleted', None)
    repo = TransactionRepository()
    transactions = repo.get_transactions_with_hierarchy(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        deleted_only=True,
        deleted_reason=DELETED_REASON_USER,
        **filters,
    )
    total = repo.count_transactions_with_hierarchy(**filters)
    logger.info(
        f"Retrieved {len(transactions)} deleted transactions of {total} total"
        )
    return paginated_response(
        transactions,
        limit,
        offset,
        total=total,
        data_key='transactions'
        )
