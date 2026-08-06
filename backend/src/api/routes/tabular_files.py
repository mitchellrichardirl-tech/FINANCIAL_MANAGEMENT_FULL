from pathlib import Path

from flask import Blueprint, request

from src.utils.tabular_files.processor import TabularProcessor
from src.utils.tabular_files.exceptions import handle_tabular_errors

from src.api.utils.file_handling import FileValidationResult
from src.api.utils.response_helpers import success_response, paginated_response
from src.api.utils.route_helpers import (
    with_uploaded_file,
    TabularValidationParams,
    TabularPreviewParams,
    TabularImportParams,
    handle_errors,
)
from src.api.utils.errors import invalid_value, not_found, required
from src.api.utils.validators import (
    validate_pagination,
    validate_date_range_filters,
    add_string_filters,
)

from src.statements.registry import get_processor

from src.database.repositories.uploads import UploadRepository
from src.database.repositories.transactions import TransactionRepository
from src.database.repositories.accounts import AccountRepository

from src.utils.logging import ContextLogger, log_route

bp = Blueprint('tabular_files', __name__)
logger = ContextLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _process_tabular_file(temp_path: Path, params: TabularImportParams):
    """Extract and validate tabular data."""
    logger.debug(
        f"Importing tabular data from {temp_path.name} "
        f"| start_row={params.start_row} | has_header={params.has_header}"
    )

    processor = TabularProcessor()
    result = processor.import_data(
        temp_path,
        start_row=params.start_row,
        columns=params.columns,
        column_names=params.column_names,
        has_header=params.has_header,
        sheet_name=params.sheet_name,
        max_rows=params.max_rows,
        skip_empty_rows=params.skip_empty_rows,
        strip_whitespace=params.strip_whitespace,
    )

    logger.debug(
        f"Imported {len(result.data)} rows, "
        f"{len(result.columns_imported)} columns from {temp_path.name}"
    )
    return result


def _create_upload_record(result, original_filename) -> int:
    """Persist upload metadata and return upload_id."""
    logger.debug(f"Creating upload record for: {original_filename}")

    upload_repo = UploadRepository()
    upload_result = upload_repo.create_upload_with_data(
        original_filename=original_filename,
        filename=result.file_name,
        file_type=result.file_type,
        columns=result.columns_imported,
        rows=result.data,
    )

    upload_id = upload_result["upload_id"]
    logger.debug(f"Created upload record with id: {upload_id}")
    return upload_id


def _process_as_statement(result, account_id: int, upload_id: int):
    """Process imported data as a bank statement."""
    logger.info(
        f"Processing upload {upload_id} as statement "
        f"for account {account_id} | {len(result.data)} rows"
    )

    account_repo = AccountRepository()
    account = account_repo.get_account_by_id(account_id)

    if account is None:
        raise not_found('Account', account_id)

    logger.debug(
        f"Account {account_id} statement format: {account['statement_format']}"
    )

    statement = get_processor(
        identifier=account['statement_format'],
        account_id=account_id,
        upload_id=upload_id,
    )
    transactions = statement.process_statement(result.data)

    transaction_repo = TransactionRepository()
    transaction_repo.bulk_add_transactions(transactions)

    logger.info(
        f"Created {len(transactions)} transactions "
        f"for account {account_id} from upload {upload_id}"
    )

    return statement.warnings


def validate_upload_filters(args) -> dict:
    """
    Validate upload query filters.
    Raises AppError on invalid input.
    """
    logger.debug(f"Validating upload filters: {list(args.keys())}")

    is_valid, pagination, error = validate_pagination(args)
    if not is_valid:
        logger.warning(f"Pagination validation failed: {error}")
        raise invalid_value(error)

    is_valid, date_filters, error = validate_date_range_filters(args)
    if not is_valid:
        logger.warning(f"Date range validation failed: {error}")
        raise invalid_value(error)

    filters = {}
    add_string_filters(filters, args, ['file_type', 'filename'])

    return {**pagination, **date_filters, **filters}

def _resolve_account(account_id: int) -> dict:
    """Look up and validate the account before anything is committed.
    Called *before* `_create_upload_record()` so that a bad `account_id`
    or an unconfigured statement format fails the request without leaving
    an orphaned upload behind. Compensating deletes are for failures we
    can't predict; this one we can.
    Args:
        account_id: Primary key of the account to import against.
    Returns:
        The account dict.
    Raises:
        not_found: If the account doesn't exist.
        invalid_value: If the account has no statement format configured.
    """
    account_repo = AccountRepository()
    account = account_repo.get_account_by_id(account_id)
    if account is None:
        raise not_found('Account', account_id)
    if not account.get('statement_format'):
        raise invalid_value(
            f"Account {account_id} has no statement_format configured",
            field='account_id',
        )
    logger.debug(
        f"Account {account_id} statement format: {account['statement_format']}"
    )
    return account

