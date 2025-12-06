from flask import Blueprint, request, jsonify, current_app as app, send_file
from datetime import datetime
from werkzeug.utils import secure_filename
from typing import Dict, Union
import logging
import os
import tempfile
import uuid
import shutil
from pathlib import Path

from src.database.repositories.receipts import ReceiptRepository
from src.database.connection import DatabaseError

from src.models.receipt import Receipt

from src.receipts.receipt_extractor import ReceiptExtractor
from src.receipts.receipt_loader import ReceiptLoader

from src.api.utils.file_handling import save_upload_file, cleanup_temp_file
from src.api.utils.response_helpers import success_response, error_response

bp = Blueprint('receipts', __name__)

logger = logging.getLogger(__name__)

# Initialize services
receipt_repository = ReceiptRepository()
receipt_loader = ReceiptLoader()
receipt_extractor = ReceiptExtractor()


# =============================================================================
# Helper Functions
# =============================================================================

def allowed_file(filename: Union[Path, str, None]) -> bool:
    """Check if file extension is allowed."""
    if filename is None:
        return False
    if isinstance(filename, Path):
        filename = filename.name
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_upload_folder() -> Path:
    """Get the upload folder path, creating it if necessary."""
    upload_folder = Path(app.config.get('UPLOAD_FOLDER', 'data/uploads/receipts'))
    upload_folder.mkdir(parents=True, exist_ok=True)
    return upload_folder


def generate_stored_filename(original_filename: str) -> str:
    """Generate a unique stored filename."""
    ext = Path(original_filename).suffix.lower()
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"receipt_{timestamp}_{unique_id}{ext}"


def format_receipt_summary(receipt: Dict) -> Dict:
    """Format receipt for list views (minimal data)."""
    return {
        'id': receipt['id'],
        'original_filename': receipt['original_filename'],
        'vendor': receipt['vendor'],
        'amount': receipt['amount'],
        'date': receipt['date'].isoformat() if isinstance(receipt.get('date'), datetime) else receipt.get('date'),
        'confidence': receipt['confidence'],
        'created_at': receipt['created_at'],
    }


def format_receipt_detail(receipt: Dict) -> Dict:
    """Format receipt for detail views (full data)."""
    return {
        'id': receipt['id'],
        'original_filename': receipt['original_filename'],
        'stored_filename': receipt['stored_filename'],
        'vendor': receipt['vendor'],
        'amount': receipt['amount'],
        'date': receipt['date'].isoformat() if isinstance(receipt.get('date'), datetime) else receipt.get('date'),
        'confidence': receipt['confidence'],
        'selected_method': receipt['selected_method'],
        'raw_text': receipt.get('raw_text'),  # Include in detail view
        'metadata': receipt.get('metadata', {}),  # Include in detail view
        'created_at': receipt['created_at'],
        'updated_at': receipt['updated_at'],
    }


# =============================================================================
# Endpoints
# =============================================================================

