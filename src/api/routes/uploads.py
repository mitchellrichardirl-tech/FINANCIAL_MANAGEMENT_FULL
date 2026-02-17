from flask import Blueprint, request
from datetime import datetime

from src.database.repositories.uploads import UploadRepository
from src.api.utils.response_helpers import success_response, error_response
from src.api.utils.route_helpers import handle_exceptions, require_json, handle_database_errors
from src.api.utils.validators import RequestValidator, require_at_least_one
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('uploads', __name__)
logger = ContextLogger(__name__)


# ==================== Helper Functions ====================

def validate_create_upload(data: dict) -> tuple[bool, dict, str]:
    """Validate upload creation data."""
    logger.debug(f"Validating creation data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    validator.validate_field('filename',
        validator.field('filename').required().strip_string())
    validator.validate_field('file_type',
        validator.field('file_type').required().strip_string())
    validator.validate_field('row_count',
        validator.field('row_count').optional().integer(min_val=0))
    validator.validate_field('column_count',
        validator.field('column_count').optional().integer(min_val=0))
    validator.validate_field('columns',
        validator.field('columns').optional())
    validator.validate_field('original_filename',
        validator.field('original_filename').optional().strip_string())

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    # Apply defaults for optional integer fields not provided
    validated = validator.validated
    validated.setdefault('row_count', 0)
    validated.setdefault('column_count', 0)

    return True, validated, None


def validate_update_upload(data: dict) -> tuple[bool, dict, str]:
    """Validate upload update data."""
    logger.debug(f"Validating update data with keys: {list(data.keys())}")

    updatable_fields = [
        'original_filename', 'filename', 'file_type',
        'row_count', 'column_count', 'columns'
    ]

    error = require_at_least_one(
        data,
        updatable_fields,
        'At least one updatable field is required'
    )
    if error:
        logger.warning(f"Validation failed: {error}")
        return False, {}, error

    validator = RequestValidator(data)

    validator.validate_field('filename',
        validator.field('filename').optional().strip_string())
    validator.validate_field('file_type',
        validator.field('file_type').optional().strip_string())
    validator.validate_field('original_filename',
        validator.field('original_filename').optional().strip_string())
    validator.validate_field('row_count',
        validator.field('row_count').optional().integer(min_val=0))
    validator.validate_field('column_count',
        validator.field('column_count').optional().integer(min_val=0))
    validator.validate_field('columns',
        validator.field('columns').optional())

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return False, {}, validator.first_error_message()

    return True, validator.validated, None


def parse_date_param(param_name: str) -> tuple[datetime | None, str | None]:
    """Parse an ISO 8601 date from query parameters.

    Returns:
        Tuple of (parsed_datetime, error_message).
        On success error_message is None; on failure datetime is None.
    """
    raw = request.args.get(param_name)
    if not raw:
        return None, None

    try:
        return datetime.fromisoformat(raw), None
    except ValueError:
        return None, f"Invalid {param_name} format. Use ISO 8601."


# ==================== Upload CRUD Routes ====================

@bp.route('', methods=['GET'])
@handle_exceptions(log_prefix="list_uploads")
@log_route(logger)
def list_uploads():
    """List all uploads with optional filtering and pagination."""
    repo = UploadRepository()

    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    file_type = request.args.get('file_type')
    original_filename = request.args.get('original_filename')
    filename = request.args.get('filename')

    start_date, err = parse_date_param('start_date')
    if err:
        return error_response(err, status_code=400)

    end_date, err = parse_date_param('end_date')
    if err:
        return error_response(err, status_code=400)

    uploads = repo.get_all_uploads(
        limit=limit,
        offset=offset,
        file_type=file_type,
        original_filename=original_filename,
        filename=filename,
        start_date=start_date,
        end_date=end_date
    )

    total = repo.count_uploads(
        file_type=file_type,
        start_date=start_date,
        end_date=end_date
    )

    logger.info(f"Retrieved {len(uploads)} uploads (total: {total})")
    return success_response(data=uploads)


@bp.route('/stats', methods=['GET'])
@handle_exceptions(log_prefix="get_upload_stats")
@log_route(logger)
def get_stats():
    """Get aggregate upload statistics."""
    repo = UploadRepository()
    stats = repo.get_upload_stats()

    logger.info("Retrieved upload stats")
    return success_response(data=stats)


@bp.route('/<int:upload_id>', methods=['GET'])
@handle_exceptions(log_prefix="get_upload")
@log_route(logger)
def get_upload(upload_id: int):
    """Get a single upload by ID, optionally including its data rows."""
    repo = UploadRepository()

    include_data = request.args.get('include_data', 'false').lower() == 'true'
    data_limit = request.args.get('data_limit', type=int)
    data_offset = request.args.get('data_offset', 0, type=int)

    if include_data:
        upload = repo.get_upload_with_data(
            upload_id,
            data_limit=data_limit,
            data_offset=data_offset
        )
    else:
        upload = repo.get_upload_by_id(upload_id)

    if upload is None:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    return success_response(data=upload)


