"""
Bank-specific statement format configurations.

Each module defines one or more `StatementConfig` instances describing
how a bank's CSV/Excel export maps to the application's transaction
schema. Configs are collected into `STATEMENT_CONFIGS` and consumed
by `registry.get_processor()`.

To add a new bank:
    1. Create a new file in this directory (e.g. `boi.py`).
    2. Define one `StatementConfig` per account type.
    3. Import and register it in `STATEMENT_CONFIGS` below.

See `base.py` for full documentation of `StatementConfig`,
`DateConfig`, and `AmountConfig`.
"""

from .ptsb import PTSB_CURRENT, PTSB_CREDIT_CARD
from .aib import AIB_CURRENT
from .revolut import REVOLUT_CURRENT

# Registry of all available statement formats.
# Keys are the identifiers used by the API and accounts table
# (`accounts.statement_format`). Values are `StatementConfig` instances.
STATEMENT_CONFIGS = {
    'ptsb_current': PTSB_CURRENT,
    'ptsb_credit_card': PTSB_CREDIT_CARD,
    'aib_current': AIB_CURRENT,
    'revolut_current': REVOLUT_CURRENT,
}

__all__ = [
    'PTSB_CURRENT',
    'PTSB_CREDIT_CARD', 
    'AIB_CURRENT',
    'REVOLUT_CURRENT',
    'STATEMENT_CONFIGS',
]