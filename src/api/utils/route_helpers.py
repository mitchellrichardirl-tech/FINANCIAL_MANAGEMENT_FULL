import logging
from functools import wraps
from typing import Callable, Optional, Type, List, Union
from dataclasses import dataclass, field

from flask import jsonify, request

from src.api.utils.response_helpers import error_response
from src.api.utils.file_handling import FileHandler, TempFileManager
from src.database.connection import DatabaseError

logger = logging.getLogger(__name__)


def handle_exceptions(log_prefix: str = "Error"):
    """
    Decorator to handle common exceptions in routes.
    
    Usage:
        @bp.route('/receipts/<int:id>')
        @handle_exceptions(log_prefix="get_receipt")
        def get_receipt(id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except DatabaseError as e:
                logger.error(f"{log_prefix} - Database error: {e}")
                return error_response(f'Database error: {str(e)}', status_code=500)
            except Exception as e:
                logger.error(f"{log_prefix} - Unexpected error: {e}", exc_info=True)
                return error_response('Internal server error', status_code=500)
        return wrapper
    return decorator


def require_json(f: Callable) -> Callable:
    """Decorator to require JSON request body."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return error_response('Request body must be JSON', status_code=400)
        return f(*args, **kwargs)
    return wrapper


def validate_request(validator_class: Type):
    """
    Decorator to validate request data using a validator class.
    
    The validator class should have:
    - __init__(data: dict)
    - is_valid() -> bool
    - first_error_message() -> str
    - validated -> dict
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            validator = validator_class(data)
            
            if not validator.is_valid():
                return error_response(validator.first_error_message(), status_code=400)
            
            # Add validated data to kwargs
            kwargs['validated_data'] = validator.validated
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_resource(
    repository,
    resource_name: str,
    id_param: str = "id"
):
    """
    Decorator to require a resource exists.
    
    Usage:
        @bp.route('/receipts/<int:receipt_id>')
        @require_resource(receipt_repository, "Receipt", "receipt_id")
        def get_receipt(receipt_id, resource):
            return success_response({'receipt': resource})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            resource_id = kwargs.get(id_param)
            if resource_id is None:
                return error_response(f'{resource_name} ID is required', status_code=400)
            
            resource = repository.get_by_id(resource_id)
            if resource is None:
                return error_response(
                    f'{resource_name} {resource_id} not found',
                    status_code=404
                )
            
            kwargs['resource'] = resource
            return f(*args, **kwargs)
        return wrapper
    return decorator

