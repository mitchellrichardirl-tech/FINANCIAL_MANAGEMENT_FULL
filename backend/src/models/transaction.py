"""
Data model for a financial transaction.

Represents a single row in the `transactions` table — a bank or card
transaction imported from a statement, linked to the category hierarchy
via `party_id` and optionally to a receipt image via `receipt_id`.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Transaction:
    """A single financial transaction.

    Maps directly to the `transactions` table schema. Constructed from
    `Transaction` objects during statement import and reconstructed
    from database rows by `TransactionRepository` read methods.

    Attributes:
        id: Auto-generated primary key. Set by the database on insert.
        transaction_date: Date the transaction occurred (not the date
            it was imported).
        amount: Transaction value. Can be positive or negative.
        description: Raw description text from the bank statement.
        created_at: Timestamp the row was inserted into the database.
        is_credit: True for income/credits, False for expenses/debits.
            Transactions which are refunds or reversals of previous transactions
            should be marked as debits, even if they have a positive amount.
        account_id: FK to `accounts.id` — which bank account the
            transaction belongs to.
        upload_id: FK to `uploads.id` — which import batch this
            transaction came from.
        party_id: FK to `parties.id` — the counterparty, which links
            through to the full category hierarchy
            (party → type → sub_category → category).
        is_kids: True if flagged as a child-related expense.
        is_one_off: True if flagged as non-recurring (excluded from
            recurring-spend analysis).
        cleaned_description: Normalised description after the
            categorizer strips bank-specific prefixes/suffixes. Used
            for party matching.
        receipt_id: FK to `receipts.id` if a receipt image has been
            linked to this transaction. None if unmatched.
    """
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
    cleaned_description: str | None = None
    receipt_id: int | None = None