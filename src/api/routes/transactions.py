from flask import Blueprint, request

from src.database.repositories.transactions import TransactionRepository
from src.api.utils.response_helpers import (
    success_response, error_response, paginated_response, search_response
)
from src.api.utils.route_helpers import (
    handle_exceptions,
    require_json,
)
from src.api.utils.validators import (
    RequestValidator,
    parse_date,
    parse_float,
    parse_int,
    validate_pagination,
    validate_date_range_filters,
    validate_id_filters,
    validate_boolean_fields,
    add_string_filters,
    require_at_least_one,
    validate_positive_int,
    apply_defaults,
    parse_bool_from_string,
)
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('transactions', __name__)
logger = ContextLogger(__name__)


def validate_transaction_filters(args: dict) -> tuple[bool, dict, str]:
    """Validate transaction query filters."""
    logger.debug(f"Validating transaction filters: {list(args.keys())}")

    # Pagination
    is_valid, pagination, error = validate_pagination(args)
    if not is_valid:
        logger.warning(f"Pagination validation failed: {error}")
        return False, {}, error

    # Date range
    is_valid, date_filters, error = validate_date_range_filters(args)
    if not is_valid:
        logger.warning(f"Date range validation failed: {error}")
        return False, {}, error

    validator = RequestValidator(args)
    validator.validated.update(date_filters)

    # ID filters
    validate_id_filters(
        validator,
        args,
        [
            'party_id',
            'account_id',
            'upload_id',
            'category_id',
            'sub_category_id',
            'type_id'
        ]
    )

    # String filters
    add_string_filters(validator.validated, args, ['description', 'cleaned_description'])

    # Boolean filters
    validate_boolean_fields(validator, args, ['is_kids', 'is_one_off', 'is_credit'])

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, {**pagination, **validator.validated}, None


