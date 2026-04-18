from flask import Blueprint, request

from src.database.repositories.accounts import AccountRepository
from src.api.utils.response_helpers import success_response
from src.api.utils.route_helpers import handle_errors, require_json
from src.api.utils.errors import AppError, required, invalid_value, not_found
from src.api.utils.validators import RequestValidator, require_at_least_one
from src.utils.logging import ContextLogger, log_route
from src.statements.configs import STATEMENT_CONFIGS
from src.statements.registry import StatementFormatRegistry

bp = Blueprint('accounts', __name__)
logger = ContextLogger(__name__)


# ==================== Helper Functions ====================

def validate_statement_format_value(value: str) -> str | None:
    """
    Check a statement format identifier against the registry.
    Accepts tagged ids ("builtin:ptsb_current", "user:42") and
    bare built-in keys for backwards compatibility.
    Returns an error message if invalid, None if valid.
    """
    registry = StatementFormatRegistry()
    try:
        registry.get(value)
        return None
    except AppError as e:
        return e.message


def validate_create_account(data: dict) -> tuple[bool, dict, str]:
    """Validate account creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('account_name',
        validator.field('account_name').required().strip_string())
    validator.validate_field('account_type',
        validator.field('account_type').required().strip_string())
    validator.validate_field('statement_format',
        validator.field('statement_format').optional().strip_string())

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    validated = validator.validated
    if 'statement_format' in validated:
        error = validate_statement_format_value(validated['statement_format'])
        if error:
            logger.warning(f"Validation failed: {error}")
            return False, {}, error

    return True, validated, None


def validate_update_account(data: dict) -> tuple[bool, dict, str]:
    """Validate account update data."""
    logger.debug(f"Validating update data with keys: {list(data.keys())}")

    error = require_at_least_one(
        data,
        ['account_name', 'account_type', 'statement_format'],
        'At least one of account_name, account_type, or statement_format is required'
    )
    if error:
        logger.warning(f"Validation failed: {error}")
        return False, {}, error

    validator = RequestValidator(data)

    validator.validate_field('account_name',
        validator.field('account_name').optional().strip_string())
    validator.validate_field('account_type',
        validator.field('account_type').optional().strip_string())
    validator.validate_field('statement_format',
        validator.field('statement_format').optional().strip_string())

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    validated = validator.validated
    if 'statement_format' in validated:
        error = validate_statement_format_value(validated['statement_format'])
        if error:
            logger.warning(f"Validation failed: {error}")
            return False, {}, error

    return True, validated, None


# ==================== Routes ====================

@bp.route('', methods=['GET'])
@handle_errors(entity='Account')
@log_route(logger)
def get_accounts():
    """Get all accounts with optional filtering by type or statement format."""
    account_repo = AccountRepository()
    account_type = request.args.get('account_type')
    statement_format = request.args.get('statement_format')

    if account_type:
        logger.debug(f"Filtering by account_type: {account_type}")
        accounts = account_repo.get_accounts_by_type(account_type)
    elif statement_format:
        logger.debug(f"Filtering by statement_format: {statement_format}")
        accounts = account_repo.get_accounts_by_statement_format(statement_format)
    else:
        accounts = account_repo.get_all_accounts()

    logger.info(f"Retrieved {len(accounts)} accounts")
    return success_response(data=accounts)


@bp.route('/<int:account_id>', methods=['GET'])
@handle_errors(entity='Account')
@log_route(logger)
def get_account(account_id: int):
    """Get a single account by ID."""
    account_repo = AccountRepository()
    account = account_repo.get_account_by_id(account_id)

    if account is None:
        raise not_found('Account', account_id)

    return success_response(data=account)


@bp.route('', methods=['POST'])
@handle_errors(entity='Account')
@require_json
@log_route(logger)
def create_account():
    """Create a new account."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    is_valid, validated_data, error_msg = validate_create_account(data)
    if not is_valid:
        raise invalid_value(error_msg)

    account_repo = AccountRepository()
    account = account_repo.add_account(**validated_data)

    logger.info(f"Created account with id: {account['id']}")
    return success_response(
        data=account,
        message='Account created successfully',
        status_code=201
    )


@bp.route('/<int:account_id>', methods=['PUT'])
@handle_errors(entity='Account')
@require_json
@log_route(logger)
def update_account(account_id: int):
    """Update an existing account."""
    data = request.get_json()

    if not data:
        raise required('Request body')

    is_valid, validated_data, error_msg = validate_update_account(data)
    if not is_valid:
        raise invalid_value(error_msg)

    account_repo = AccountRepository()
    updated_account = account_repo.update_account(
        account_id=account_id,
        **validated_data
    )

    if updated_account is None:
        raise not_found('Account', account_id)

    logger.info(f"Updated account {account_id} fields: {list(validated_data.keys())}")
    return success_response(
        data=updated_account,
        message='Account updated successfully'
    )


@bp.route('/<int:account_id>', methods=['DELETE'])
@handle_errors(entity='Account')
@log_route(logger)
def delete_account(account_id: int):
    """Delete an account."""
    account_repo = AccountRepository()
    deleted = account_repo.delete_account(account_id)

    if not deleted:
        raise not_found('Account', account_id)

    return success_response(
        data={'deleted_id': account_id},
        message=f'Account {account_id} deleted successfully'
    )


@bp.route('/types', methods=['GET'])
@handle_errors(entity='Account')
@log_route(logger)
def get_account_types():
    """Get all distinct account types."""
    account_repo = AccountRepository()
    account_types = account_repo.get_distinct_account_types()

    logger.info(f"Retrieved {len(account_types)} account types")
    return success_response(data=account_types)


@bp.route('/statement-formats', methods=['GET'])
@handle_errors(entity='Statement format')
@log_route(logger)
def get_statement_formats():
    """Get all available statement format configurations."""
    formats = STATEMENT_CONFIGS
    format_list = [
        {"key": key, "name": key}
        for key in formats.keys()
    ]

    logger.info(f"Retrieved {len(format_list)} statement formats")
    return success_response(data=format_list)


@bp.route('/unconfigured', methods=['GET'])
@handle_errors(entity='Account')
@log_route(logger)
def get_unconfigured_accounts():
    """Get accounts that don't have a statement format configured."""
    account_repo = AccountRepository()
    accounts = account_repo.get_accounts_without_statement_format()

    logger.info(f"Retrieved {len(accounts)} unconfigured accounts")
    return success_response(data=accounts)


@bp.route('/<int:account_id>/transaction-count', methods=['GET'])
@handle_errors(entity='Account')
@log_route(logger)
def get_transaction_count(account_id: int):
    """Get the number of transactions for an account."""
    account_repo = AccountRepository()

    account = account_repo.get_account_by_id(account_id)
    if account is None:
        raise not_found('Account', account_id)

    count = account_repo.get_account_transaction_count(account_id)

    logger.info(f"Account {account_id} has {count} transactions")
    return success_response(data={'account_id': account_id, 'transaction_count': count})