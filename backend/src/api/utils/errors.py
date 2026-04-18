from enum import Enum
from dataclasses import dataclass, field as dc_field
from typing import Any

class ErrorCode(str, Enum):
    """Error codes that frontend can map to user messages."""
    
    # Validation
    REQUIRED_FIELD = "REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_VALUE = "INVALID_VALUE"
    CONFLICT = "CONFLICT"
    
    # Conflicts
    DUPLICATE_NAME = "DUPLICATE_NAME"
    FOREIGN_KEY_VIOLATION = "FOREIGN_KEY_VIOLATION"
    HAS_DEPENDENCIES = "HAS_DEPENDENCIES"
    
    # Not found
    NOT_FOUND = "NOT_FOUND"
    PARENT_NOT_FOUND = "PARENT_NOT_FOUND"
    
    # System
    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"


@dataclass
class AppError(Exception):
    """Structured application error."""
    code: ErrorCode
    message: str
    status_code: int = 400
    field: str|None = None
    entity: str|None = None
    details: dict = dc_field(default_factory=dict)
    
    def __post_init__(self):
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        result = {
            'code': self.code.value,
            'message': self.message,
        }
        if self.field:
            result['field'] = self.field
        if self.entity:
            result['entity'] = self.entity
        if self.details:
            result['details'] = self.details
        return result


# Convenience factory functions
def not_found(entity: str, identifier: Any = None) -> AppError:
    msg = f"{entity} not found" if identifier is None else f"{entity} {identifier} not found"
    return AppError(
        code=ErrorCode.NOT_FOUND,
        message=msg,
        status_code=404,
        entity=entity,
        details={'identifier': identifier} if identifier else {}
    )

def duplicate(entity: str, field: str = 'name', value: str = None) -> AppError:
    msg = f"{entity} with this {field} already exists"
    if value:
        msg = f'{entity} "{value}" already exists'
    return AppError(
        code=ErrorCode.DUPLICATE_NAME,
        message=msg,
        status_code=409,
        entity=entity,
        field=field,
        details={'value': value} if value else {}
    )

def required(field: str) -> AppError:
    return AppError(
        code=ErrorCode.REQUIRED_FIELD,
        message=f"{field} is required",
        status_code=400,
        field=field
    )

def has_dependencies(entity: str, dependency: str) -> AppError:
    return AppError(
        code=ErrorCode.HAS_DEPENDENCIES,
        message=f"Cannot delete {entity}: has associated {dependency}",
        status_code=409,
        entity=entity,
        details={'dependency': dependency}
    )

def invalid_value(message: str, field: str = None) -> AppError:
    return AppError(
        code=ErrorCode.INVALID_VALUE,
        message=message,
        status_code=400,
        field=field
    )