# 1. Upload receipt image
@bp.route('/receipts/upload', methods=['POST'])
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
    temp_path = None
    stored_path = None
    
    try:
        # Validate file presence
        if 'file' not in request.files:
            return error_response('No file provided', status_code=400)
        
        file = request.files['file']
        
        if file.filename == '':
            return error_response('No file selected', status_code=400)
        
        if not allowed_file(file.filename):
            allowed = ', '.join(app.config['ALLOWED_EXTENSIONS'])
            return error_response(
                f'Invalid file type. Allowed types: {allowed}',
                status_code=400
            )
        
        # Secure and generate filenames
        original_filename = secure_filename(file.filename)
        stored_filename = generate_stored_filename(original_filename)
        
        # Save to temp location first for processing
        file_extension = Path(original_filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)
        
        logger.info(f"Processing uploaded receipt: {original_filename}")
        
        # Load and process the image
        receipts = receipt_loader.process_files(temp_path, yield_pages=True)
        
        if not receipts:
            return error_response(
                'Unable to process the uploaded image',
                status_code=422
            )
        
        # Process first receipt (or best from multi-page)
        receipt = receipts[0]
        if len(receipts) > 1:
            # For multi-page, find best confidence
            processed_receipts = [receipt_extractor.process_receipt(r) for r in receipts]
            receipt = max(processed_receipts, key=lambda r: r.confidence)
        else:
            receipt = receipt_extractor.process_receipt(receipt)
        
        # Apply any manual overrides from form data
        if request.form.get('vendor'):
            receipt.vendor = request.form['vendor']
        
        if request.form.get('amount'):
            try:
                receipt.amount = float(request.form['amount'])
            except ValueError:
                return error_response('Invalid amount format', status_code=400)
        
        if request.form.get('date'):
            try:
                receipt.date = datetime.fromisoformat(request.form['date'])
            except ValueError:
                return error_response(
                    'Invalid date format. Use YYYY-MM-DD',
                    status_code=400
                )
        
        # Move file to permanent storage
        upload_folder = get_upload_folder()
        stored_path = upload_folder / stored_filename
        shutil.copy2(temp_path, stored_path)
        
        # Update receipt with file info
        receipt.original_filename = original_filename
        receipt.stored_filename = stored_filename
        receipt.file_path = stored_path
        
        # Save to database
        receipt_id = receipt_repository.save(receipt)
        
        if receipt_id is None:
            # Cleanup stored file if save failed
            if stored_path and stored_path.exists():
                stored_path.unlink()
            return error_response('Failed to save receipt', status_code=500)
        
        # Fetch the saved receipt for response
        saved_receipt = receipt_repository.get_by_id(receipt_id)
        
        logger.info(f"Successfully uploaded and saved receipt {receipt_id}: {original_filename}")
        
        return success_response(
            {
                'receipt': format_receipt_summary(saved_receipt),
                'message': 'Receipt uploaded and processed successfully'
            },
            status_code=201
        )
        
    except DatabaseError as e:
        logger.error(f"Database error in upload_receipt: {e}")
        # Cleanup stored file on error
        if stored_path and Path(stored_path).exists():
            Path(stored_path).unlink()
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in upload_receipt: {e}", exc_info=True)
        # Cleanup stored file on error
        if stored_path and Path(stored_path).exists():
            Path(stored_path).unlink()
        return error_response('Internal server error', status_code=500)
    
    finally:
        cleanup_temp_file(temp_path)