def validate_transaction_update(data: dict) -> tuple[bool, dict, str]:
    """Validate transaction update data."""
    logger.debug(f"Validating update data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    # Date and amount
    validator.validate_field('transaction_date',
        validator.field('transaction_date').optional().transform(parse_date, 'Invalid transaction_date format. Use YYYY-MM-DD'))
    validator.validate_field('amount',
        validator.field('amount').optional().transform(parse_float, 'Invalid amount format'))

    # IDs
    validate_id_filters(validator, data, ['party_id'])
    validator.validate_field('receipt_id',
        validator.field('receipt_id').optional().transform(parse_int).in_range(min_val=0))

    # Strings
    add_string_filters(validator.validated, data, ['description', 'cleaned_description'])

    # Booleans
    validate_boolean_fields(validator, data, ['is_credit', 'is_kids', 'is_one_off'])

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def validate_transaction_search(data: dict) -> tuple[bool, dict, str]:
    """Validate transaction search parameters."""
    logger.debug(f"Validating search params with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    # Core search parameters
    validator.validate_field('amount',
        validator.field('amount').optional().transform(parse_float, 'Invalid amount format'))
    validator.validate_field('transaction_date',
        validator.field('transaction_date').optional().transform(parse_date, 'Invalid transaction_date format. Use YYYY-MM-DD'))

    add_string_filters(validator.validated, data, ['party_name'])

    # Tolerance parameters
    validator.validate_field('amount_tolerance',
        validator.field('amount_tolerance').optional().transform(parse_float).in_range(min_val=0))
    validator.validate_field('date_tolerance_days',
        validator.field('date_tolerance_days').optional().transform(parse_int).in_range(min_val=0))
    validator.validate_field('limit',
        validator.field('limit').optional().transform(parse_int).in_range(1, 200))

    # Boolean
    if 'include_matched' in data:
        validator.validated['include_matched'] = parse_bool_from_string(data['include_matched'])

    # Defaults
    apply_defaults(validator.validated, {
        'amount_tolerance': 0.01,
        'date_tolerance_days': 7,
        'include_matched': True,
        'limit': 50
    })

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


@bp.route('', methods=['GET'])
@handle_exceptions(log_prefix="get_transactions")
@log_route(logger)
def get_transactions():
    """Get all transactions with full party hierarchy."""
    is_valid, filters, error_msg = validate_transaction_filters(request.args.to_dict())
    if not is_valid:
        return error_response(error_msg, status_code=400)

    limit = filters.pop('limit')
    offset = filters.pop('offset')

    active_filters = {k: v for k, v in filters.items() if v is not None}
    if active_filters:
        logger.debug(f"Active filters: {active_filters}")

    repo = TransactionRepository()
    transactions = repo.get_transactions_with_hierarchy(limit=limit, offset=offset, **filters)

    logger.info(f"Retrieved {len(transactions)} transactions (offset={offset}, limit={limit})")
    return paginated_response(transactions, limit, offset, data_key='transactions')


@bp.route('/<int:transaction_id>', methods=['GET'])
@handle_exceptions(log_prefix="get_transaction")
@log_route(logger)
def get_transaction(transaction_id: int):
    """Get a specific transaction with full party hierarchy."""
    repo = TransactionRepository()
    transaction = repo.get_transaction_with_hierarchy(transaction_id)

    if transaction is None:
        logger.warning(f"Transaction {transaction_id} not found")
        return error_response(
            f'Transaction {transaction_id} not found',
            status_code=404
        )

    return success_response(data=transaction)


@bp.route('/<int:transaction_id>', methods=['PUT'])
@handle_exceptions(log_prefix="update_transaction")
@require_json
@log_route(logger)
def update_transaction(transaction_id: int):
    """Update a transaction."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_transaction_update(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

    repo = TransactionRepository()
    updated_transaction = repo.update_transaction(transaction_id, **validated_data)

    if updated_transaction is None:
        logger.warning(f"Transaction {transaction_id} not found")
        return error_response(f'Transaction {transaction_id} not found', status_code=404)

    logger.info(f"Updated transaction {transaction_id}: {list(validated_data.keys())}")
    return success_response(
        data=updated_transaction,
        message='Transaction updated successfully'
    )


@bp.route('/search', methods=['POST'])
@handle_exceptions(log_prefix="find_transactions")
@require_json
@log_route(logger)
def find_transactions():
    """Find transactions matching given parameters."""
    data = request.get_json() or {}

    error = require_at_least_one(
        data,
        ['amount', 'transaction_date', 'party_name'],
        'At least one of amount, transaction_date, or party_name is required'
    )
    if error:
        logger.warning(f"Search validation failed: {error}")
        return error_response(error, status_code=400)

    is_valid, search_params, error_msg = validate_transaction_search(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

    limit = search_params.pop('limit')

    logger.debug(
        f"Searching transactions: {search_params} | limit={limit}"
    )

    repo = TransactionRepository()
    transactions = repo.find_matching_transactions(limit=limit, **search_params)

    logger.info(f"Search returned {len(transactions)} matches")

    search_params['limit'] = limit
    return search_response(transactions, search_params, results_key='transactions')


@bp.route('/<int:transaction_id>/link-receipt', methods=['POST'])
@handle_exceptions(log_prefix="link_receipt")
@require_json
@log_route(logger)
def link_receipt(transaction_id: int):
    """Link a receipt to a transaction."""
    result = validate_positive_int('receipt_id', request.get_json().get('receipt_id'))
    if not result.is_valid:
        error_msg = result.error.message if result.error else 'receipt_id is required'
        logger.warning(f"Validation failed for transaction {transaction_id}: {error_msg}")
        return error_response(error_msg, status_code=400)

    receipt_id = result.value

    try:
        repo = TransactionRepository()
        updated_transaction = repo.link_receipt_to_transaction(
            transaction_id=transaction_id,
            receipt_id=receipt_id
        )

        if updated_transaction is None:
            logger.warning(f"Transaction {transaction_id} not found")
            return error_response(f'Transaction {transaction_id} not found', status_code=404)

        logger.info(f"Linked receipt {receipt_id} to transaction {transaction_id}")
        return success_response(
            data=updated_transaction,
            message=f'Receipt {receipt_id} linked to transaction {transaction_id} successfully'
        )
    except ValueError as e:
        logger.warning(f"Link failed for transaction {transaction_id} -> receipt {receipt_id}: {e}")
        return error_response(str(e), status_code=404)


@bp.route('/<int:transaction_id>/unlink-receipt', methods=['POST'])
@handle_exceptions(log_prefix="unlink_receipt")
@log_route(logger)
def unlink_receipt(transaction_id: int):
    """Unlink a receipt from a transaction."""
    repo = TransactionRepository()
    updated_transaction = repo.update_transaction(transaction_id=transaction_id, receipt_id=None)

    if updated_transaction is None:
        logger.warning(f"Transaction {transaction_id} not found")
        return error_response(f'Transaction {transaction_id} not found', status_code=404)

    logger.info(f"Unlinked receipt from transaction {transaction_id}")
    return success_response(
        data=updated_transaction,
        message=f'Receipt unlinked from transaction {transaction_id} successfully'
    )