from pathlib import Path
from datetime import datetime

from flask import Blueprint, request, jsonify

from src.utils.tabular_files.processor import TabularProcessor
from src.utils.tabular_files.exceptions import handle_tabular_errors

from src.api.utils.file_handling import FileValidationResult
from src.api.utils.response_helpers import success_response, error_response, paginated_response
from src.api.utils.route_helpers import (
    with_uploaded_file,
    TabularValidationParams,
    TabularPreviewParams,
    TabularImportParams,
    handle_exceptions
)
from src.api.utils.validators import (
    validate_pagination,
    validate_date_range_filters,
    add_string_filters
)

from src.statements.statement import Statement

from src.database.repositories.uploads import UploadRepository
from src.database.repositories.transactions import TransactionRepository
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
        rows=result.data
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

    statement = Statement(account_id=account_id, upload_id=upload_id)
    transactions = statement.process_statement(result.data)

    transaction_repo = TransactionRepository()
    transaction_repo.bulk_add_transactions(transactions)

    logger.info(
        f"Created {len(transactions)} transactions "
        f"for account {account_id} from upload {upload_id}"
    )


def validate_upload_filters(args) -> tuple[bool, dict, str]:
    """Validate upload query filters."""
    logger.debug(f"Validating upload filters: {list(args.keys())}")

    # Validate pagination
    is_valid, pagination, error = validate_pagination(args)
    if not is_valid:
        logger.warning(f"Pagination validation failed: {error}")
        return False, {}, error

    # Validate date range
    is_valid, date_filters, error = validate_date_range_filters(args)
    if not is_valid:
        logger.warning(f"Date range validation failed: {error}")
        return False, {}, error

    # String filters
    filters = {}
    add_string_filters(filters, args, ['file_type', 'filename'])

    return True, {**pagination, **date_filters, **filters}, None


# =============================================================================
# File Processing Endpoints
# =============================================================================

@bp.route('/validate', methods=['POST'])
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
        sheet_name=params.sheet_name
    )

    logger.info(
        f"Validation result for {file_info.secured_filename}: "
        f"valid={result.is_valid}"
    )
    return success_response(result.to_dict())


@bp.route('/preview', methods=['POST'])
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
        include_types=params.include_types
    )

    logger.info(
        f"Preview generated for {file_info.secured_filename}: "
        f"{result.total_rows} total rows"
    )
    return success_response(result.to_dict())


@bp.route('/import', methods=['POST'])
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xlsx', 'xls'})
@log_route(logger)
def import_file(temp_path: Path, file_info: FileValidationResult):
    """Import a tabular file and optionally process as statement."""
    original_filename = request.form.get('original_filename', temp_path.name)
    params = TabularImportParams.from_form(request.form)

    logger.info(
        f"Importing file: {original_filename} "
        f"| account_id={params.account_id or 'none'}"
    )

    # Step 1: Import tabular data
    result = _process_tabular_file(temp_path, params)

    # Step 2: Create upload record
    upload_id = _create_upload_record(result, original_filename)
    result.upload_id = upload_id
    result.file_name = original_filename

    # Step 3: Process as statement (if account_id provided)
    if params.account_id:
        _process_as_statement(result, params.account_id, upload_id)
    else:
        logger.debug("No account_id provided, skipping statement processing")

    logger.info(
        f"Import complete: upload_id={upload_id} | "
        f"{len(result.data)} rows, {len(result.columns_imported)} columns"
    )
    return success_response(result.to_dict())


@bp.route('/sheets', methods=['POST'])
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
        'file_name': file_info.secured_filename
    })


# =============================================================================
# Upload CRUD Endpoints
# =============================================================================

@bp.route('', methods=['GET'])
@handle_exceptions(log_prefix="get_uploads")
@log_route(logger)
def get_uploads():
    """Get all uploads with optional filters."""
    # Validate filters
    is_valid, filters, error_msg = validate_upload_filters(request.args.to_dict())
    if not is_valid:
        return error_response(error_msg, status_code=400)

    # Extract pagination
    limit = filters.pop('limit')
    offset = filters.pop('offset')

    active_filters = {k: v for k, v in filters.items() if v is not None}
    if active_filters:
        logger.debug(f"Active filters: {active_filters}")

    # Get uploads
    upload_repo = UploadRepository()
    uploads = upload_repo.get_all_uploads(
        limit=limit,
        offset=offset,
        **filters
    )

    logger.info(f"Retrieved {len(uploads)} uploads (offset={offset}, limit={limit})")
    return paginated_response(uploads, limit, offset, data_key='uploads')


@bp.route('/<int:upload_id>', methods=['GET'])
@handle_exceptions(log_prefix="get_upload")
@log_route(logger)
def get_upload(upload_id: int):
    """Get a single upload by ID."""
    upload_repo = UploadRepository()
    upload = upload_repo.get_upload_by_id(upload_id)

    if upload is None:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    return success_response(data=upload)


@bp.route('/<int:upload_id>', methods=['DELETE'])
@handle_exceptions(log_prefix="delete_upload")
@log_route(logger)
def delete_upload(upload_id: int):
    """Delete an upload and all associated data."""
    upload_repo = UploadRepository()
    deleted = upload_repo.delete_upload(upload_id)

    if not deleted:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    return success_response(
        data={'deleted_upload_id': upload_id},
        message=f'Upload {upload_id} deleted successfully'
    )