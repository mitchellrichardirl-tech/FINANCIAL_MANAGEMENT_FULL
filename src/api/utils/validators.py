from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from dataclasses import dataclass
from pathlib import Path
from flask import current_app as app
from werkzeug.datastructures import FileStorage


@dataclass
class ValidationError:
    """Represents a validation error."""
    field: str
    message: str
    code: str = "invalid"


@dataclass  
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    value: Any = None
    error: Optional[ValidationError] = None
    
    @classmethod
    def success(cls, value: Any) -> 'ValidationResult':
        return cls(is_valid=True, value=value)
    
    @classmethod
    def failure(cls, field: str, message: str, code: str = "invalid") -> 'ValidationResult':
        return cls(is_valid=False, error=ValidationError(field, message, code))


class FieldValidator:
    """Chainable field validator."""
    
    def __init__(self, field_name: str, value: Any):
        self.field_name = field_name
        self.value = value
        self.errors: List[ValidationError] = []
        self._stopped = False
    
    def required(self) -> 'FieldValidator':
        """Check if field is present and not None."""
        if not self._stopped and self.value is None:
            self.errors.append(ValidationError(self.field_name, f"{self.field_name} is required", "required"))
            self._stopped = True
        return self
    
    def optional(self) -> 'FieldValidator':
        """Mark field as optional - stop validation chain if None."""
        if self.value is None:
            self._stopped = True
        return self
    
    def is_type(self, expected_type: type, type_name: str = None) -> 'FieldValidator':
        """Validate value is of expected type."""
        if self._stopped:
            return self
        type_name = type_name or expected_type.__name__
        if not isinstance(self.value, expected_type):
            self.errors.append(ValidationError(
                self.field_name, 
                f"{self.field_name} must be a {type_name}", 
                "type_error"
            ))
            self._stopped = True
        return self
    
    def in_range(self, min_val: Optional[float] = None, max_val: Optional[float] = None) -> 'FieldValidator':
        """Validate numeric value is within range."""
        if self._stopped:
            return self
        if min_val is not None and self.value < min_val:
            self.errors.append(ValidationError(
                self.field_name,
                f"{self.field_name} must be at least {min_val}",
                "min_value"
            ))
        elif max_val is not None and self.value > max_val:
            self.errors.append(ValidationError(
                self.field_name,
                f"{self.field_name} must be at most {max_val}",
                "max_value"
            ))
        return self
    
    def transform(self, transformer: Callable[[Any], Any], error_message: str = None) -> 'FieldValidator':
        """Transform value using provided function."""
        if self._stopped:
            return self
        try:
            self.value = transformer(self.value)
        except (ValueError, TypeError) as e:
            message = error_message or f"Invalid {self.field_name} format"
            self.errors.append(ValidationError(self.field_name, message, "transform_error"))
            self._stopped = True
        return self
    
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def get_result(self) -> ValidationResult:
        if self.errors:
            return ValidationResult.failure(
                self.errors[0].field,
                self.errors[0].message,
                self.errors[0].code
            )
        return ValidationResult.success(self.value)


class RequestValidator:
    """Validate request data with fluent interface."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data or {}
        self.validated: Dict[str, Any] = {}
        self.errors: List[ValidationError] = []
    
    def field(self, field_name: str) -> FieldValidator:
        """Start validating a field."""
        return FieldValidator(field_name, self.data.get(field_name))
    
    def validate_field(self, field_name: str, validator: FieldValidator) -> 'RequestValidator':
        """Add validated field to results."""
        result = validator.get_result()
        if result.is_valid:
            if result.value is not None:  # Don't add None values
                self.validated[field_name] = result.value
        else:
            self.errors.append(result.error)
        return self
    
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def get_errors(self) -> List[Dict[str, str]]:
        return [{"field": e.field, "message": e.message, "code": e.code} for e in self.errors]
    
    def first_error_message(self) -> Optional[str]:
        return self.errors[0].message if self.errors else None


# Common transformers
def parse_date(value: str) -> datetime:
    """Parse ISO format date string."""
    return datetime.fromisoformat(value)


def parse_float(value: Any) -> float:
    """Parse value as float."""
    return float(value)


def parse_int(value: Any) -> int:
    """Parse value as integer."""
    return int(value)


# Common validators for receipts
def validate_confidence(value: Any) -> ValidationResult:
    """Validate confidence score."""
    validator = FieldValidator("confidence", value).optional().is_type(int).in_range(0, 3)
    return validator.get_result()


def validate_amount(value: Any) -> ValidationResult:
    """Validate receipt amount."""
    validator = FieldValidator("amount", value).optional().transform(parse_float, "Invalid amount format")
    return validator.get_result()


def validate_receipt_date(value: Any) -> ValidationResult:
    """Validate receipt date."""
    validator = FieldValidator("date", value).optional().transform(parse_date, "Invalid date format. Use YYYY-MM-DD")
    return validator.get_result()


def validate_pagination(args: Dict) -> Tuple[bool, Dict, Optional[str]]:
    """Validate common pagination parameters."""
    validator = RequestValidator(args)
    
    limit_validator = validator.field("limit").optional().transform(parse_int).in_range(1, 500)
    offset_validator = validator.field("offset").optional().transform(parse_int).in_range(0)
    
    validator.validate_field("limit", limit_validator)
    validator.validate_field("offset", offset_validator)
    
    if not validator.is_valid():
        return False, {}, validator.first_error_message()
    
    return True, {
        "limit": validator.validated.get("limit", 50),
        "offset": validator.validated.get("offset", 0)
    }, None