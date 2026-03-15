from .ptsb import PTSB_CURRENT, PTSB_CREDIT_CARD
from .aib import AIB_CURRENT
from .revolut import REVOLUT_CURRENT

# Registry of all available configurations
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