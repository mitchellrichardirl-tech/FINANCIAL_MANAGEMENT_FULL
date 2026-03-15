import numpy as np
from dataclasses import dataclass
from typing import Dict
from datetime import datetime
from pathlib import Path

@dataclass
class Transaction:
    id: int
    transaction_date: datetime
    amount: float
    description: str
    created_at: datetime
    is_credit: bool
    account_id: int
    upload_id: int
    party_id: int
    is_kids: bool
    is_one_off: bool
    cleaned_description: str|None = None
    receipt_id: int|None = None

