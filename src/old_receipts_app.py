from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
import os
import tempfile

from src.database.database import Database, DatabaseError
from src.receipts.receipt_extractor import ReceiptExtractor
from src.receipts.receipt_loader import ReceiptLoader

app = Flask(__name__)
CORS(app)  # Enable CORS if you need frontend access

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf'}


# Helper function to validate file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

db = Database()
receipt_loader = ReceiptLoader()
receipt_extractor = ReceiptExtractor()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1. Upload receipt image
@app.route('/api/receipts/upload', methods=['POST'])
def upload_receipt():
    """
    Upload a receipt image file
    Expected: multipart/form-data with 'file' field
    Returns: receipt_id and status
    """
    pass


# 2. Get list of receipts with optional filters
@app.route('/api/receipts', methods=['GET'])
def get_receipts():
    """
    Get list of receipts
    Query params: 
        - vendor (optional): filter by vendor name
        - min_confidence (optional): minimum confidence score (0-3)
        - limit (optional): max number of results (default: 50, max: 500)
        - offset (optional): pagination offset (default: 0)
        - start_date (optional): filter receipts from this date (ISO format: YYYY-MM-DD)
        - end_date (optional): filter receipts until this date (ISO format: YYYY-MM-DD)
    Returns: list of receipts with pagination info
    """
    try:
        # Parse and validate query parameters
        vendor = request.args.get('vendor', type=str)
        min_confidence = request.args.get('min_confidence', type=int)
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        start_date_str = request.args.get('start_date', type=str)
        end_date_str = request.args.get('end_date', type=str)
        
        # Validate limit
        if limit < 1:
            return jsonify({'error': 'Limit must be at least 1'}), 400
        if limit > 500:
            return jsonify({'error': 'Limit cannot exceed 500'}), 400
        
        # Validate offset
        if offset < 0:
            return jsonify({'error': 'Offset must be non-negative'}), 400
        
        # Validate confidence
        if min_confidence is not None and (min_confidence < 0 or min_confidence > 3):
            return jsonify({'error': 'Confidence must be between 0 and 3'}), 400
        
        # Parse dates
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        # Validate date range
        if start_date and end_date and start_date > end_date:
            return jsonify({'error': 'start_date cannot be after end_date'}), 400
        
        # Get receipts from database
        receipts = db.get_receipts(
            limit=limit,
            offset=offset,
            vendor=vendor,
            min_confidence=min_confidence,
            start_date=start_date,
            end_date=end_date
        )
        
        # Format receipts for response
        formatted_receipts = []
        for receipt in receipts:
            formatted_receipt = {
                'id': receipt['id'],
                'original_filename': receipt['original_filename'],
                'stored_filename': receipt['stored_filename'],
                'vendor': receipt['vendor'],
                'amount': receipt['amount'],
                'date': receipt['date'].isoformat() if receipt['date'] else None,
                'confidence': receipt['confidence'],
                'selected_method': receipt['selected_method'],
                'created_at': receipt['created_at'],
                'updated_at': receipt['updated_at']
            }
            formatted_receipts.append(formatted_receipt)
        
        # Build response with pagination info
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
        
        logger.info(f"Retrieved {len(formatted_receipts)} receipts (offset: {offset}, limit: {limit})")
        return jsonify(response), 200
        
    except DatabaseError as e:
        logger.error(f"Database error in get_receipts: {e}")
        return jsonify({'error': 'Database error occurred', 'message': str(e)}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in get_receipts: {e}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


# 3. Get specific receipt
@app.route('/api/receipts/<int:receipt_id>', methods=['GET'])
def get_receipt(receipt_id):
    """
    Get a specific receipt by ID
    Returns: receipt details
    """
    pass


# 4. Update specific receipt
@app.route('/api/receipts/<int:receipt_id>', methods=['PUT'])
def update_receipt(receipt_id):
    """
    Update receipt attributes (vendor, amount, date)
    Expected: JSON with fields to update
    Returns: updated receipt
    """
    pass


# 5. Delete specific receipt
@app.route('/api/receipts/<int:receipt_id>', methods=['DELETE'])
def delete_receipt(receipt_id):
    """
    Delete a specific receipt
    Returns: success status
    """
    pass


# 6. Get receipt image file
@app.route('/api/receipts/<int:receipt_id>/image', methods=['GET'])
def get_receipt_image(receipt_id):
    """
    Get the image file for a specific receipt
    Returns: image file
    """
    pass


# 7. Reprocess receipt (rerun OCR)
@app.route('/api/receipts/<int:receipt_id>/reprocess', methods=['POST'])
def reprocess_receipt(receipt_id):
    """
    Rerun OCR processing on an existing receipt
    Returns: updated receipt data
    """
    pass


# 8. Process receipt without saving
@app.route('/api/receipts/process', methods=['POST'])
def process_receipt():
    """
    Run OCR on receipt image without saving to database
    Expected: multipart/form-data with 'file' field
    Returns: extracted data (vendor, amount, date, confidence, etc.)
    """
    temp_path = None
    
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Request must include a file field'
            }), 400
        
        file = request.files['file']
        
        # Check if file was actually selected
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'File field is empty'
            }), 400
        
        # Validate file type
        if not allowed_file(file.filename):
            allowed = ', '.join(app.config['ALLOWED_EXTENSIONS'])
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Allowed file types: {allowed}'
            }), 400
        
        # Secure the filename
        original_filename = secure_filename(file.filename)
        
        # Save file temporarily for processing
        file_extension = os.path.splitext(original_filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)
        
        logger.info(f"Processing receipt image: {original_filename}")
        
        # Load and preprocess the image using ReceiptLoader
        # Handle both single images and PDFs (which may yield multiple pages)
        receipts = list(receipt_loader.process_files(temp_path, yield_pages=True))
        
        if not receipts:
            return jsonify({
                'error': 'Processing failed',
                'message': 'Unable to load or preprocess the image'
            }), 422
        
        # Process each receipt (page) and collect results
        results = []
        for receipt in receipts:
            # Extract information using OCR
            processed_receipt = receipt_extractor.process_receipt(receipt)
            
            result = {
                'vendor': processed_receipt.vendor,
                'amount': processed_receipt.amount,
                'date': processed_receipt.date.isoformat() if processed_receipt.date else None,
                'confidence': processed_receipt.confidence,
                'selected_method': processed_receipt.selected_method,
                'raw_text': processed_receipt.extracted_text,
            }
            results.append(result)
        
        # If single page/image, return single result
        # If multiple pages (PDF), return array of results
        if len(results) == 1:
            response = {
                'success': True,
                'original_filename': original_filename,
                'extracted_data': results[0],
                'page_count': 1
            }
        else:
            # For multi-page documents, also identify the best result
            best_result = max(results, key=lambda x: x['confidence'])
            response = {
                'success': True,
                'original_filename': original_filename,
                'extracted_data': best_result,  # Best overall result
                'all_pages': results,  # All page results
                'page_count': len(results),
                'best_page_index': results.index(best_result)
            }
        
        logger.info(f"Successfully processed {original_filename}: "
                   f"vendor={response['extracted_data']['vendor']}, "
                   f"amount={response['extracted_data']['amount']}, "
                   f"confidence={response['extracted_data']['confidence']}")
        
        return jsonify(response), 200
        
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        return jsonify({
            'error': 'File processing failed',
            'message': 'Unable to process the uploaded file'
        }), 400
        
    except ValueError as e:
        logger.error(f"Value error in processing: {e}")
        return jsonify({
            'error': 'Processing failed',
            'message': str(e)
        }), 422
        
    except Exception as e:
        logger.error(f"Unexpected error in process_receipt: {e}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while processing the receipt'
        }), 500
        
    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")

# 9. Confirm and save receipt
@app.route('/api/receipts/confirm', methods=['POST'])
def confirm_receipt():
    """
    Save receipt and its attributes to database
    Expected: JSON with receipt data
    Returns: saved receipt with receipt_id
    """
    pass


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)