def _process_as_statement(result, account: dict, upload_id: int):
    """Process imported data as a bank statement.
    Everything here runs *after* the upload has been committed. If any of
    it raises, the caller discards the upload — so nothing in this function
    may leave partial state behind. `bulk_add_transactions()` is atomic,
    which is what makes that safe.
    Args:
        result: The `TabularProcessor` import result.
        account: Account dict from `_resolve_account()`.
        upload_id: The committed upload's primary key.
    Returns:
        List of warnings emitted by the statement processor.
    """
    account_id = account['id']
    logger.info(
        f"Processing upload {upload_id} as statement "
        f"for account {account_id} | {len(result.data)} rows"
    )
    statement = get_processor(
        identifier=account['statement_format'],
        account_id=account_id,
        upload_id=upload_id,
    )
    transactions = statement.process_statement(result.data)
    transaction_repo = TransactionRepository()
    transaction_repo.bulk_add_transactions(transactions)
    logger.info(
        f"Created {len(transactions)} transactions "
        f"for account {account_id} from upload {upload_id}"
    )
    return statement.warnings

def _discard_orphaned_upload(upload_id: int) -> None:
    """Remove an upload whose statement processing failed.
    Compensating delete for the gap between `create_upload_with_data()`
    committing and `bulk_add_transactions()` committing. Without this, a
    failure in statement processing leaves an upload with raw `upload_data`
    rows and zero transactions — invisible to `GET /uploads` under the
    live-transactions filter, and therefore undeletable through the UI.
    Called from an exception handler, so it must never raise: masking the
    original error with a cleanup error would be strictly worse.
    Args:
        upload_id: The upload to remove. `upload_data` rows cascade.
    """
    try:
        UploadRepository().delete_upload(upload_id)
        logger.warning(
            f"Discarded orphaned upload {upload_id} "
            f"after statement processing failed"
        )
    except Exception as cleanup_error:
        logger.error(
            f"Failed to discard orphaned upload {upload_id}: {cleanup_error}. "
            f"The upload and its upload_data rows remain in the database and "
            f"will not appear in GET /uploads."
        )

# =============================================================================
# File Processing Endpoints
# =============================================================================
# Decorator order (top → bottom = outer → inner):
#   @handle_errors         ← catches AppError, DatabaseError, anything else
#   @handle_tabular_errors ← catches TabularProcessorError first (more specific)
#   @with_uploaded_file    ← provides temp_path, file_info
#   @log_route             ← innermost, logs timing
#
# An exception bubbles inner→outer, so tabular errors are caught by
# handle_tabular_errors before reaching handle_errors. Everything else
# (bad account_id, DB failures in _create_upload_record, etc.) falls
# through to handle_errors.

@bp.route('/validate', methods=['POST'])
@handle_errors(entity='File')
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
@log_route(logger)
def validate_file(temp_path: Path, file_info: FileValidationResult):
    """Validate a tabular file."""
    params = TabularValidationParams.from_form(request.form)

    logger.info(f"Validating file: {file_info.secured_filename}")
    logger.debug(
        f"Validation params: min_rows={params.min_rows}, "
        f"min_columns={params.min_columns}, sheet={params.sheet_name}"
    )

    processor = TabularProcessor()
    result = processor.validate(
        temp_path,
        min_rows=params.min_rows,
        min_columns=params.min_columns,
        required_columns=params.required_columns,
        sheet_name=params.sheet_name,
    )

    logger.info(
        f"Validation result for {file_info.secured_filename}: "
        f"valid={result.is_valid}"
    )
    return success_response(result.to_dict())


@bp.route('/preview', methods=['POST'])
@handle_errors(entity='File')
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
@log_route(logger)
def preview_file(temp_path: Path, file_info: FileValidationResult):
    """Get a preview of tabular file contents."""
    params = TabularPreviewParams.from_form(request.form)

    logger.info(f"Previewing file: {file_info.secured_filename}")
    logger.debug(
        f"Preview params: num_rows={params.num_rows}, "
        f"sheet={params.sheet_name}, include_types={params.include_types}"
    )

    processor = TabularProcessor()
    result = processor.preview(
        temp_path,
        num_rows=params.num_rows,
        sheet_name=params.sheet_name,
        include_types=params.include_types,
    )

    logger.info(
        f"Preview generated for {file_info.secured_filename}: "
        f"{result.total_rows} total rows"
    )
    return success_response(result.to_dict())


