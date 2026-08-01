import re
from functools import wraps
from typing import Callable, Optional, Type, List, Union
from dataclasses import dataclass

from flask import request

from src.api.utils.response_helpers import error_response
from src.api.utils.file_handling import FileHandler, TempFileManager
from src.api.utils.errors import (
  AppError, ErrorCode, not_found, duplicate, has_dependencies, invalid_value
)
from src.database.errors import DatabaseError
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)

SQLITE_CONSTRAINT_MAP = {
    'categories.category': ('Category', 'name'),
    'sub_categories.sub_category': ('Sub-category', 'name'),
    'types.type': ('Type', 'name'),
    'parties.name': ('Party', 'name'),
}

def require_json(f: Callable) -> Callable:
    """Decorator to require JSON request body."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            logger.debug(
                f"Non-JSON request rejected for {f.__name__}: "
                f"content_type={request.content_type}"
            )
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

            logger.debug(
                f"Validating request for {f.__name__} "
                f"with {validator_class.__name__}"
            )

            validator = validator_class(data)

            if not validator.is_valid():
                logger.debug(
                    f"Validation failed for {f.__name__}: "
                    f"{validator.first_error_message()}"
                )
                return error_response(validator.first_error_message(), status_code=400)

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
                logger.debug(f"Missing {id_param} for {f.__name__}")
                return error_response(f'{resource_name} ID is required', status_code=400)

            resource = repository.get_by_id(resource_id)
            if resource is None:
                logger.debug(f"{resource_name} {resource_id} not found for {f.__name__}")
                return error_response(
                    f'{resource_name} {resource_id} not found',
                    status_code=404
                )

            kwargs['resource'] = resource
            return f(*args, **kwargs)
        return wrapper
    return decorator


def with_uploaded_file(allowed_extensions: set|None = None):
    """Decorator that handles file upload boilerplate."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            logger.debug(
                f"Handling file upload for {f.__name__} "
                f"| allowed_extensions={allowed_extensions}"
            )

            file_handler = FileHandler(allowed_extensions=allowed_extensions)
            validation = file_handler.validate_file(request.files.get('file'))

            if not validation.is_valid:
                return error_response(validation.error, status_code=400)

            if kwargs.get('temp_path'):
                logger.debug("temp_path already provided, skipping file save")
                return f(*args, **kwargs)

            with TempFileManager() as temp_manager:
                temp_path = temp_manager.save_file_to_temp(
                    request.files['file'],
                    suffix=validation.extension
                )
                logger.debug(
                    f"File ready for {f.__name__}: "
                    f"{validation.secured_filename} -> {temp_path}"
                )
                return f(temp_path=temp_path, file_info=validation, *args, **kwargs)
        return wrapper
    return decorator


def parse_sheet_name(form_data, default=0):
    """Parse sheet_name as int if numeric, otherwise keep as string."""
    sheet_name = form_data.get('sheet_name', default)
    try:
        return int(sheet_name)
    except (ValueError, TypeError):
        logger.debug(f"Sheet name kept as string: '{sheet_name}'")
        return sheet_name


def parse_csv_list(form_data, key: str, type_cast=None) -> Optional[list]:
    """Parse a comma-separated form value into a list."""
    if key not in form_data:
        return None

    items = [item.strip() for item in form_data[key].split(',') if item.strip()]

    if not items:
        logger.debug(f"Empty CSV list for key '{key}'")
        return None

    if type_cast:
        parsed = []
        cast_failures = 0
        for item in items:
            try:
                parsed.append(type_cast(item))
            except (ValueError, TypeError):
                parsed.append(item)
                cast_failures += 1

        if cast_failures:
            logger.debug(
                f"CSV list '{key}': {cast_failures}/{len(items)} items "
                f"failed {type_cast.__name__} cast"
            )
        return parsed

    return items


def parse_bool(form_data, key: str, default: bool = True) -> bool:
    """Parse a boolean form value."""
    return form_data.get(key, str(default)).lower() == 'true'

