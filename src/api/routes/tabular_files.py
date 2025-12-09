from datetime import datetime

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import logging

from src.api.routes.health import status
from src.utils.tabular_files.processor import TabularProcessor
from src.utils.tabular_files.exceptions import (
    TabularProcessorError,
    FileNotFoundError,
    UnsupportedFileTypeError
)
from src.api.utils.file_handling import save_upload_file, cleanup_temp_file
from src.api.utils.response_helpers import success_response, error_response

from src.statements.statement import Statement

from src.database.connection import DatabaseError
from src.database.repositories.uploads import UploadRepository
from src.database.repositories.transactions import TransactionRepository

bp = Blueprint('tabular_files', __name__)

logger = logging.getLogger(__name__)

@bp.route('/validate', methods=['POST'])
def validate_file():
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
    if 'file' not in request.files:
        return error_response('No file provided', status_code=400)
    
    file = request.files['file']
    if file.filename == '':
        return error_response('Empty filename', status_code=400)
    
    # Save file temporarily
    temp_path = None
    try:
        temp_path = save_upload_file(file)
        
        # Parse optional parameters
        min_rows = request.form.get('min_rows', 0, type=int)
        min_columns = request.form.get('min_columns', 1, type=int)
        sheet_name = request.form.get('sheet_name', 0)
        
        # Parse sheet_name as int if it's numeric
        try:
            sheet_name = int(sheet_name)
        except (ValueError, TypeError):
            pass
        
        # Parse required columns
        required_columns = None
        if 'required_columns' in request.form:
            cols = request.form['required_columns']
            required_columns = [c.strip() for c in cols.split(',') if c.strip()]
        
        # Validate
        processor = TabularProcessor()
        result = processor.validate(
            temp_path,
            min_rows=min_rows,
            min_columns=min_columns,
            required_columns=required_columns,
            sheet_name=sheet_name
        )
        
        return jsonify(result.to_dict())
        
    except Exception as e:
        return error_response(f'Validation failed: {str(e)}', status_code=500)
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)


@bp.route('/preview', methods=['POST'])
def preview_file():
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
    if 'file' not in request.files:
        return error_response('No file provided', status_code=400)
    
    file = request.files['file']
    if file.filename == '':
        return error_response('Empty filename', status_code=400)
    
    temp_path = None
    try:
        temp_path = save_upload_file(file)
        
        # Parse parameters
        num_rows = request.form.get('num_rows', 10, type=int)
        sheet_name = request.form.get('sheet_name', 0)
        include_types = request.form.get('include_types', 'true').lower() == 'true'
        
        # Parse sheet_name
        try:
            sheet_name = int(sheet_name)
        except (ValueError, TypeError):
            pass
        
        # Preview
        processor = TabularProcessor()
        result = processor.preview(
            temp_path,
            num_rows=num_rows,
            sheet_name=sheet_name,
            include_types=include_types
        )
        
        return jsonify(result.to_dict())
        
    except Exception as e:
        return error_response(f'Preview failed: {str(e)}', status_code=500)
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)


@bp.route('/import', methods=['POST'])
def import_file():
    """
    Import data from a tabular file.
    
    Request:
        - file: Uploaded file
        - start_row: Row to start importing from (default: 0)
        - columns: Optional comma-separated list of column indices or names
        - column_names: Optional comma-separated list of custom column names
        - has_header: Whether file has header (default: true)
        - sheet_name: Optional sheet name for Excel files
        - max_rows: Optional maximum number of rows to import
        - skip_empty_rows: Whether to skip empty rows (default: true)
        - strip_whitespace: Whether to strip whitespace (default: true)
        
    Returns:
        ImportResult as JSON
    """
    if 'file' not in request.files:
        return error_response('No file provided', status_code=400)
    
    file = request.files['file']
    if file.filename == '':
        return error_response('Empty filename', status_code=400)
    
    temp_path = None
    try:
        temp_path = save_upload_file(file)
        logger.debug(f'Importing file: {temp_path}')
        # Parse parameters
        start_row = request.form.get('start_row', 0, type=int)
        has_header = request.form.get('has_header', 'true').lower() == 'true'
        max_rows = request.form.get('max_rows', type=int)
        skip_empty_rows = request.form.get('skip_empty_rows', 'true').lower() == 'true'
        strip_whitespace = request.form.get('strip_whitespace', 'true').lower() == 'true'
        sheet_name = request.form.get('sheet_name', 0)
        
        # Parse sheet_name
        try:
            sheet_name = int(sheet_name)
        except (ValueError, TypeError):
            pass
        
        # Parse columns
        columns = None
        if 'columns' in request.form:
            cols = request.form['columns']
            columns = []
            for c in cols.split(','):
                c = c.strip()
                if c:
                    # Try as integer index, otherwise use as string name
                    try:
                        columns.append(int(c))
                    except ValueError:
                        columns.append(c)
        
        # Parse column names
        column_names = None
        if 'column_names' in request.form:
            names = request.form['column_names']
            column_names = [n.strip() for n in names.split(',') if n.strip()]
        
        # Import
        processor = TabularProcessor()
        result = processor.import_data(
            temp_path,
            start_row=start_row,
            columns=columns,
            column_names=column_names,
            has_header=has_header,
            sheet_name=sheet_name,
            max_rows=max_rows,
            skip_empty_rows=skip_empty_rows,
            strip_whitespace=strip_whitespace
        )
        
        try:
            # Save upload record
            upload_repo = UploadRepository()
            upload_result = upload_repo.create_upload_with_data(
                filename=result.file_name,
                file_type=result.file_type,
                columns=result.columns_imported,
                rows=result.data
            )
            result.upload_id = upload_result["upload_id"]
            logger.info(
                f'Upload record created with ID: {upload_result["upload_id"]}, '
                f'Rows: {upload_result["rows_inserted"]}')
        except DatabaseError as db_err:
            return error_response(f'Failed to save upload record: {str(db_err)}', status_code=500)
        try:
            # Prepare transactions
            statement = Statement(
                account_id=request.form.get('account_id', type=int),
                upload_id=upload_result["upload_id"]
            )
            transactions = statement.process_statement(result.data)
        except Exception as e:
            return error_response(f'Failed to process statement: {str(e)}', status_code=500)
        
        try:
            # Save transactions
            transaction_repo = TransactionRepository()
            transaction_ids = transaction_repo.bulk_add_transactions(transactions)
        except DatabaseError as db_err:
            return error_response(f'Failed to save transactions: {str(db_err)}', status_code=500)
        return jsonify(result.to_dict())
        
    except Exception as e:
        return error_response(f'Import failed: {str(e)}', status_code=500)
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)