# 2. Get list of receipts with optional filters
@bp.route('/receipts', methods=['GET'])
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
    try:
        # Parse query parameters
        vendor = request.args.get('vendor', type=str)
        min_confidence = request.args.get('min_confidence', type=int)
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        start_date_str = request.args.get('start_date', type=str)
        end_date_str = request.args.get('end_date', type=str)
        
        # Validate parameters
        if limit < 1:
            return error_response('Limit must be at least 1', status_code=400)
        if limit > 500:
            return error_response('Limit cannot exceed 500', status_code=400)
        if offset < 0:
            return error_response('Offset must be non-negative', status_code=400)
        if min_confidence is not None and (min_confidence < 0 or min_confidence > 3):
            return error_response('Confidence must be between 0 and 3', status_code=400)
        
        # Parse dates
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                return error_response('Invalid start_date format. Use YYYY-MM-DD', status_code=400)
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                return error_response('Invalid end_date format. Use YYYY-MM-DD', status_code=400)
        
        if start_date and end_date and start_date > end_date:
            return error_response('start_date cannot be after end_date', status_code=400)
        
        # Get receipts
        receipts = receipt_repository.get_all(
            limit=limit,
            offset=offset,
            vendor=vendor,
            min_confidence=min_confidence,
            start_date=start_date,
            end_date=end_date
        )
        
        # Format response
        formatted_receipts = [format_receipt_summary(r) for r in receipts]
        
        response = {
            'receipts': formatted_receipts,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'count': len(formatted_receipts),
                'has_more': len(formatted_receipts) == limit
            },
            'filters': {
                'vendor': vendor,
                'min_confidence': min_confidence,
                'start_date': start_date_str,
                'end_date': end_date_str
            }
        }
        
        logger.info(f"Retrieved {len(formatted_receipts)} receipts")
        return jsonify(response), 200
        
    except DatabaseError as e:
        logger.error(f"Database error in get_receipts: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_receipts: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)


# 3. Get specific receipt
@bp.route('/receipts/<int:receipt_id>', methods=['GET'])
def get_receipt(receipt_id: int):
    """
    Get a specific receipt by ID.
    
    Returns: Receipt details
    """
    try:
        receipt = receipt_repository.get_by_id(receipt_id)
        
        if receipt is None:
            return error_response(
                f'Receipt {receipt_id} not found',
                status_code=404
            )
        
        return success_response({
            'receipt': format_receipt_detail(receipt)
        })
        
    except DatabaseError as e:
        logger.error(f"Database error in get_receipt: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_receipt: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)


# 4. Update specific receipt
@bp.route('/receipts/<int:receipt_id>', methods=['PUT'])
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
    try:
        # Check if receipt exists
        existing = receipt_repository.get_by_id(receipt_id)
        if existing is None:
            return error_response(
                f'Receipt {receipt_id} not found',
                status_code=404
            )
        
        # Parse request data
        data = request.get_json(silent=True)
        
        if data is None:
            return error_response('Request body must be JSON', status_code=400)
        
        # Build update kwargs
        update_kwargs = {}
        
        if 'vendor' in data:
            update_kwargs['vendor'] = data['vendor']
        
        if 'amount' in data:
            try:
                update_kwargs['amount'] = float(data['amount']) if data['amount'] is not None else None
            except (ValueError, TypeError):
                return error_response('Invalid amount format', status_code=400)
        
        if 'date' in data:
            if data['date'] is None:
                update_kwargs['date'] = None
            else:
                try:
                    update_kwargs['date'] = datetime.fromisoformat(data['date'])
                except ValueError:
                    return error_response('Invalid date format. Use YYYY-MM-DD', status_code=400)
        
        if 'confidence' in data:
            confidence = data['confidence']
            if confidence is not None:
                if not isinstance(confidence, int) or confidence < 0 or confidence > 3:
                    return error_response('Confidence must be an integer between 0 and 3', status_code=400)
            update_kwargs['confidence'] = confidence
        
        if 'raw_text' in data:
            update_kwargs['raw_text'] = data['raw_text']
        
        # Perform update
        if not update_kwargs:
            return error_response('No valid fields to update', status_code=400)
        
        updated_receipt = receipt_repository.update(receipt_id, **update_kwargs)
        
        if updated_receipt is None:
            return error_response(
                f'Receipt {receipt_id} not found',
                status_code=404
            )
        
        logger.info(f"Updated receipt {receipt_id}: {list(update_kwargs.keys())}")
        
        return success_response({
            'receipt': format_receipt_summary(updated_receipt),
            'message': 'Receipt updated successfully'
        })
        
    except DatabaseError as e:
        logger.error(f"Database error in update_receipt: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in update_receipt: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)


# 5. Delete specific receipt
@bp.route('/receipts/<int:receipt_id>', methods=['DELETE'])
def delete_receipt(receipt_id: int):
    """
    Delete a specific receipt and its associated image file.
    
    Returns: Success status
    """
    try:
        # Get receipt to find file path
        receipt = receipt_repository.get_by_id(receipt_id)
        
        if receipt is None:
            return error_response(
                f'Receipt {receipt_id} not found',
                status_code=404
            )
        
        # Delete from database
        deleted = receipt_repository.delete(receipt_id)
        
        if not deleted:
            return error_response(
                f'Failed to delete receipt {receipt_id}',
                status_code=500
            )
        
        # Delete associated file
        file_path = receipt.get('file_path')
        if file_path:
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.info(f"Deleted receipt file: {file_path}")
            except Exception as e:
                # Log but don't fail - the database record is already deleted
                logger.warning(f"Failed to delete receipt file {file_path}: {e}")
        
        logger.info(f"Deleted receipt {receipt_id}")
        
        return success_response({
            'message': f'Receipt {receipt_id} deleted successfully',
            'deleted_id': receipt_id
        })
        
    except DatabaseError as e:
        logger.error(f"Database error in delete_receipt: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in delete_receipt: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)


# 6. Get receipt image file
@bp.route('/receipts/<int:receipt_id>/image', methods=['GET'])
def get_receipt_image(receipt_id: int):
    """
    Get the image file for a specific receipt.
    
    Returns: Image file
    """
    try:
        receipt = receipt_repository.get_by_id(receipt_id)
        
        if receipt is None:
            return error_response(
                f'Receipt {receipt_id} not found',
                status_code=404
            )
        
        file_path = receipt.get('file_path')
        
        if not file_path:
            return error_response(
                f'No image file associated with receipt {receipt_id}',
                status_code=404
            )
        
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Receipt image file not found: {file_path}")
            return error_response(
                f'Image file not found for receipt {receipt_id}',
                status_code=404
            )
        
        # Determine MIME type
        extension = path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
        }
        mimetype = mime_types.get(extension, 'application/octet-stream')
        
        return send_file(
            path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=receipt.get('original_filename', path.name)
        )
        
    except DatabaseError as e:
        logger.error(f"Database error in get_receipt_image: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_receipt_image: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)


# 7. Reprocess receipt (rerun OCR)
@bp.route('/receipts/<int:receipt_id>/reprocess', methods=['POST'])
def reprocess_receipt(receipt_id: int):
    """
    Rerun OCR processing on an existing receipt.
    
    Optional JSON body:
        - keep_overrides: If true, preserve manual vendor/amount/date edits (default: false)
    
    Returns: Updated receipt data
    """
    try:
        # Get existing receipt
        receipt = receipt_repository.get_by_id(receipt_id)
        
        if receipt is None:
            return error_response(
                f'Receipt {receipt_id} not found',
                status_code=404
            )
        
        file_path = receipt.get('file_path')
        
        if not file_path:
            return error_response(
                f'No image file associated with receipt {receipt_id}',
                status_code=400
            )
        
        path = Path(file_path)
        
        if not path.exists():
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
        
        logger.info(f"Reprocessing receipt {receipt_id}: {path}")
        
        # Reload and reprocess the image
        receipts = list(receipt_loader.process_files(str(path), yield_pages=True))
        
        if not receipts:
            return error_response(
                'Unable to reprocess the image',
                status_code=422
            )
        
        # Process (handle multi-page)
        processed = receipts[0]
        if len(receipts) > 1:
            processed_all = [receipt_extractor.process_receipt(r) for r in receipts]
            processed = max(processed_all, key=lambda r: r.confidence)
        else:
            processed = receipt_extractor.process_receipt(processed)
        
        # Build update data
        update_kwargs = {
            'confidence': processed.confidence,
            'raw_text': processed.extracted_text,
        }
        
        # Apply new values or keep overrides
        if keep_overrides:
            if original_vendor is None:
                update_kwargs['vendor'] = processed.vendor
            if original_amount is None:
                update_kwargs['amount'] = processed.amount
            if original_date is None:
                update_kwargs['date'] = processed.date
        else:
            update_kwargs['vendor'] = processed.vendor
            update_kwargs['amount'] = processed.amount
            update_kwargs['date'] = processed.date
        
        # Update in database
        updated_receipt = receipt_repository.update(receipt_id, **update_kwargs)
        
        logger.info(f"Reprocessed receipt {receipt_id}: confidence={processed.confidence}")
        
        return success_response({
            'receipt': format_receipt_summary(updated_receipt),
            'message': 'Receipt reprocessed successfully',
            'reprocessing': {
                'kept_overrides': keep_overrides,
                'new_confidence': processed.confidence,
                'extracted_vendor': processed.vendor,
                'extracted_amount': processed.amount,
                'extracted_date': processed.date.isoformat() if processed.date else None
            }
        })
        
    except DatabaseError as e:
        logger.error(f"Database error in reprocess_receipt: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in reprocess_receipt: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)


# 8. Process receipt without saving
@bp.route('/receipts/process', methods=['POST'])
def process_receipt():
    """
    Run OCR on receipt image without saving to database.
    
    Expected: multipart/form-data with 'file' field
    
    Returns: Extracted data (vendor, amount, date, confidence, etc.)
    """
    temp_path = None
    
    try:
        if 'file' not in request.files:
            return error_response('No file provided', status_code=400)
        
        file = request.files['file']
        
        if file.filename == '':
            return error_response('No file selected', status_code=400)
        
        if not allowed_file(file.filename):
            allowed = ', '.join(app.config['ALLOWED_EXTENSIONS'])
            return error_response(
                f'Invalid file type. Allowed types: {allowed}',
                status_code=400
            )
        
        original_filename = secure_filename(file.filename)
        
        # Save temporarily
        file_extension = Path(original_filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)
        
        logger.info(f"Processing receipt image: {original_filename}")
        
        # Load and process
        receipts = list(receipt_loader.process_files(temp_path, yield_pages=True))
        
        if not receipts:
            return error_response(
                'Unable to process the uploaded image',
                status_code=422
            )
        
        # Process each page
        results = []
        for receipt in receipts:
            processed = receipt_extractor.process_receipt(receipt)
            results.append({
                'vendor': processed.vendor,
                'amount': processed.amount,
                'date': processed.date.isoformat() if processed.date else None,
                'confidence': processed.confidence,
                'selected_method': processed.selected_method,
                'raw_text': processed.extracted_text,
            })
        
        # Build response
        if len(results) == 1:
            response = {
                'success': True,
                'original_filename': original_filename,
                'extracted_data': results[0],
                'page_count': 1
            }
        else:
            best_result = max(results, key=lambda x: x['confidence'])
            response = {
                'success': True,
                'original_filename': original_filename,
                'extracted_data': best_result,
                'all_pages': results,
                'page_count': len(results),
                'best_page_index': results.index(best_result)
            }
        
        logger.info(f"Processed {original_filename}: vendor={response['extracted_data']['vendor']}, "
                   f"amount={response['extracted_data']['amount']}")
        
        return jsonify(response), 200
    except FileNotFoundError as e:
        logger.error(f"File not found in process_receipt: {e}")
        return error_response('File processing failed due to file not found error', status_code=400)
    except ValueError as e:
        logger.error(f"Value error in process_receipt: {e}")
        return error_response(f'Processing failed: {str(e)}', status_code=422)        
    except Exception as e:
        logger.error(f"Unexpected error in process_receipt: {e}", exc_info=True)
        return error_response(f'Internal server error: {str(e)}', status_code=500)
    
    finally:
        cleanup_temp_file(temp_path)


# 9. Confirm and save receipt
@bp.route('/receipts/confirm', methods=['POST'])
def confirm_receipt():
    """
    Save receipt data to database (typically after processing/preview).
    
    Expected JSON:
        - original_filename: Original file name
        - stored_filename: (optional) Generated storage name
        - file_path: (optional) Path to stored file
        - vendor: Vendor name
        - amount: Receipt amount
        - date: Receipt date (YYYY-MM-DD)
        - confidence: Confidence score (0-3)
        - selected_method: OCR method used
        - raw_text: (optional) Extracted text
    
    Returns: Saved receipt with receipt_id
    """
    try:
        data = request.get_json()
        
        if data is None:
            return error_response('Request body must be JSON', status_code=400)
        
        # Validate required fields
        required_fields = ['original_filename', 'vendor']
        missing = [f for f in required_fields if f not in data or data[f] is None]
        
        if missing:
            return error_response(
                f'Missing required fields: {", ".join(missing)}',
                status_code=400
            )
        
        # Parse and validate data
        try:
            amount = float(data['amount']) if data.get('amount') is not None else None
        except (ValueError, TypeError):
            return error_response('Invalid amount format', status_code=400)
        
        receipt_date = None
        if data.get('date'):
            try:
                receipt_date = datetime.fromisoformat(data['date'])
            except ValueError:
                return error_response('Invalid date format. Use YYYY-MM-DD', status_code=400)
        
        confidence = data.get('confidence', 0)
        if not isinstance(confidence, int) or confidence < 0 or confidence > 3:
            return error_response('Confidence must be an integer between 0 and 3', status_code=400)
        
        # Generate stored filename if not provided
        stored_filename = data.get('stored_filename')
        if not stored_filename:
            stored_filename = generate_stored_filename(data['original_filename'])
        
        # Create Receipt model
        receipt = Receipt(
            original_filename=data['original_filename'],
            stored_filename=stored_filename,
            file_path=data.get('file_path'),
            vendor=data['vendor'],
            amount=amount,
            date=receipt_date,
            confidence=confidence,
            selected_method=data.get('selected_method', 'manual'),
            extracted_text=data.get('raw_text'),
            page_number=data.get('page_number', 1)
        )
        
        # Save to database
        receipt_id = receipt_repository.save(receipt)
        
        if receipt_id is None:
            return error_response('Failed to save receipt', status_code=500)
        
        # Fetch saved receipt
        saved_receipt = receipt_repository.get_by_id(receipt_id)
        
        logger.info(f"Confirmed and saved receipt {receipt_id}: {data['original_filename']}")
        
        return success_response(
            {
                'receipt': format_receipt_summary(saved_receipt),
                'message': 'Receipt saved successfully'
            },
            status_code=201
        )
        
    except DatabaseError as e:
        logger.error(f"Database error in confirm_receipt: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in confirm_receipt: {e}", exc_info=True)
        return error_response(f'Internal server error: {str(e)}', status_code=500)


# 10. Get receipt statistics (bonus endpoint)
@bp.route('/receipts/stats', methods=['GET'])
def get_receipt_stats():
    """
    Get receipt statistics.
    
    Returns: Aggregated statistics about receipts
    """
    try:
        stats = receipt_repository.get_stats()
        
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
        
    except DatabaseError as e:
        logger.error(f"Database error in get_receipt_stats: {e}")
        return error_response(f'Database error: {str(e)}', status_code=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_receipt_stats: {e}", exc_info=True)
        return error_response('Internal server error', status_code=500)