def classify_database_error(e: Exception, entity_hint: str|None = None) -> AppError:
    """Convert a database exception to a structured AppError."""
    error_str = str(e).lower()

    # ── Duplicate / unique violations ──
    # Covers:
    #   - SQLite raw: "UNIQUE constraint failed: categories.category"
    #   - Postgres raw: "duplicate key value violates unique constraint"
    #   - Repo-wrapped: "Record already exists: (...)"
    if any(k in error_str for k in ('unique constraint', 'duplicate key', 'already exists')):
        entity = entity_hint or 'Item'
        field = 'name'
        value = None

        # SQLite: "UNIQUE constraint failed: categories.category"
        m = re.search(r'unique constraint failed:\s*(\w+\.\w+)', error_str)
        if m:
            constraint = m.group(1)
            if constraint in SQLITE_CONSTRAINT_MAP:
                entity, field = SQLITE_CONSTRAINT_MAP[constraint]

        # Postgres: 'constraint "categories_category_key"'
        m = re.search(r'constraint "(\w+?)(?:_key|_unique)?"', error_str)
        if m:
            constraint = m.group(1)
            # reuse your existing CONSTRAINT_ENTITY_MAP lookup here if you
            # ever run against Postgres

        # Repo-wrapped: "Record already exists: ('Groceries', ...)"
        # Try to pull the offending value out of the tuple repr
        m = re.search(r"already exists:\s*\('([^']+)'", str(e))
        if m:
            value = m.group(1)

        return duplicate(entity=entity, field=field, value=value)

    # ── Foreign key violations ──
    if 'foreign key' in error_str:
        if 'is still referenced' in error_str or 'constraint failed' in error_str:
            # SQLite: "FOREIGN KEY constraint failed" (unfortunately not specific)
            # We can't tell insert-fk vs delete-fk from SQLite's message alone,
            # so lean on entity_hint + context
            return AppError(
                code=ErrorCode.FOREIGN_KEY_VIOLATION,
                message="Operation would violate a relationship constraint.",
                status_code=409,
                entity=entity_hint,
            )
        return AppError(
            code=ErrorCode.PARENT_NOT_FOUND,
            message="Referenced item does not exist. It may have been deleted.",
            status_code=400,
        )

    # ── Not found ──
    if 'not found' in error_str or 'does not exist' in error_str:
        return not_found(entity=entity_hint or 'Item')

    # ── Fallback ──
    return AppError(
        code=ErrorCode.DATABASE_ERROR,
        message="A database error occurred. Please try again.",
        status_code=500,
    )


def handle_errors(entity: str|None = None):
    """
    Unified error handling decorator.
    
    Args:
        entity: Hint for error messages (e.g., 'Category', 'Transaction')
    
    Usage:
        @handle_errors(entity='Category')
        def create_category():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            
            except AppError as e:
                # Our structured errors — pass through
                logger.info(f"{f.__name__}: {e.code.value} - {e.message}")
                return error_response(e)
            
            except DatabaseError as e:
                # Classify and convert
                app_error = classify_database_error(e, entity_hint=entity)
                logger.warning(f"{f.__name__}: DatabaseError -> {app_error.code.value}: {e}")
                return error_response(app_error)
            
            except ValueError as e:
                # Common for repo-layer validation
                logger.info(f"{f.__name__}: ValueError - {e}")
                return error_response(invalid_value(str(e)))
            
            except Exception as e:
                logger.error(f"{f.__name__}: Unexpected error: {e}", exc_info=True)
                return error_response(AppError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="An unexpected error occurred",
                    status_code=500
                ))
        
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
        self.logger = ContextLogger(logger_name)

    def get_or_404(self, resource_id: int):
        """Get a resource or return 404 response."""
        resource = self.repository.get_by_id(resource_id)
        if resource is None:
            self.logger.debug(f"{self.resource_name} {resource_id} not found")
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
            self.logger.error(
                f"Failed to delete {self.resource_name} {resource_id}"
            )
            return error_response(
                f'Failed to delete {self.resource_name} {resource_id}',
                status_code=500
            )

        self.logger.info(f"Deleted {self.resource_name} {resource_id}")
        return None


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
        params = cls(
            sheet_name=cls._parse_sheet_name(form_data),
            min_rows=form_data.get('min_rows', 0, type=int),
            min_columns=form_data.get('min_columns', 1, type=int),
            required_columns=parse_csv_list(form_data, 'required_columns'),
        )
        logger.debug(
            f"Parsed validation params: min_rows={params.min_rows}, "
            f"min_columns={params.min_columns}, "
            f"required_columns={params.required_columns}"
        )
        return params


@dataclass
class TabularPreviewParams(BaseTabularParams):
    """Parameters for file preview."""
    num_rows: int = 10
    include_types: bool = True

    @classmethod
    def from_form(cls, form_data) -> 'TabularPreviewParams':
        params = cls(
            sheet_name=cls._parse_sheet_name(form_data),
            num_rows=form_data.get('num_rows', 10, type=int),
            include_types=parse_bool(form_data, 'include_types', True),
        )
        logger.debug(
            f"Parsed preview params: num_rows={params.num_rows}, "
            f"include_types={params.include_types}"
        )
        return params


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
        params = cls(
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
        logger.debug(
            f"Parsed import params: start_row={params.start_row}, "
            f"has_header={params.has_header}, "
            f"columns={params.columns}, account_id={params.account_id}"
        )
        return params