def with_uploaded_file(allowed_extensions: set = None):
    """Decorator that handles file upload boilerplate."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            logger.debug(f"Processing uploaded file with allowed extensions: {allowed_extensions}")
            file_handler = FileHandler(allowed_extensions=allowed_extensions)
            validation = file_handler.validate_file(request.files.get('file'))
            if not validation.is_valid:
                logger.debug(f"File validation failed: {validation.error}")
                return error_response(validation.error, status_code=400)
            
            with TempFileManager() as temp_manager:
                temp_path = temp_manager.save_file_to_temp(
                    request.files['file'],
                    suffix=validation.extension
                )
                # Inject temp_path into the function
                return f(temp_path=temp_path, file_info=validation, *args, **kwargs)
        return wrapper
    return decorator

def parse_sheet_name(form_data, default=0):
    """Parse sheet_name as int if numeric, otherwise keep as string."""
    sheet_name = form_data.get('sheet_name', default)
    try:
        return int(sheet_name)
    except (ValueError, TypeError):
        return sheet_name

def parse_csv_list(form_data, key: str, type_cast=None) -> Optional[list]:
    """Parse a comma-separated form value into a list."""
    logger.debug(f"Parsing CSV list for key: {key}")
    if key not in form_data:
        logger.error(f"Key {key} not found in form data")
        return None
    
    items = [item.strip() for item in form_data[key].split(',') if item.strip()]
    logger.debug(f"Parsed items: {items}")

    if type_cast:
        logger.debug(f"Cast to items to {type_cast}")
        parsed = []
        for item in items:
            try:
                parsed.append(type_cast(item))
            except (ValueError, TypeError):
                parsed.append(item)  # Keep original if cast fails
        logger.debug(f"Type-cast items: {parsed}")
        return parsed
    
    return items

def parse_bool(form_data, key: str, default: bool = True) -> bool:
    """Parse a boolean form value."""
    return form_data.get(key, str(default)).lower() == 'true'

def handle_database_errors(
    status_mapping: dict[str, int] = None
) -> Callable:
    """
    Decorator to handle database errors with appropriate status codes.
    
    Usage:
        @handle_database_errors({
            'already exists': 409,
            'does not exist': 404,
            'associated': 409
        })
        def create_category():
            ...
    """
    default_mapping = {
        'already exists': 409,
        'does not exist': 404,
        'not found': 404,
        'associated': 409,
        'has': 409,
        'constraint': 409,
        'foreign key': 409,
    }
    
    if status_mapping:
        default_mapping.update(status_mapping)
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except DatabaseError as e:
                error_str = str(e).lower()
                for keyword, status_code in default_mapping.items():
                    if keyword in error_str:
                        return error_response(str(e), status_code=status_code)
                return error_response(f'Database error: {str(e)}', status_code=500)
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                return error_response('Internal server error', status_code=500)
        return wrapper
    return decorator

class ResourceController:
    """
    Base class for resource controllers with common CRUD patterns.
    
    Subclass this for each resource type to reduce boilerplate.
    """
    
    def __init__(self, repository, resource_name: str, logger_name: str):
        self.repository = repository
        self.resource_name = resource_name
        self.logger = logging.getLogger(logger_name)
    
    def get_or_404(self, resource_id: int):
        """Get a resource or return 404 response."""
        resource = self.repository.get_by_id(resource_id)
        if resource is None:
            return None, error_response(
                f'{self.resource_name} {resource_id} not found',
                status_code=404
            )
        return resource, None
    
    def delete_with_response(self, resource_id: int):
        """Delete a resource and return appropriate response."""
        resource, error = self.get_or_404(resource_id)
        if error:
            return error
        
        deleted = self.repository.delete(resource_id)
        if not deleted:
            return error_response(
                f'Failed to delete {self.resource_name} {resource_id}',
                status_code=500
            )
        
        self.logger.info(f"Deleted {self.resource_name} {resource_id}")
        return None  # Success, caller handles response
    

@dataclass
class BaseTabularParams:
    """Base parameters for tabular file processing."""
    sheet_name: Union[int, str] = 0

    @classmethod
    def _parse_sheet_name(cls, form_data, default=0) -> Union[int, str]:
        return parse_sheet_name(form_data)
    
    @classmethod
    def from_form(cls, form_data) -> 'BaseTabularParams':
        raise NotImplementedError("Subclasses must implement from_form method")

@dataclass
class TabularValidationParams(BaseTabularParams):
    """Parameters for file validation."""
    min_rows: int = 0
    min_columns: int = 1
    required_columns: Optional[List[str]] = None
    
    @classmethod
    def from_form(cls, form_data) -> 'TabularValidationParams':
        return cls(
            sheet_name=cls._parse_sheet_name(form_data),
            min_rows=form_data.get('min_rows', 0, type=int),
            min_columns=form_data.get('min_columns', 1, type=int),
            required_columns=parse_csv_list(form_data, 'required_columns'),
        )


@dataclass
class TabularPreviewParams(BaseTabularParams):
    """Parameters for file preview."""
    num_rows: int = 10
    include_types: bool = True
    
    @classmethod
    def from_form(cls, form_data) -> 'TabularPreviewParams':
        return cls(
            sheet_name=cls._parse_sheet_name(form_data),
            num_rows=form_data.get('num_rows', 10, type=int),
            include_types=parse_bool(form_data, 'include_types', True),
        )
    
@dataclass
class TabularImportParams(BaseTabularParams):
    """Parameters for tabular file import."""
    start_row: int = 0
    has_header: bool = True
    max_rows: Optional[int] = None
    skip_empty_rows: bool = True
    strip_whitespace: bool = True
    sheet_name: Union[int, str] = 0
    columns: Optional[List[Union[int, str]]] = None
    column_names: Optional[List[str]] = None
    account_id: Optional[int] = None
    
    @classmethod
    def from_form(cls, form_data) -> 'TabularImportParams':
        """Parse from Flask request.form."""
        return cls(
            start_row=form_data.get('start_row', 0, type=int),
            has_header=parse_bool(form_data, 'has_header'),
            max_rows=form_data.get('max_rows', type=int),
            skip_empty_rows=parse_bool(form_data, 'skip_empty_rows'),
            strip_whitespace=parse_bool(form_data, 'strip_whitespace'),
            sheet_name=parse_sheet_name(form_data),
            columns=parse_csv_list(form_data, 'columns', type_cast=int),
            column_names=parse_csv_list(form_data, 'column_names'),
            account_id=form_data.get('account_id', type=int),
        )