@bp.route('/import', methods=['POST'])
@handle_errors(entity='Upload')
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xlsx', 'xls'})
@log_route(logger)
def import_file(temp_path: Path, file_info: FileValidationResult):
    """Import a bank statement and create its transactions.

    `account_id` is mandatory. An import that produces no transactions would
    leave an upload that `GET /uploads` filters out (it has no live
    transactions) and that therefore cannot be deleted through the UI — so
    the request is rejected rather than allowed to create one.

    Ordering is load-bearing:
        1. Validate the account           — before anything is committed.
        2. Parse the file                 — before anything is committed.
        3. Commit the upload + raw rows.
        4. Create transactions            — on failure, discard step 3.

    A 2xx response therefore always means "upload exists and has
    transactions"; any error response means nothing was persisted.
    """
    original_filename = request.form.get('original_filename', temp_path.name)
    params = TabularImportParams.from_form(request.form)

    # Account ids are AUTOINCREMENT from 1, so a falsy value is always absent
    # or invalid. The frontend blocks this, but an upload is expensive to
    # half-create, so don't rely on that.
    if not params.account_id:
        raise required('account_id')
    
    logger.info(
        f"Importing file: {original_filename} | account_id={params.account_id}"
    )

    # Fail before committing anything we'd have to clean up.
    account = _resolve_account(params.account_id)

    result = _process_tabular_file(temp_path, params)

    # --- Everything below this line touches the database ---
    upload_id = _create_upload_record(result, original_filename)
    result.upload_id = upload_id
    result.file_name = original_filename

    try:
        warnings = _process_as_statement(result, account, upload_id)
    except Exception:
        # Catch everything, not just DatabaseError: bulk_add_transactions()
        # raises a bare ValueError for missing columns, and process_statement()
        # can raise whatever the parsers throw.
        _discard_orphaned_upload(upload_id)
        raise

    # Deliberately outside the try. The transactions are committed by now, so a
    # serialization failure here must not delete a perfectly good upload.
    if warnings:
        result.warnings = [warning.to_dict() for warning in warnings]
        
    logger.info(
        f"Import complete: upload_id={upload_id} | "
        f"{len(result.data)} rows, {len(result.columns_imported)} columns"
    )
    return success_response(result.to_dict())


@bp.route('/sheets', methods=['POST'])
@handle_errors(entity='File')
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'xls', 'xlsx'})
@log_route(logger)
def get_sheets(temp_path: Path, file_info: FileValidationResult):
    """Get sheet names from an Excel file."""
    logger.info(f"Getting sheet info for: {file_info.secured_filename}")

    processor = TabularProcessor()
    result = processor.get_sheet_info(temp_path)

    logger.info(
        f"Found {len(result.sheets)} sheets in {file_info.secured_filename}"
    )
    return success_response(result.to_dict())


@bp.route('/check', methods=['POST'])
@handle_errors(entity='File')
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
@log_route(logger)
def check_tabular(temp_path: Path, file_info: FileValidationResult):
    """Quick check if a file is valid tabular data."""
    processor = TabularProcessor()
    is_tabular = processor.is_tabular(temp_path)

    logger.info(
        f"Tabular check for {file_info.secured_filename}: "
        f"is_tabular={is_tabular}"
    )
    return success_response({
        'is_tabular': is_tabular,
        'file_name': file_info.secured_filename,
    })


# =============================================================================
# Upload CRUD Endpoints
# =============================================================================

@bp.route('', methods=['GET'])
@handle_errors(entity='Upload')
@log_route(logger)
def get_uploads():
    """Get all uploads with optional filters."""
    filters = validate_upload_filters(request.args.to_dict())

    limit = filters.pop('limit')
    offset = filters.pop('offset')

    active_filters = {k: v for k, v in filters.items() if v is not None}
    if active_filters:
        logger.debug(f"Active filters: {active_filters}")

    upload_repo = UploadRepository()
    uploads = upload_repo.get_all_uploads(limit=limit, offset=offset, **filters)

    logger.info(f"Retrieved {len(uploads)} uploads (offset={offset}, limit={limit})")
    return paginated_response(uploads, limit, offset, data_key='uploads')


@bp.route('/<int:upload_id>', methods=['GET'])
@handle_errors(entity='Upload')
@log_route(logger)
def get_upload(upload_id: int):
    """Get a single upload by ID."""
    upload_repo = UploadRepository()
    upload = upload_repo.get_upload_by_id(upload_id)

    if upload is None:
        raise not_found('Upload', upload_id)

    return success_response(data=upload)


@bp.route('/<int:upload_id>', methods=['DELETE'])
@handle_errors(entity='Upload')
@log_route(logger)
def delete_upload(upload_id: int):
    """Delete an upload and all associated data."""
    upload_repo = UploadRepository()
    deleted = upload_repo.delete_upload(upload_id)

    if not deleted:
        raise not_found('Upload', upload_id)

    return success_response(
        data={'deleted_upload_id': upload_id},
        message=f'Upload {upload_id} deleted successfully',
    )