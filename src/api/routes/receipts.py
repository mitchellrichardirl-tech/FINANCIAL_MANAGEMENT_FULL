from flask import Blueprint, Response, request, jsonify, current_app as app, send_file
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
import tempfile
from pathlib import Path

from src.database.repositories.receipts import ReceiptRepository
from src.database.connection import DatabaseError

from src.models.receipt import Receipt

from src.receipts.receipt_extractor import ReceiptExtractor
from src.receipts.receipt_loader import ReceiptLoader

from src.api.utils.file_handling import FileHandler, TempFileManager
from src.api.utils.response_helpers import success_response, error_response
from src.api.utils.sse import SSEEventBuilder, ProgressInfo, create_sse_response, create_error_sse_response
from src.api.utils.route_helpers import handle_exceptions, require_json, handle_database_errors
from src.api.utils.validators import (
    RequestValidator, parse_date, parse_float, parse_int,
    validate_pagination, validate_date_range_filters,
    add_string_filters, require_at_least_one
)
from src.api.formatters.receipt_formatter import ReceiptFormatter
from src.api.services.receipt_processor import ReceiptStreamProcessor, receipt_worker, ProcessingResult
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('receipts', __name__)
logger = ContextLogger(__name__)

# Initialize services
receipt_repository = ReceiptRepository()
receipt_loader = ReceiptLoader()
receipt_extractor = ReceiptExtractor()


# =============================================================================
# Helper Functions
# =============================================================================

def process_receipt_images(file_path: str) -> Optional[Receipt]:
    """
    Load and process receipt image(s), returning the best result.

    For multi-page documents, returns the page with highest confidence.
    """
    logger.debug(f"Loading receipt images from: {file_path}")
    receipts = receipt_loader.process_files(file_path, yield_pages=True)

    if not receipts:
        logger.warning(f"No receipt images loaded from: {file_path}")
        return None

    if len(receipts) > 1:
        logger.debug(f"Multi-page document detected: {len(receipts)} pages")
        processed_receipts = [receipt_extractor.process_receipt(r) for r in receipts]
        best = max(processed_receipts, key=lambda r: r.confidence)
        logger.debug(
            f"Selected best page with confidence: {best.confidence} "
            f"from {len(processed_receipts)} pages"
        )
        return best
    else:
        processed = receipt_extractor.process_receipt(receipts[0])
        logger.debug(f"Single page processed with confidence: {processed.confidence}")
        return processed


def apply_form_overrides(receipt: Receipt, form) -> Tuple[Receipt, Optional[str]]:
    """
    Apply form data overrides to a receipt.

    Returns (receipt, error_message) - error_message is None if successful.
    """
    overridden_fields = []

    if form.get('vendor'):
        receipt.vendor = form['vendor']
        overridden_fields.append('vendor')

    if form.get('amount'):
        try:
            receipt.amount = float(form['amount'])
            overridden_fields.append('amount')
        except ValueError:
            logger.warning(f"Invalid amount format: {form['amount']}")
            return receipt, 'Invalid amount format'

    if form.get('date'):
        try:
            receipt.date = datetime.fromisoformat(form['date'])
            overridden_fields.append('date')
        except ValueError:
            logger.warning(f"Invalid date format: {form['date']}")
            return receipt, 'Invalid date format. Use YYYY-MM-DD'

    if overridden_fields:
        logger.debug(f"Applied form overrides: {overridden_fields}")

    return receipt, None