@bp.route('/sheets', methods=['POST'])
def get_sheets():
    """
    Get sheet names from an Excel file.
    
    Request:
        - file: Uploaded Excel file
        
    Returns:
        SheetInfo as JSON
    """
    if 'file' not in request.files:
        return error_response('No file provided', status_code=400)
    
    file = request.files['file']
    if file.filename == '':
        return error_response('Empty filename', status_code=400)
    
    temp_path = None
    try:
        temp_path = save_upload_file(file)
        
        processor = TabularProcessor()
        result = processor.get_sheet_info(temp_path)
        
        return jsonify(result.to_dict())
        
    except FileNotFoundError:
        return error_response('File not found', status_code=404)
    except Exception as e:
        return error_response(f'Failed to get sheets: {str(e)}', status_code=500)
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)


@bp.route('/check', methods=['POST'])
def check_tabular():
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
    if 'file' not in request.files:
        return error_response('No file provided', status_code=400)
    
    file = request.files['file']
    if file.filename == '':
        return error_response('Empty filename', status_code=400)
    
    temp_path = None
    try:
        temp_path = save_upload_file(file)
        
        processor = TabularProcessor()
        is_tabular = processor.is_tabular(temp_path)
        
        return jsonify({
            'is_tabular': is_tabular,
            'file_name': secure_filename(file.filename)
        })
        
    except Exception as e:
        return error_response(f'Check failed: {str(e)}', status_code=500)
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)

@bp.route('', methods=['GET'])
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
    try:
        # Parse query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        file_type = request.args.get('file_type')
        filename = request.args.get('filename')
        
        # Parse dates
        start_date = None
        end_date = None
        
        if request.args.get('start_date'):
            try:
                from datetime import datetime
                start_date = datetime.fromisoformat(request.args.get('start_date'))
            except ValueError:
                return error_response('Invalid start_date format. Use YYYY-MM-DD', status_code=400)
        
        if request.args.get('end_date'):
            try:
                from datetime import datetime
                end_date = datetime.fromisoformat(request.args.get('end_date'))
            except ValueError:
                return error_response('Invalid end_date format. Use YYYY-MM-DD', status_code=400)
        
        upload_repo = UploadRepository()
        uploads = upload_repo.get_all_uploads(
            limit=limit,
            offset=offset,
            file_type=file_type,
            filename=filename,
            start_date=start_date,
            end_date=end_date
        )
        
        return success_response(data=uploads)
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get uploads: {e}')
        return error_response(f'Failed to get uploads: {str(e)}', status_code=500)


@bp.route('/<int:upload_id>', methods=['GET'])
def get_upload(upload_id: int):
    """
    Get a single upload by ID.
    
    Path Parameters:
        - upload_id: The upload ID
        
    Returns:
        Upload object as JSON or 404 if not found
    """
    try:
        upload_repo = UploadRepository()
        upload = upload_repo.get_upload_by_id(upload_id)
        
        if upload is None:
            return error_response(f'Upload {upload_id} not found', status_code=404)
        
        return success_response(data=upload)
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to get upload {upload_id}: {e}')
        return error_response(f'Failed to get upload: {str(e)}', status_code=500)


@bp.route('/<int:upload_id>', methods=['DELETE'])
def delete_upload(upload_id: int):
    """
    Delete an upload and all associated data.
    
    Path Parameters:
        - upload_id: The upload ID to delete
        
    Returns:
        Success message or 404 if not found
    """
    try:
        upload_repo = UploadRepository()
        deleted = upload_repo.delete_upload(upload_id)
        
        if not deleted:
            return error_response(f'Upload {upload_id} not found', status_code=404)
        
        return success_response(
            data={'deleted_upload_id': upload_id},
            message=f'Upload {upload_id} deleted successfully',
            status_code=200
        )
        
    except DatabaseError as e:
        return error_response(f'Database error: {str(e)}', status_code=500)
    except Exception as e:
        logger.error(f'Failed to delete upload {upload_id}: {e}')
        return error_response(f'Failed to delete upload: {str(e)}', status_code=500)