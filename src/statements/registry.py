from typing import Optional, Type

from src.statements.base import (
    StatementProcessor,
    ConfigurableStatementProcessor
)
from src.statements.configs import STATEMENT_CONFIGS
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


# Custom processors that override default behavior
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
    """
    Factory function to get the appropriate statement processor.
    
    Args:
        statement_type: Key identifying the bank/account type (e.g., 'ptsb_current')
        account_id: Database account ID
        upload_id: Database upload ID
        categorizer: Optional custom categorizer
        **kwargs: Additional arguments for custom processors
        
    Returns:
        Configured StatementProcessor instance
        
    Raises:
        ValueError: If statement_type is not recognized
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
    """List all available statement types with their metadata."""
    return [
        {
            'type_key': key,
            'bank_name': config.bank_name,
            'account_type': config.account_type,
            'has_custom_processor': key in CUSTOM_PROCESSORS
        }
        for key, config in STATEMENT_CONFIGS.items()
    ]