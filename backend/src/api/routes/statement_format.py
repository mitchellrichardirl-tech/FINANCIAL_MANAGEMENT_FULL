# src/api/blueprints/statement_formats.py

from flask import Blueprint, request

from src.utils.logging import ContextLogger, log_route

from src.api.utils.response_helpers import success_response
from src.api.utils.route_helpers import handle_errors
from src.api.utils.errors import AppError, ErrorCode, invalid_value, not_found

from src.statements.base import (
    StatementConfig,
    ConfigurableStatementProcessor,
)
from src.statements.registry import StatementFormatRegistry

from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.database.repositories.statement_format import StatementFormatRepository
from src.database.repositories.accounts import AccountRepository
from src.database.connection import RecordNotFound

bp = Blueprint('statement_formats', __name__)
logger = ContextLogger(__name__)


# Cap on how many rows we'll run through the pipeline in a preview call.
# High enough to surface real data issues, low enough that the wizard
# stays snappy when the user iterates on the config.
PREVIEW_MAX_INPUT_ROWS = 200

# Cap on how many parsed rows we return to the client. The pipeline may
# drop rows (exclude_patterns, unparseable dates), so this is applied
# after processing.
PREVIEW_MAX_OUTPUT_ROWS = 50


@bp.route('/preview', methods=['POST'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def preview_format():
    """Run a draft config against sample rows without persisting anything.

    Body:
        {
            "config": {...},     # StatementConfig.to_dict() shape
            "rows":   [{...}],   # raw rows as returned by /files/preview
        }

    Returns:
        {
            "total_parsed": int,
            "preview_rows": [...],  # capped at PREVIEW_MAX_OUTPUT_ROWS
            "warnings":     [...],  # ProcessingWarning.to_dict() list
        }

    Raises (via handle_errors):
        AppError (INVALID_VALUE, 400):  Malformed request body.
        AppError (INVALID_FORMAT, 422): Config validation failed, or the
            processing pipeline rejected the rows (e.g. no columns
            matched, no dates parseable). The `details` dict carries
            structured info for the ColumnMismatchPanel.
    """
    body = request.get_json(silent=True) or {}
    config_dict = body.get('config')
    rows = body.get('rows')

    if not isinstance(config_dict, dict):
        raise invalid_value("Request body must contain a 'config' object.")
    if not isinstance(rows, list):
        raise invalid_value("Request body must contain a 'rows' array.")

    if len(rows) > PREVIEW_MAX_INPUT_ROWS:
        logger.debug(
            f"Truncating preview input from {len(rows)} to "
            f"{PREVIEW_MAX_INPUT_ROWS} rows"
        )
        rows = rows[:PREVIEW_MAX_INPUT_ROWS]

    # StatementConfig.__post_init__ does shape + defaults validation.
    # Translate ValueError into a structured AppError so the UI can
    # point at the offending field.
    try:
        config = StatementConfig.from_dict(config_dict)
    except (ValueError, TypeError) as e:
        raise invalid_value(f"Invalid statement config: {e}")

    logger.info(
        f"Previewing config {config.display_name!r} against {len(rows)} rows"
    )

    # Dummy ids — nothing is persisted. A real categorizer is used so
    # the preview reflects what the user would actually get.
    processor = ConfigurableStatementProcessor(
        statement_config=config,
        account_id=-1,
        upload_id=-1,
        categorizer=TransactionCategorizer(),
    )

    # AppError raised here (missing columns, unparseable dates, etc.)
    # propagates to handle_errors with its full details dict intact.
    transactions_df = processor.process_statement(rows)

    preview_rows = (
        transactions_df.head(PREVIEW_MAX_OUTPUT_ROWS)
        .to_dict(orient='records')
    )

    logger.info(
        f"Preview complete: {len(transactions_df)} parsed, "
        f"{len(processor.warnings)} warning(s)"
    )

    return success_response({
        'total_parsed': int(len(transactions_df)),
        'preview_rows': preview_rows,
        'warnings': [w.to_dict() for w in processor.warnings],
    })

# =============================================================================
# Schema — metadata the wizard needs to render its form
# =============================================================================

@bp.route('/schema', methods=['GET'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def get_schema():
    """Return metadata about the StatementConfig shape.

    Used by the frontend wizard to render inputs dynamically — in
    particular the set of fields that may have a config-level default
    applied. Centralizing this means adding a new allowed default on
    the backend doesn't require a frontend change.

    Returns:
        {
            "allowed_defaults": [
                {"name": "is_kids",    "type": "bool"},
                {"name": "is_one_off", "type": "bool"},
            ],
        }
    """
    return success_response({
        'allowed_defaults': [
            {'name': name, 'type': typ.__name__}
            for name, typ in StatementConfig.ALLOWED_DEFAULT_FIELDS.items()
        ],
    })


# =============================================================================
# Read
# =============================================================================

@bp.route('', methods=['GET'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def list_formats():
    """List every known statement format, built-in and user-defined.

    Returns summary metadata only — use GET /<identifier> to fetch a
    full config for editing. Malformed stored rows are skipped by the
    registry so this endpoint stays functional even if one DB row is
    corrupt.
    """
    registry = StatementFormatRegistry()
    formats = registry.list_all()
    logger.debug(f"Listed {len(formats)} statement format(s)")
    return success_response({'formats': formats})


@bp.route('/<identifier>', methods=['GET'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def get_format(identifier: str):
    """Return the full config for a single statement format.

    Args:
        identifier: Tagged identifier as used by the registry
            (e.g. "user:42" or "builtin:ptsb_current").

    Raises:
        AppError (NOT_FOUND):       No format with that identifier.
        AppError (INVALID_FORMAT):  Stored config is malformed or no
            longer conforms to the current schema (user formats only).
    """
    registry = StatementFormatRegistry()
    handle = registry.get(identifier)

    return success_response({
        'identifier': handle.identifier,
        'source': handle.source,
        'editable': handle.editable,
        'has_custom_processor': handle.custom_processor_cls is not None,
        'config': handle.config.to_dict(),
    })


# =============================================================================
# Write helpers
# =============================================================================

def _parse_config_from_body() -> StatementConfig:
    """Pull a validated StatementConfig out of the request body.

    Raises:
        AppError (INVALID_VALUE): Body missing or config invalid.
    """
    body = request.get_json(silent=True) or {}
    config_dict = body.get('config')

    if not isinstance(config_dict, dict):
        raise invalid_value("Request body must contain a 'config' object.")

    try:
        return StatementConfig.from_dict(config_dict)
    except (ValueError, TypeError) as e:
        raise invalid_value(f"Invalid statement config: {e}")


def _assert_no_collision(
    config: StatementConfig,
    repo: StatementFormatRepository,
    registry: StatementFormatRegistry,
    ignore_format_id: int | None = None,
) -> None:
    """Refuse if the config's display_name collides with a built-in
    or an existing user format.

    Args:
        config: The incoming config.
        repo: For the user-format lookup.
        registry: For the built-in display name set.
        ignore_format_id: On update, skip collisions against this id
            (a format can't collide with itself).

    Raises:
        AppError (CONFLICT, 409): Either kind of collision.
    """
    if config.display_name in registry.builtin_display_names():
        raise AppError(
            code=ErrorCode.CONFLICT,
            message=(
                f"A built-in format named '{config.display_name}' already "
                f"exists. Change the bank name or account type."
            ),
            status_code=409,
            entity='StatementFormat',
        )

    clash = repo.get_format_by_bank_and_type(
        config.bank_name, config.account_type
    )
    if clash and clash['id'] != ignore_format_id:
        raise AppError(
            code=ErrorCode.CONFLICT,
            message=(
                f"A statement format for '{config.display_name}' already "
                f"exists."
            ),
            status_code=409,
            entity='StatementFormat',
        )


# =============================================================================
# Create
# =============================================================================

@bp.route('', methods=['POST'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def create_format():
    """Create a new user-defined statement format.

    Body:
        { "config": { ...StatementConfig.to_dict() shape... } }

    Returns 201 with the created row and its tagged identifier.

    Raises:
        AppError (INVALID_VALUE, 400): Body or config invalid.
        AppError (CONFLICT, 409):      Display name collides with a
            built-in or existing user format.
    """
    config = _parse_config_from_body()

    repo = StatementFormatRepository()
    registry = StatementFormatRegistry()
    _assert_no_collision(config, repo, registry)

    row = repo.add_format(
        bank_name=config.bank_name,
        account_type=config.account_type,
        config_json=config.to_dict(),
    )

    logger.info(
        f"Created statement format {row['id']}: {config.display_name}"
    )

    return success_response({
        'identifier': f'user:{row["id"]}',
        'id': row['id'],
        'source': 'user',
        'editable': True,
        'config': row['config_json'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }, status_code=201)


# =============================================================================
# Update
# =============================================================================

@bp.route('/<int:format_id>', methods=['PUT'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def update_format(format_id: int):
    """Replace a user-defined statement format.

    The entire config is replaced — this is a PUT, not a PATCH.
    Callers should fetch the current config, mutate it, and send the
    full object back.

    Body:
        { "config": { ...StatementConfig.to_dict() shape... } }

    Raises:
        AppError (INVALID_VALUE, 400): Body or config invalid.
        AppError (NOT_FOUND, 404):     No format with that id.
        AppError (CONFLICT, 409):      New display name collides with
            a built-in or another user format.
    """
    new_config = _parse_config_from_body()

    repo = StatementFormatRepository()
    registry = StatementFormatRegistry()

    # Confirm the target exists first, so we raise 404 rather than
    # pretending to update something that isn't there.
    try:
        existing = repo.get_format_by_id(format_id)
    except RecordNotFound:
        raise not_found('StatementFormat', format_id)

    # Only run the collision check if identity columns actually changed
    # — otherwise a pure config edit would falsely collide with itself.
    identity_changed = (
        new_config.bank_name != existing['bank_name']
        or new_config.account_type != existing['account_type']
    )
    if identity_changed:
        _assert_no_collision(
            new_config, repo, registry, ignore_format_id=format_id
        )

    updated = repo.update_format(
        format_id=format_id,
        bank_name=new_config.bank_name,
        account_type=new_config.account_type,
        config_json=new_config.to_dict(),
    )

    logger.info(
        f"Updated statement format {format_id}: {new_config.display_name}"
    )

    return success_response({
        'identifier': f'user:{format_id}',
        'id': format_id,
        'source': 'user',
        'editable': True,
        'config': updated['config_json'],
        'updated_at': updated['updated_at'],
    })


# =============================================================================
# Delete
# =============================================================================

@bp.route('/<int:format_id>', methods=['DELETE'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def delete_format(format_id: int):
    """Delete a user-defined statement format.

    Refuses deletion if any accounts still reference the format —
    better to fail loudly than orphan the reference, because the
    account's upload flow would then break silently on the next import.

    Raises:
        AppError (NOT_FOUND, 404): No format with that id.
        AppError (CONFLICT, 409):  Format is referenced by one or more
            accounts. The error message lists which ones.
    """
    repo = StatementFormatRepository()
    identifier = f'user:{format_id}'

    # Check account references before touching the row. AccountRepository
    # already has a get-by-format-string method we can reuse.
    account_repo = AccountRepository()
    linked = account_repo.get_accounts_by_statement_format(identifier)
    if linked:
        names = ', '.join(a['account_name'] for a in linked)
        logger.warning(
            f"Refusing to delete format {format_id}: "
            f"referenced by {len(linked)} account(s)"
        )
        raise AppError(
            code=ErrorCode.CONFLICT,
            message=(
                f"Cannot delete this format: it is used by "
                f"{len(linked)} account(s): {names}. "
                f"Reassign those accounts first."
            ),
            status_code=409,
            entity='StatementFormat',
            details={'linked_accounts': [a['id'] for a in linked]},
        )

    deleted = repo.delete_format(format_id)
    if not deleted:
        raise not_found('StatementFormat', format_id)

    logger.info(f"Deleted statement format {format_id}")
    return success_response({'deleted': True, 'id': format_id})