@bp.route('', methods=['POST'])
@handle_database_errors()
@require_json
@log_route(logger)
def create_upload():
    """Create a new upload record."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_create_upload(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

    repo = UploadRepository()
    upload_id = repo.create_upload(**validated_data)
    upload = repo.get_upload_by_id(upload_id)

    logger.info(f"Created upload with id: {upload_id}")
    return success_response(
        data=upload,
        message='Upload created successfully',
        status_code=201
    )


@bp.route('/<int:upload_id>', methods=['PUT'])
@handle_database_errors()
@require_json
@log_route(logger)
def update_upload(upload_id: int):
    """Update an existing upload record."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    is_valid, validated_data, error_msg = validate_update_upload(data)
    if not is_valid:
        return error_response(error_msg, status_code=400)

    repo = UploadRepository()
    updated = repo.update_upload(upload_id=upload_id, **validated_data)

    if updated is None:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    logger.info(f"Updated upload {upload_id} fields: {list(validated_data.keys())}")
    return success_response(
        data=updated,
        message='Upload updated successfully'
    )


@bp.route('/<int:upload_id>', methods=['DELETE'])
@handle_database_errors()
@log_route(logger)
def delete_upload(upload_id: int):
    """Delete an upload and all associated data."""
    repo = UploadRepository()
    deleted = repo.delete_upload(upload_id)

    if not deleted:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    return success_response(
        data={'deleted_id': upload_id},
        message=f'Upload {upload_id} deleted successfully'
    )


# ==================== Upload Data Row Routes ====================

@bp.route('/<int:upload_id>/data', methods=['GET'])
@handle_exceptions(log_prefix="get_upload_data")
@log_route(logger)
def get_upload_data(upload_id: int):
    """Get data rows for a specific upload."""
    repo = UploadRepository()

    upload = repo.get_upload_by_id(upload_id)
    if upload is None:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', 0, type=int)
    start_row = request.args.get('start_row', type=int)
    end_row = request.args.get('end_row', type=int)

    rows = repo.get_upload_data(
        upload_id,
        limit=limit,
        offset=offset,
        start_row=start_row,
        end_row=end_row
    )

    total = repo.count_upload_data_rows(upload_id)

    logger.info(f"Retrieved {len(rows)} data rows for upload {upload_id} (total: {total})")
    return success_response(data={
        'rows': rows,
        'total': total,
        'upload_id': upload_id
    })


@bp.route('/<int:upload_id>/data/<int:row_index>', methods=['GET'])
@handle_exceptions(log_prefix="get_upload_data_row")
@log_route(logger)
def get_upload_data_row(upload_id: int, row_index: int):
    """Get a specific data row from an upload."""
    repo = UploadRepository()

    row = repo.get_upload_data_row(upload_id, row_index)
    if row is None:
        logger.warning(f"Row {row_index} not found in upload {upload_id}")
        return error_response(
            f'Row {row_index} not found in upload {upload_id}',
            status_code=404
        )

    return success_response(data=row)


@bp.route('/<int:upload_id>/data/<int:row_index>', methods=['PUT'])
@handle_database_errors()
@require_json
@log_route(logger)
def update_upload_data_row(upload_id: int, row_index: int):
    """Update a specific data row in an upload."""
    data = request.get_json()

    if not data:
        logger.warning("Empty request body")
        return error_response('Request body is required', status_code=400)

    if 'row_data' not in data:
        logger.warning("Missing row_data in request body")
        return error_response('row_data is required in request body', status_code=400)

    repo = UploadRepository()
    updated = repo.update_upload_data_row(upload_id, row_index, data['row_data'])

    if updated is None:
        logger.warning(f"Row {row_index} not found in upload {upload_id}")
        return error_response(
            f'Row {row_index} not found in upload {upload_id}',
            status_code=404
        )

    logger.info(f"Updated row {row_index} in upload {upload_id}")
    return success_response(
        data=updated,
        message=f'Row {row_index} updated successfully'
    )


@bp.route('/<int:upload_id>/data', methods=['DELETE'])
@handle_database_errors()
@log_route(logger)
def delete_upload_data(upload_id: int):
    """Delete all data rows for an upload (keeps the upload record)."""
    repo = UploadRepository()

    upload = repo.get_upload_by_id(upload_id)
    if upload is None:
        logger.warning(f"Upload {upload_id} not found")
        return error_response(f'Upload {upload_id} not found', status_code=404)

    deleted_count = repo.delete_upload_data(upload_id)

    logger.info(f"Deleted {deleted_count} rows from upload {upload_id}")
    return success_response(
        data={'upload_id': upload_id, 'deleted_count': deleted_count},
        message=f'Deleted {deleted_count} rows from upload {upload_id}'
    )