def validate_receipt_filters(args) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Parse and validate receipt filter parameters from request args.

    Returns (filters_dict, error_message) - error_message is None if valid.
    """
    logger.debug(f"Validating receipt filters: {list(args.keys())}")

    # Validate pagination
    is_valid, pagination, error = validate_pagination(args)
    if not is_valid:
        logger.warning(f"Pagination validation failed: {error}")
        return None, error

    # Validate date range
    is_valid, date_filters, error = validate_date_range_filters(args)
    if not is_valid:
        logger.warning(f"Date range validation failed: {error}")
        return None, error

    validator = RequestValidator(args)
    validator.validated.update(date_filters)

    # Vendor filter
    add_string_filters(validator.validated, args, ['vendor'])

    # Confidence filter
    validator.validate_field('min_confidence',
        validator.field('min_confidence').optional().transform(parse_int).in_range(0, 3))

    # Date range validation
    if validator.validated.get('start_date') and validator.validated.get('end_date'):
        if validator.validated['start_date'] > validator.validated['end_date']:
            logger.warning("start_date is after end_date")
            return None, 'start_date cannot be after end_date'

    if not validator.is_valid():
        logger.warning(f"Filter validation failed: {validator.first_error_message()}")
        return None, validator.first_error_message()

    return {**pagination, **validator.validated}, None


def validate_receipt_update(data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Validate and extract receipt update fields from request data.

    Returns (update_kwargs, error_message) - error_message is None if valid.
    """
    logger.debug(f"Validating update data with keys: {list(data.keys())}")

    validator = RequestValidator(data)

    # String fields
    add_string_filters(validator.validated, data, ['vendor', 'raw_text'])

    # Amount
    if 'amount' in data:
        if data['amount'] is not None:
            validator.validate_field('amount',
                validator.field('amount').transform(parse_float, 'Invalid amount format'))
        else:
            validator.validated['amount'] = None

    # Date
    if 'date' in data:
        if data['date'] is not None:
            validator.validate_field('date',
                validator.field('date').transform(parse_date, 'Invalid date format. Use YYYY-MM-DD'))
        else:
            validator.validated['date'] = None

    # Confidence
    if 'confidence' in data:
        if data['confidence'] is not None:
            validator.validate_field('confidence',
                validator.field('confidence').transform(parse_int).in_range(0, 3))
        else:
            validator.validated['confidence'] = None

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return None, validator.first_error_message()

    return validator.validated, None


