from pathlib import Path
from pathlib import Path
from datetime import datetime

from flask import Blueprint, request, jsonify
import logging

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

bp = Blueprint('tabular_files', __name__)
logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _process_tabular_file(temp_path: Path, params: TabularImportParams):
    """Extract and validate tabular data."""
    processor = TabularProcessor()
    return processor.import_data(
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


def _create_upload_record(result, original_filename) -> int:
    """Persist upload metadata and return upload_id."""
    upload_repo = UploadRepository()
    upload_result = upload_repo.create_upload_with_data(
        original_filename=original_filename,
        filename=result.file_name,
        file_type=result.file_type,
        columns=result.columns_imported,
        rows=result.data
    )
    return upload_result["upload_id"]


def _process_as_statement(result, account_id: int, upload_id: int):
    """Process imported data as a bank statement."""
    statement = Statement(account_id=account_id, upload_id=upload_id)
    transactions = statement.process_statement(result.data)
    
    transaction_repo = TransactionRepository()
    transaction_repo.bulk_add_transactions(transactions)


def validate_upload_filters(args) -> tuple[bool, dict, str]:
    """Validate upload query filters."""
    # Validate pagination
    is_valid, pagination, error = validate_pagination(args)
    if not is_valid:
        return False, {}, error
    
    # Validate date range
    is_valid, date_filters, error = validate_date_range_filters(args)
    if not is_valid:
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
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
def validate_file(temp_path: Path, file_info: FileValidationResulttemp_path: Path, file_info: FileValidationResult):
    """
    Validate a tabular file.
    
    Request:
        - file: Uploaded file (multipart/form-data)
        - min_rows: Optional minimum row requirement
        - min_columns: Optional minimum column requirement
        - required_columns: Optional comma-separated list of required columns
        - sheet_name: Optional sheet name for Excel files
        
    Returns:
        ValidationResult as JSON
    """
    params = TabularValidationParams.from_form(request.form)
    
    processor = TabularProcessor()
    result = processor.validate(
        temp_path,
        min_rows=params.min_rows,
        min_columns=params.min_columns,
        required_columns=params.required_columns,
        sheet_name=params.sheet_name
    )

    return success_response(result.to_dict())
    params = TabularValidationParams.from_form(request.form)
    
    processor = TabularProcessor()
    result = processor.validate(
        temp_path,
        min_rows=params.min_rows,
        min_columns=params.min_columns,
        required_columns=params.required_columns,
        sheet_name=params.sheet_name
    )

    return success_response(result.to_dict())


@bp.route('/preview', methods=['POST'])
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
def preview_file(temp_path: Path, file_info: FileValidationResulttemp_path: Path, file_info: FileValidationResult):
    """
    Get a preview of tabular file contents.
    
    Request:
        - file: Uploaded file
        - num_rows: Number of rows to preview (default: 10)
        - sheet_name: Optional sheet name for Excel files
        - include_types: Whether to include column type detection (default: true)
        
    Returns:
        PreviewResult as JSON
    """
    params = TabularPreviewParams.from_form(request.form)
    
    processor = TabularProcessor()
    result = processor.preview(
        temp_path,
        num_rows=params.num_rows,
        sheet_name=params.sheet_name,
        include_types=params.include_types
    )

    return success_response(result.to_dict())
    params = TabularPreviewParams.from_form(request.form)
    
    processor = TabularProcessor()
    result = processor.preview(
        temp_path,
        num_rows=params.num_rows,
        sheet_name=params.sheet_name,
        include_types=params.include_types
    )

    return success_response(result.to_dict())


@bp.route('/import', methods=['POST'])
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xlsx', 'xls'})
def import_file(temp_path: Path, file_info: FileValidationResult):
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xlsx', 'xls'})
def import_file(temp_path: Path, file_info: FileValidationResult):
    """
    Import a tabular file and optionally process as statement.
    
    Request:
        - file: Uploaded file
        - start_row: Row to start import from (default: 0)
        - has_header: Whether first row is header (default: true)
        - columns: Comma-separated column indices to import
        - column_names: Comma-separated custom column names
        - sheet_name: Optional sheet name for Excel files
        - account_id: Optional account ID to process as statement
        
    Returns:
        ImportResult as JSON
    """
    original_filename = request.form.get('original_filename', temp_path.name)
    params = TabularImportParams.from_form(request.form)
    
    # Step 1: Import tabular data
    result = _process_tabular_file(temp_path, params)
    
    # Step 2: Create upload record
    upload_id = _create_upload_record(
        result,
        original_filename
    )
    result.upload_id = upload_id
    result.file_name = original_filename

    # Step 3: Process as statement (if account_id provided)
    if params.account_id:
        _process_as_statement(result, params.account_id, upload_id)
    
    return success_response(result.to_dict())


@bp.route('/sheets', methods=['POST'])
@with_uploaded_file(allowed_extensions={'xls', 'xlsx'})
def get_sheets(temp_path: Path, file_info: FileValidationResult):
@with_uploaded_file(allowed_extensions={'xls', 'xlsx'})
def get_sheets(temp_path: Path, file_info: FileValidationResult):
    """
    Get sheet names from an Excel file.
    
    Request:
        - file: Uploaded Excel file
        
    Returns:
        SheetInfo as JSON
    """
    processor = TabularProcessor()
    result = processor.get_sheet_info(temp_path)
    
    return success_response(result.to_dict())


@bp.route('/check', methods=['POST'])
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
def check_tabular(temp_path: Path, file_info: FileValidationResult):
@handle_tabular_errors
@with_uploaded_file(allowed_extensions={'csv', 'tsv', 'xls', 'xlsx'})
def check_tabular(temp_path: Path, file_info: FileValidationResult):
    """
    Quick check if a file is valid tabular data.
    
    Request:
        - file: Uploaded file
        
    Returns:
        {
            "is_tabular": true/false,
            "file_name": "filename.csv"
        }
    """
    processor = TabularProcessor()
    is_tabular = processor.is_tabular(temp_path)
    
    return success_response({
        'is_tabular': is_tabular,
        'file_name': file_info.secured_filename
    })


# =============================================================================
# Upload CRUD Endpoints
# =============================================================================
    processor = TabularProcessor()
    is_tabular = processor.is_tabular(temp_path)
    
    return success_response({
        'is_tabular': is_tabular,
        'file_name': file_info.secured_filename
    })


# =============================================================================
# Upload CRUD Endpoints
# =============================================================================

@bp.route('', methods=['GET'])
@handle_exceptions(log_prefix="get_uploads")
@handle_exceptions(log_prefix="get_uploads")
def get_uploads():
    """
    Get all uploads with optional filters.
    
    Query Parameters:
        - limit: Maximum number of results (default: 50)
        - offset: Pagination offset (default: 0)
        - file_type: Filter by file type
        - filename: Filter by filename (partial match)
        - start_date: Filter uploads from this date (YYYY-MM-DD)
        - end_date: Filter uploads until this date (YYYY-MM-DD)
        
    Returns:
        List of upload objects as JSON
    """
    # Validate filters
    is_valid, filters, error_msg = validate_upload_filters(request.args.to_dict())
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    # Extract pagination
    limit = filters.pop('limit')
    offset = filters.pop('offset')
    
    # Get uploads
    upload_repo = UploadRepository()
    uploads = upload_repo.get_all_uploads(
        limit=limit,
        offset=offset,
        **filters
    )
    
    return paginated_response(uploads, limit, offset, data_key='uploads')
    # Validate filters
    is_valid, filters, error_msg = validate_upload_filters(request.args.to_dict())
    if not is_valid:
        return error_response(error_msg, status_code=400)
    
    # Extract pagination
    limit = filters.pop('limit')
    offset = filters.pop('offset')
    
    # Get uploads
    upload_repo = UploadRepository()
    uploads = upload_repo.get_all_uploads(
        limit=limit,
        offset=offset,
        **filters
    )
    
    return paginated_response(uploads, limit, offset, data_key='uploads')


@bp.route('/<int:upload_id>', methods=['GET'])
@handle_exceptions(log_prefix="get_upload")
@handle_exceptions(log_prefix="get_upload")
def get_upload(upload_id: int):
    """
    Get a single upload by ID.
    
    Path Parameters:
        - upload_id: The upload ID
        
    Returns:
        Upload object as JSON or 404 if not found
    """
    upload_repo = UploadRepository()
    upload = upload_repo.get_upload_by_id(upload_id)
    
    if upload is None:
        return error_response(f'Upload {upload_id} not found', status_code=404)
    
    return success_response(data=upload)
    upload_repo = UploadRepository()
    upload = upload_repo.get_upload_by_id(upload_id)
    
    if upload is None:
        return error_response(f'Upload {upload_id} not found', status_code=404)
    
    return success_response(data=upload)


@bp.route('/<int:upload_id>', methods=['DELETE'])
@handle_exceptions(log_prefix="delete_upload")
@handle_exceptions(log_prefix="delete_upload")
def delete_upload(upload_id: int):
    """
    Delete an upload and all associated data.
    
    Path Parameters:
        - upload_id: The upload ID to delete
        
    Returns:
        Success message or 404 if not found
    """
    upload_repo = UploadRepository()
    deleted = upload_repo.delete_upload(upload_id)
    
    if not deleted:
        return error_response(f'Upload {upload_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_upload_id': upload_id},
        message=f'Upload {upload_id} deleted successfully'
    )
    upload_repo = UploadRepository()
    deleted = upload_repo.delete_upload(upload_id)
    
    if not deleted:
        return error_response(f'Upload {upload_id} not found', status_code=404)
    
    return success_response(
        data={'deleted_upload_id': upload_id},
        message=f'Upload {upload_id} deleted successfully'
    )