"""
Statement processor registry and factory.

Maps statement-type keys (e.g. "ptsb_current", "aib_visa") to the
appropriate processor, either a `ConfigurableStatementProcessor` driven
by a declarative config or a custom `StatementProcessor` subclass for
banks that need bespoke parsing logic.

This is the single entry point for obtaining a processor — callers
should use `get_processor()` rather than importing individual configs
or processors directly.

Typical usage:
    from src.statements.registry import get_processor

    processor = get_processor(
        statement_type="ptsb_current",
        account_id=1,
        upload_id=42,
    )
    transactions = processor.process(dataframe)
"""

from typing import Optional, Type

from src.statements.base import (
    StatementProcessor,
    ConfigurableStatementProcessor
)
from src.statements.configs import STATEMENT_CONFIGS
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


# Custom processors that override default behavior.
# Map statement-type keys to processor classes for banks that can't be
# handled by the declarative config alone (e.g. Revolut's non-standard
# CSV structure). The configurable path is preferred whenever possible.
CUSTOM_PROCESSORS: dict[str, Type[StatementProcessor]] = {
    # 'revolut_current': RevolutStatementProcessor,
}


def get_processor(
    statement_type: str,
    account_id: int,
    upload_id: int,
    categorizer: Optional[TransactionCategorizer] = None,
    **kwargs
) -> StatementProcessor:
    """Create and return the appropriate processor for a statement type.

    Checks `CUSTOM_PROCESSORS` first (for banks with bespoke logic),
    then falls back to `ConfigurableStatementProcessor` with the
    matching declarative config from `STATEMENT_CONFIGS`.

    Args:
        statement_type: Key identifying the bank and account format
            (e.g. "ptsb_current", "aib_visa"). Must exist in
            `STATEMENT_CONFIGS`.
        account_id: FK to `accounts.id` — attached to every
            transaction produced by the processor.
        upload_id: FK to `uploads.id` — the import batch these
            transactions belong to.
        categorizer: Custom `TransactionCategorizer` instance. If None,
            the processor will create its own with default settings.
        **kwargs: Additional keyword arguments forwarded to custom
            processor constructors only. Ignored for configurable
            processors.

    Returns:
        A ready-to-use `StatementProcessor` instance.

    Raises:
        ValueError: If `statement_type` is not found in
            `STATEMENT_CONFIGS`. The error message lists all available
            types.
    """
    if statement_type not in STATEMENT_CONFIGS:
        available = ', '.join(sorted(STATEMENT_CONFIGS.keys()))
        raise ValueError(
            f"Unknown statement type: '{statement_type}'. "
            f"Available types: {available}"
        )

    # Check for custom processor first
    if statement_type in CUSTOM_PROCESSORS:
        processor_class = CUSTOM_PROCESSORS[statement_type]
        logger.debug(f"Using custom processor: {processor_class.__name__}")
        return processor_class(
            account_id=account_id,
            upload_id=upload_id,
            categorizer=categorizer,
            **kwargs
        )

    # Use configurable processor with the config
    config = STATEMENT_CONFIGS[statement_type]
    logger.debug(f"Using configurable processor for: {config.bank_name} {config.account_type}")
    return ConfigurableStatementProcessor(
        statement_config=config,
        account_id=account_id,
        upload_id=upload_id,
        categorizer=categorizer
    )


def list_available_types() -> list[dict]:
    """List all registered statement types with their metadata.

    Used by the API to populate the statement-format dropdown in the
    UI. Includes both config-driven and custom-processor types.

    Returns:
        List of dicts, each with:
            - `type_key`: The registry key (e.g. "ptsb_current").
            - `bank_name`: Human-readable bank name.
            - `account_type`: Account kind (e.g. "current", "visa").
            - `has_custom_processor`: True if this type uses a custom
              processor class rather than the configurable path.
    """
    return [
        {
            'type_key': key,
            'bank_name': config.bank_name,
            'account_type': config.account_type,
            'has_custom_processor': key in CUSTOM_PROCESSORS
        }
        for key, config in STATEMENT_CONFIGS.items()
    ]