def validate_confirm_receipt(data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """Validate receipt confirmation data."""
    logger.debug(f"Validating confirmation data with keys: {list(data.keys())}")

    # Check required fields
    error = require_at_least_one(data, ['original_filename', 'vendor'])
    if error:
        logger.warning(f"Validation failed: {error}")
        return None, error

    validator = RequestValidator(data)

    # Required string fields
    validator.validate_field('original_filename',
        validator.field('original_filename').required().strip_string())
    validator.validate_field('vendor',
        validator.field('vendor').required().strip_string())

    # Optional fields
    if 'amount' in data and data['amount'] is not None:
        validator.validate_field('amount',
            validator.field('amount').transform(parse_float, 'Invalid amount format'))

    if 'date' in data and data['date']:
        validator.validate_field('date',
            validator.field('date').transform(parse_date, 'Invalid date format. Use YYYY-MM-DD'))

    # Confidence with default
    confidence = data.get('confidence', 0)
    validator.validate_field('confidence',
        validator.field('confidence').transform(parse_int).in_range(0, 3))
    if 'confidence' not in validator.validated:
        validator.validated['confidence'] = 0

    # Other optional fields
    for field in ['id', 'file_path', 'stored_filename', 'raw_text']:
        if field in data:
            validator.validated[field] = data[field]

    if not validator.is_valid():
        logger.warning(f"Validation failed: {validator.first_error_message()}")
        return None, validator.first_error_message()

    return validator.validated, None


# =============================================================================
# Streaming Upload Endpoint
# =============================================================================

@bp.route('/receipts/upload-stream', methods=['POST'])
@log_route(logger)
def upload_receipts_stream():
    """Upload and process multiple receipt images with streaming responses."""
    temp_files = []

    try:
        file_handler = FileHandler.from_app_config(prefix="receipt")
        files = request.files.getlist('files')

        # Validate we have files
        if not files or (len(files) == 1 and files[0].filename == ''):
            logger.warning("No files provided in stream upload")
            return create_error_sse_response("No files provided")

        logger.info(f"Received {len(files)} files for stream processing")

        # Save files to temp locations - cleanup happens in generator
        for file in files:
            validation = file_handler.validate_file(file)
            if not validation.is_valid:
                logger.warning(f"Skipping invalid file: {validation.error}")
                continue

            # Create temp file
            fd, temp_path = tempfile.mkstemp(suffix=validation.extension)
            try:
                with os.fdopen(fd, 'wb') as f:
                    file.save(f)
                temp_files.append((validation.secured_filename, temp_path))
                logger.debug(f"Saved {validation.secured_filename} to temp: {temp_path}")
            except Exception as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                logger.error(f"Failed to save {file.filename}: {e}")

        if not temp_files:
            logger.warning("No valid files after validation")
            return create_error_sse_response("No valid files to process")

        logger.info(f"Processing {len(temp_files)} valid files via stream")

        form_data = request.form.to_dict() if request.form else None

        processor = ReceiptStreamProcessor(
            upload_folder=file_handler.ensure_upload_folder(),
            allowed_extensions=file_handler.allowed_extensions
        )

        def cleanup_and_stream():
            """Generator wrapper that ensures cleanup after streaming completes."""
            try:
                yield from processor.process_files(temp_files, form_data)
            finally:
                for _, temp_path in temp_files:
                    if os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                            logger.debug(f"Cleaned up temp file: {temp_path}")
                        except Exception as e:
                            logger.error(f"Failed to cleanup {temp_path}: {e}")

        return create_sse_response(
            cleanup_and_stream(),
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logger.error(f"Stream upload failed: {e}", exc_info=True)
        # Cleanup on error before streaming starts
        for _, temp_path in temp_files:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
        return create_error_sse_response("Internal server error", str(e))


# =============================================================================
# Single Upload Endpoint
# =============================================================================

@bp.route('/receipts/upload', methods=['POST'])
@handle_exceptions(log_prefix="upload_receipt")
@log_route(logger)
def upload_receipt():
    """
    Upload a receipt image file, process it, and save to database.

    Expected: multipart/form-data with 'file' field
    Optional form fields:
        - vendor: Override extracted vendor
        - amount: Override extracted amount
        - date: Override extracted date (YYYY-MM-DD)

    Returns: receipt_id and extracted data
    """
    file_handler = FileHandler.from_app_config(prefix="receipt")
    stored_path = None

    # Validate file presence
    if 'file' not in request.files:
        logger.warning("No file field in request")
        return error_response('No file provided', status_code=400)

    file = request.files['file']
    validation = file_handler.validate_file(file)

    if not validation.is_valid:
        logger.warning(f"File validation failed: {validation.error}")
        return error_response(validation.error, status_code=400)

    with TempFileManager() as temp_manager:
        # Save to temp location for processing
        temp_path = temp_manager.save_file_to_temp(file, suffix=validation.extension)

        logger.info(f"Processing uploaded file: {validation.secured_filename}")

        # Load and process the image
        receipt = process_receipt_images(str(temp_path))

        if receipt is None:
            logger.warning(f"Failed to process image: {validation.secured_filename}")
            return error_response('Unable to process the uploaded image', status_code=422)

        # Apply any manual overrides from form data
        receipt, override_error = apply_form_overrides(receipt, request.form)
        if override_error:
            return error_response(override_error, status_code=400)

        # Move file to permanent storage
        stored_filename = file_handler.generate_stored_filename(validation.secured_filename)
        stored_path = file_handler.move_to_permanent(temp_path, stored_filename)
        logger.debug(f"Moved to permanent storage: {stored_path}")

        # Update receipt with file info
        receipt.original_filename = validation.secured_filename
        receipt.stored_filename = stored_filename
        receipt.file_path = stored_path

        # Save to database
        receipt_id = receipt_repository.save(receipt)

        if receipt_id is None:
            file_handler.delete_file(stored_path)
            logger.error(f"Database save failed, cleaned up file: {stored_path}")
            return error_response('Failed to save receipt', status_code=500)

        # Fetch the saved receipt for response
        saved_receipt = receipt_repository.get_by_id(receipt_id)

        logger.info(
            f"Uploaded receipt {receipt_id}: {validation.secured_filename} "
            f"| confidence={receipt.confidence}"
        )

        return success_response(
            {
                'receipt': ReceiptFormatter.summary(saved_receipt),
                'message': 'Receipt uploaded and processed successfully'
            },
            status_code=201
        )


# =============================================================================
# CRUD Endpoints
# =============================================================================

@bp.route('/receipts', methods=['GET'])
@handle_exceptions(log_prefix="get_receipts")
@log_route(logger)
def get_receipts():
    """
    Get list of receipts with optional filters and pagination.

    Query params:
        - vendor: Filter by vendor name (partial match)
        - min_confidence: Minimum confidence score (0-3)
        - limit: Max results (default: 50, max: 500)
        - offset: Pagination offset (default: 0)
        - start_date: Filter from date (YYYY-MM-DD)
        - end_date: Filter until date (YYYY-MM-DD)

    Returns: List of receipts with pagination info
    """
    # Validate and parse filters
    filters, error = validate_receipt_filters(request.args)
    if error:
        return error_response(error, status_code=400)

    # Extract pagination from filters
    limit = filters.pop('limit')
    offset = filters.pop('offset')

    active_filters = {k: v for k, v in filters.items() if v is not None}
    if active_filters:
        logger.debug(f"Active filters: {active_filters}")

    # Get receipts
    receipts = receipt_repository.get_all(
        limit=limit,
        offset=offset,
        **filters
    )

    # Format response
    formatted_receipts = ReceiptFormatter.summary_list(receipts)

    response = {
        'receipts': formatted_receipts,
        'pagination': {
            'limit': limit,
            'offset': offset,
            'count': len(formatted_receipts),
            'has_more': len(formatted_receipts) == limit
        },
        'filters': {
            'vendor': filters.get('vendor'),
            'min_confidence': filters.get('min_confidence'),
            'start_date': request.args.get('start_date'),
            'end_date': request.args.get('end_date')
        }
    }

    logger.info(
        f"Retrieved {len(formatted_receipts)} receipts "
        f"(offset={offset}, limit={limit})"
    )
    return jsonify(response), 200


@bp.route('/receipts/<int:receipt_id>', methods=['GET'])
@handle_exceptions(log_prefix="get_receipt")
@log_route(logger)
def get_receipt(receipt_id: int):
    """Get a specific receipt by ID."""
    receipt = receipt_repository.get_by_id(receipt_id)

    if receipt is None:
        logger.warning(f"Receipt {receipt_id} not found")
        return error_response(f'Receipt {receipt_id} not found', status_code=404)

    return success_response({
        'receipt': ReceiptFormatter.detail(receipt)
    })


@bp.route('/receipts/<int:receipt_id>', methods=['PUT'])
@handle_exceptions(log_prefix="update_receipt")
@require_json
@log_route(logger)
def update_receipt(receipt_id: int):
    """
    Update receipt attributes.

    Expected JSON:
        - vendor: New vendor name
        - amount: New amount
        - date: New date (YYYY-MM-DD)
        - confidence: New confidence score (0-3)

    Returns: Updated receipt
    """
    # Check if receipt exists
    existing = receipt_repository.get_by_id(receipt_id)
    if existing is None:
        logger.warning(f"Receipt {receipt_id} not found")
        return error_response(f'Receipt {receipt_id} not found', status_code=404)

    data = request.get_json()

    # Validate update fields
    update_kwargs, error = validate_receipt_update(data)
    if error:
        return error_response(error, status_code=400)

    if not update_kwargs:
        logger.warning("No valid fields to update")
        return error_response('No valid fields to update', status_code=400)

    # Perform update
    updated_receipt = receipt_repository.update(receipt_id, **update_kwargs)

    if updated_receipt is None:
        logger.warning(f"Receipt {receipt_id} not found during update")
        return error_response(f'Receipt {receipt_id} not found', status_code=404)

    logger.info(f"Updated receipt {receipt_id}: {list(update_kwargs.keys())}")

    return success_response({
        'receipt': ReceiptFormatter.summary(updated_receipt),
        'message': 'Receipt updated successfully'
    })


@bp.route('/receipts/<int:receipt_id>', methods=['DELETE'])
@handle_exceptions(log_prefix="delete_receipt")
@log_route(logger)
def delete_receipt(receipt_id: int):
    """Delete a specific receipt and its associated image file."""
    file_handler = FileHandler.from_app_config()

    # Get receipt to find file path
    receipt = receipt_repository.get_by_id(receipt_id)

    if receipt is None:
        logger.warning(f"Receipt {receipt_id} not found")
        return error_response(f'Receipt {receipt_id} not found', status_code=404)

    # Delete from database
    deleted = receipt_repository.delete(receipt_id)

    if not deleted:
        logger.error(f"Database deletion failed for receipt {receipt_id}")
        return error_response(f'Failed to delete receipt {receipt_id}', status_code=500)

    # Delete associated file
    file_path = receipt.get('file_path')
    if file_path:
        if file_handler.delete_file(file_path):
            logger.debug(f"Deleted receipt file: {file_path}")
        else:
            logger.warning(f"Could not delete receipt file: {file_path}")
    else:
        logger.debug(f"No file associated with receipt {receipt_id}")

    return success_response({
        'message': f'Receipt {receipt_id} deleted successfully',
        'deleted_id': receipt_id
    })


# =============================================================================
# Image Endpoint
# =============================================================================

@bp.route('/receipts/<int:receipt_id>/image', methods=['GET'])
@handle_exceptions(log_prefix="get_receipt_image")
@log_route(logger)
def get_receipt_image(receipt_id: int):
    """Get the image file for a specific receipt."""
    file_handler = FileHandler.from_app_config()

    receipt = receipt_repository.get_by_id(receipt_id)

    if receipt is None:
        logger.warning(f"Receipt {receipt_id} not found")
        return error_response(f'Receipt {receipt_id} not found', status_code=404)

    file_path = receipt.get('file_path')

    if not file_path:
        logger.warning(f"No image file associated with receipt {receipt_id}")
        return error_response(
            f'No image file associated with receipt {receipt_id}',
            status_code=404
        )

    path = Path(file_path)

    if not path.exists():
        logger.error(f"Image file missing from disk: {file_path}")
        return error_response(
            f'Image file not found for receipt {receipt_id}',
            status_code=404
        )

    return send_file(
        path,
        mimetype=file_handler.get_mime_type(path),
        as_attachment=False,
        download_name=receipt.get('original_filename', path.name)
    )


# =============================================================================
# Processing Endpoints
# =============================================================================

@bp.route('/receipts/<int:receipt_id>/reprocess', methods=['POST'])
@handle_exceptions(log_prefix="reprocess_receipt")
@log_route(logger)
def reprocess_receipt(receipt_id: int):
    """
    Rerun OCR processing on an existing receipt.

    Optional JSON body:
        - keep_overrides: If true, preserve manual vendor/amount/date edits (default: false)

    Returns: Updated receipt data
    """
    # Get existing receipt
    receipt = receipt_repository.get_by_id(receipt_id)

    if receipt is None:
        logger.warning(f"Receipt {receipt_id} not found")
        return error_response(f'Receipt {receipt_id} not found', status_code=404)

    file_path = receipt.get('file_path')

    if not file_path:
        logger.warning(f"No image file associated with receipt {receipt_id}")
        return error_response(
            f'No image file associated with receipt {receipt_id}',
            status_code=400
        )

    path = Path(file_path)

    if not path.exists():
        logger.error(f"Image file missing from disk: {file_path}")
        return error_response(
            f'Image file not found for receipt {receipt_id}',
            status_code=404
        )

    # Check for options
    data = request.get_json(silent=True) or {}
    keep_overrides = data.get('keep_overrides', False)

    # Store original values if keeping overrides
    original_vendor = receipt.get('vendor') if keep_overrides else None
    original_amount = receipt.get('amount') if keep_overrides else None
    original_date = receipt.get('date') if keep_overrides else None

    logger.info(f"Reprocessing receipt {receipt_id} | keep_overrides={keep_overrides}")

    # Reload and reprocess the image
    processed = process_receipt_images(str(path))

    if processed is None:
        logger.warning(f"Reprocessing failed for receipt {receipt_id}")
        return error_response('Unable to reprocess the image', status_code=422)

    # Build update data
    update_kwargs = {
        'confidence': processed.confidence,
        'raw_text': processed.extracted_text,
    }

    # Apply new values or keep overrides
    if keep_overrides:
        preserved = []
        if original_vendor is not None:
            preserved.append('vendor')
        else:
            update_kwargs['vendor'] = processed.vendor
        if original_amount is not None:
            preserved.append('amount')
        else:
            update_kwargs['amount'] = processed.amount
        if original_date is not None:
            preserved.append('date')
        else:
            update_kwargs['date'] = processed.date
        if preserved:
            logger.debug(f"Preserved override fields: {preserved}")
    else:
        update_kwargs['vendor'] = processed.vendor
        update_kwargs['amount'] = processed.amount
        update_kwargs['date'] = processed.date

    # Update in database
    updated_receipt = receipt_repository.update(receipt_id, **update_kwargs)

    logger.info(
        f"Reprocessed receipt {receipt_id} "
        f"| new_confidence={processed.confidence}"
    )

    return success_response({
        'receipt': ReceiptFormatter.summary(updated_receipt),
        'message': 'Receipt reprocessed successfully',
        'reprocessing': {
            'kept_overrides': keep_overrides,
            'new_confidence': processed.confidence,
            'extracted_vendor': processed.vendor,
            'extracted_amount': processed.amount,
            'extracted_date': processed.date.isoformat() if processed.date else None
        }
    })


@bp.route('/receipts/process', methods=['POST'])
@handle_exceptions(log_prefix="process_receipt")
@log_route(logger)
def process_receipt():
    """
    Run OCR on receipt image without saving to database.

    Expected: multipart/form-data with 'file' field

    Returns: Extracted data (vendor, amount, date, confidence, etc.)
    """
    file_handler = FileHandler.from_app_config(prefix="receipt")

    if 'file' not in request.files:
        logger.warning("No file field in request")
        return error_response('No file provided', status_code=400)

    file = request.files['file']
    validation = file_handler.validate_file(file)

    if not validation.is_valid:
        logger.warning(f"File validation failed: {validation.error}")
        return error_response(validation.error, status_code=400)

    with TempFileManager() as temp_manager:
        temp_path = temp_manager.save_file_to_temp(file, suffix=validation.extension)

        logger.info(f"Processing image (no save): {validation.secured_filename}")

        # Load and process
        receipts = receipt_loader.process_files(str(temp_path), yield_pages=True)

        if not receipts:
            logger.warning(f"Failed to process image: {validation.secured_filename}")
            return error_response('Unable to process the uploaded image', status_code=422)

        # Process each page
        results = []
        for receipt in receipts:
            processed = receipt_extractor.process_receipt(receipt)
            results.append(ReceiptFormatter.extracted_data(processed))

        logger.debug(f"Processed {len(results)} pages from {validation.secured_filename}")

        # Build response
        if len(results) == 1:
            response = {
                'success': True,
                'original_filename': validation.secured_filename,
                'extracted_data': results[0],
                'page_count': 1
            }
        else:
            best_idx = max(range(len(results)), key=lambda i: results[i].get('confidence') or 0)
            logger.debug(f"Multi-page: selected page {best_idx} as best result")
            response = {
                'success': True,
                'original_filename': validation.secured_filename,
                'extracted_data': results[best_idx],
                'all_pages': results,
                'page_count': len(results),
                'best_page_index': best_idx
            }

        logger.info(
            f"Processed {validation.secured_filename}: "
            f"vendor={response['extracted_data'].get('vendor')}, "
            f"amount={response['extracted_data'].get('amount')}"
        )

        return jsonify(response), 200


# =============================================================================
# Cancel/Confirm Endpoints
# =============================================================================

@bp.route('/receipts/<int:receipt_id>/cancel', methods=['POST'])
@handle_exceptions(log_prefix="cancel_receipt")
@log_route(logger)
def cancel_receipt(receipt_id: int):
    """
    Cancel receipt upload and delete temporary file.

    This endpoint is used when a user abandons the upload process after
    the preview/processing step but before confirmation.

    Returns: Success message
    """
    file_handler = FileHandler.from_app_config()

    receipt = receipt_repository.delete(receipt_id)

    if not receipt:
        logger.warning(f"No receipt found to cancel: {receipt_id}")
        return error_response(
            message=f'No receipt found with ID {receipt_id}',
            status_code=400
        )

    receipt_deleted = True
    file_deleted = False
    stored_filename = receipt.get('stored_filename')
    file_deletion_message = None

    # Clean up stored file (if upload was partially completed)
    if stored_filename:
        # Security: prevent directory traversal
        if not file_handler.is_safe_filename(stored_filename):
            file_deletion_message = (
                f'For receipt {receipt_id} invalid stored_filename {stored_filename}. '
                f'File not deleted'
            )
            logger.warning(f"Unsafe stored_filename for receipt {receipt_id}: {stored_filename}")
        else:
            upload_folder = file_handler.ensure_upload_folder()
            stored_path = upload_folder / stored_filename

            if file_handler.delete_file(stored_path):
                file_deletion_message = f'For receipt {receipt_id} deleted stored file: {stored_path}'
                file_deleted = True
                logger.debug(f"Deleted stored file: {stored_path}")
            else:
                file_deletion_message = f"For receipt {receipt_id} failed to find path {stored_path}"
                logger.warning(f"Stored file not found: {stored_path}")
    else:
        file_deletion_message = f'No stored file associated with receipt {receipt_id}'
        logger.debug(f"No stored file to clean up for receipt {receipt_id}")

    logger.info(
        f"Cancelled receipt {receipt_id} "
        f"| record_deleted={receipt_deleted} | file_deleted={file_deleted}"
    )

    return success_response(
        data={
            'deleted_receipt': receipt,
            'receipt_deleted': receipt_deleted,
            'file_deleted': file_deleted,
        },
        message=file_deletion_message
    )


@bp.route('/receipts/confirm', methods=['POST'])
@handle_exceptions(log_prefix="confirm_receipt")
@require_json
@log_route(logger)
def confirm_receipt():
    """
    Save receipt data to database (typically after processing/preview).

    Expected JSON:
        - id: Receipt ID to confirm
        - original_filename: Original file name
        - vendor: Vendor name
        - amount: Receipt amount
        - date: Receipt date (YYYY-MM-DD)
        - confidence: Confidence score (0-3)
        - selected_method: OCR method used
        - raw_text: (optional) Extracted text

    Returns: Saved receipt with receipt_id
    """
    file_handler = FileHandler.from_app_config()
    data = request.get_json()

    # Validate required fields
    validated_data, error = validate_confirm_receipt(data)
    if error:
        return error_response(error, status_code=400)

    receipt_id = validated_data.get('id')

    # Get file path from existing receipt
    file_path = validated_data.get('file_path')
    if not file_path:
        existing_receipt = receipt_repository.get_by_id(receipt_id)
        if not existing_receipt:
            logger.warning(f"Receipt {receipt_id} not found for confirmation")
            return error_response(f'Receipt {receipt_id} not found', status_code=400)
        file_path = existing_receipt.get('file_path')

    if not file_path or not Path(file_path).exists():
        logger.warning(f"File not found at: {file_path}")
        return error_response(f'File not found at {file_path}', status_code=400)

    # Generate stored filename if not provided
    stored_filename = validated_data.get('stored_filename')
    if not stored_filename:
        stored_filename = file_handler.generate_stored_filename(validated_data['original_filename'])
        logger.debug(f"Generated stored filename: {stored_filename}")

    # Update in database
    saved_receipt = receipt_repository.update(
        id=receipt_id,
        vendor=validated_data['vendor'],
        amount=validated_data.get('amount'),
        date=validated_data.get('date'),
        confidence=validated_data.get('confidence', 0),
        raw_text=validated_data.get('raw_text')
    )

    if saved_receipt is None:
        logger.error(f"Failed to confirm receipt {receipt_id}")
        return error_response('Failed to save receipt', status_code=500)

    logger.info(
        f"Confirmed receipt {receipt_id}: {validated_data['original_filename']} "
        f"| vendor={validated_data['vendor']}"
    )

    return success_response(
        {
            'receipt': ReceiptFormatter.summary(saved_receipt),
            'message': 'Receipt saved successfully'
        },
        status_code=201
    )


# =============================================================================
# Statistics Endpoint
# =============================================================================

@bp.route('/receipts/stats', methods=['GET'])
@handle_exceptions(log_prefix="get_receipt_stats")
@log_route(logger)
def get_receipt_stats():
    """Get receipt statistics."""
    stats = receipt_repository.get_stats()

    logger.info(f"Retrieved stats: {stats.get('total_receipts', 0)} total receipts")

    return success_response({
        'statistics': {
            'total_receipts': stats.get('total_receipts', 0),
            'total_amount': stats.get('total_amount'),
            'average_amount': stats.get('avg_amount'),
            'average_confidence': stats.get('avg_confidence'),
            'unique_vendors': stats.get('unique_vendors', 0),
            'high_confidence_count': stats.get('high_confidence_count', 0),
            'date_range': {
                'earliest': stats.get('earliest_date'),
                'latest': stats.get('latest_date')
            },
            'top_vendors': stats.get('top_vendors', [])
        }
    })