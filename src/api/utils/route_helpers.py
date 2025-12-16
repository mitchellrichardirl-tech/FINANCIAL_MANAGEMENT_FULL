import logging
from functools import wraps
from typing import Callable, Optional, Type

from flask import jsonify, request

from src.api.utils.response_helpers import error_response
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