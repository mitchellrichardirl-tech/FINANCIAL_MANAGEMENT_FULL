"""
Service for generating cash-account counterpart transactions.

When a user withdraws cash (e.g. an ATM transaction on a bank account)
or lodges cash into an account, the Cash account itself has no
statement to upload. This service bridges that gap by creating mirror
transactions on the Cash account derived from selected source
transactions.

The generated transaction copies the date, description, party, and
flags from the source, negates the amount, and records a link back to
the source via ``source_transaction_id``.

Each generation batch is grouped under a synthetic ``uploads`` record
(``file_type='generated'``) so the existing upload-based bookkeeping
remains consistent.

Typical usage::

    service = CashTransactionService()
    result = service.generate_cash_transactions([101, 102, 103])
    print(result['created_count'])
"""

import json
from datetime import datetime
from typing import List, Dict, Any

from src.database.connection import get_manager, DatabaseError
from src.database.repositories.accounts import AccountRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class CashTransactionService:
    """Generates cash-account counterpart transactions.

    Coordinates across the ``accounts``, ``uploads``, and
    ``transactions`` tables inside a single database transaction to
    ensure atomicity.

    Attributes:
        db: The ``ConnectionManager`` used for database access.
        account_repo: ``AccountRepository`` for Cash account lookup.
    """

    def __init__(self):
        """Initialise the service.

        Must be called after ``connection.init()`` or
        ``connection.init_app()``.
        """
        self.db = get_manager()
        self.account_repo = AccountRepository()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_cash_transactions(
        self,
        source_transaction_ids: List[int],
    ) -> Dict[str, Any]:
        """Create cash counterpart transactions for the given sources.

        For each source transaction the method:

        1. Verifies the source exists and is **not** already on the
           Cash account (rejects those).
        2. Checks that no counterpart has already been generated
           (skips duplicates).
        3. Creates a new transaction on the Cash account with the
           amount negated and all other descriptive fields copied.

        All inserts happen inside a single DB transaction. A synthetic
        ``uploads`` row groups the batch.

        Args:
            source_transaction_ids: IDs of existing transactions to
                mirror onto the Cash account.

        Returns:
            A result dict::

                {
                    "created_count": int,
                    "skipped_count": int,
                    "rejected_count": int,
                    "upload_id": int | None,
                    "transactions": [<created row dicts>],
                    "skipped_ids": [int],
                    "rejected_ids": [int],
                }

        Raises:
            ValueError: If *source_transaction_ids* is empty or
                contains IDs that do not exist.
            DatabaseError: On any underlying database failure.
        """
        if not source_transaction_ids:
            raise ValueError("No transaction IDs provided")

        # De-duplicate while preserving order
        seen = set()
        unique_ids = []
        for tid in source_transaction_ids:
            if tid not in seen:
                seen.add(tid)
                unique_ids.append(tid)
        source_transaction_ids = unique_ids

        cash_account = self.account_repo.ensure_cash_account()
        cash_account_id = cash_account["id"]

        created: List[Dict[str, Any]] = []
        skipped_ids: List[int] = []
        rejected_ids: List[int] = []

        # TODO: Can we make the try blocks more targeted and specific?
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # ---- fetch source transactions ----
                placeholders = ",".join("?" * len(source_transaction_ids))
                cursor.execute(
                    f"SELECT * FROM transactions WHERE id IN ({placeholders})",
                    source_transaction_ids,
                )
                source_transactions = {
                    row["id"]: dict(row) for row in cursor.fetchall()
                }
                # TODO: Why not just use the seen set from above instead of repeatedly converting to a set here?
                missing_ids = (
                    set(source_transaction_ids) - source_transactions.keys()
                )
                if missing_ids:
                    raise ValueError(
                        f"Transactions not found: {sorted(missing_ids)}"
                    )

                # ---- find existing counterparts ----
                cursor.execute(
                    f"""SELECT source_transaction_id
                        FROM transactions
                        WHERE source_transaction_id IN ({placeholders})""",
                    source_transaction_ids,
                )
                already_generated = {
                    row["source_transaction_id"] for row in cursor.fetchall()
                }

                # ---- categorise ----
                to_generate = []
                for tid in source_transaction_ids:
                    txn = source_transactions[tid]
                    if txn["account_id"] == cash_account_id:
                        rejected_ids.append(tid)
                    elif tid in already_generated:
                        skipped_ids.append(tid)
                    else:
                        to_generate.append(txn)

                if not to_generate:
                    logger.info(
                        f"Nothing to generate: "
                        f"{len(skipped_ids)} skipped, "
                        f"{len(rejected_ids)} rejected"
                    )
                    return self._build_result(
                        created, skipped_ids, rejected_ids, upload_id=None
                    )

                # ---- synthetic upload record ----
                upload_id = self._create_synthetic_upload(
                    cursor, len(to_generate)
                )

                # ---- insert counterparts ----
                params = [
                    (
                        txn["transaction_date"],
                        -txn["amount"],
                        txn["description"],
                        txn["cleaned_description"],
                        txn["is_credit"],
                        txn["is_kids"],
                        txn["is_one_off"],
                        cash_account_id,
                        upload_id,
                        txn["party_id"],
                        txn["id"],
                    )
                    for txn in to_generate
                ]

                cursor.executemany(
                    """INSERT INTO transactions
                       (transaction_date, amount, description,
                        cleaned_description, is_credit, is_kids,
                        is_one_off, account_id, upload_id,
                        party_id, source_transaction_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    params,
                )

                # ---- fetch created rows via the batch's upload_id ----
                cursor.execute(
                    """SELECT * FROM transactions
                       WHERE upload_id = ?
                       ORDER BY id""",
                    (upload_id,),
                )
                created = [dict(row) for row in cursor.fetchall()]

            logger.info(
                f"Generated {len(created)} cash transactions "
                f"(skipped={len(skipped_ids)}, "
                f"rejected={len(rejected_ids)}, "
                f"upload_id={upload_id})"
            )
            return self._build_result(
                created, skipped_ids, rejected_ids, upload_id
            )

        except ValueError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate cash transactions: {e}")
            raise DatabaseError(
                f"Failed to generate cash transactions: {e}"
            ) from e

    # ------------------------------------------------------------------
    # Generate from a receipt
    # ------------------------------------------------------------------

    def generate_cash_transaction_from_receipt(
        self,
        receipt_id: int,
        party_id: int,
        is_withdrawal: bool = True,
        is_credit: bool = False,
        is_kids: bool = False,
        is_one_off: bool = False,
    ) -> Dict[str, Any]:
        """Create a single Cash-account transaction from a receipt.

        ...

        Args:
            receipt_id: ID of a **confirmed** receipt (must have
                ``vendor``, ``date``, and ``amount`` populated).
            party_id: Party to assign to the new transaction.
            is_withdrawal: When True (default) the amount is stored
                negative (cash going out); when False it is stored
                positive (cash coming in).
            is_credit: Value for the transaction's ``is_credit`` flag
                (currently used to mean "is income"). Defaults False.
            is_kids: Value for the transaction's ``is_kids`` flag.
                Defaults False.
            is_one_off: Value for the transaction's ``is_one_off`` flag.
                Defaults False.
        ...
        """
        cash_account = self.account_repo.ensure_cash_account()
        cash_account_id = cash_account["id"]

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # ---- load + validate the receipt ----
                cursor.execute(
                    "SELECT * FROM receipts WHERE id = ?",
                    (receipt_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"Receipt {receipt_id} not found")
                receipt = dict(row)

                missing = [
                    f for f in ("vendor", "date", "amount")
                    if receipt.get(f) in (None, "")
                ]
                if missing:
                    raise ValueError(
                        f"Receipt {receipt_id} is missing required "
                        f"field(s): {', '.join(missing)}"
                    )

                # ---- reject if already linked ----
                cursor.execute(
                    "SELECT id FROM transactions WHERE receipt_id = ? LIMIT 1",
                    (receipt_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    raise ValueError(
                        f"Receipt {receipt_id} is already linked to "
                        f"transaction {existing['id']}"
                    )

                # ---- synthetic upload record (per-receipt) ----
                original_filename = (
                    receipt.get("original_filename")
                    or receipt.get("stored_filename")
                    or f"receipt_{receipt_id}"
                )
                cursor.execute(
                    """INSERT INTO uploads
                       (original_filename, filename, file_type,
                        row_count, column_count, columns)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        original_filename,
                        original_filename,
                        "generated",
                        1,
                        0,
                        json.dumps([]),
                    ),
                )
                upload_id = cursor.lastrowid

                # ---- insert the transaction ----
                amount = abs(float(receipt["amount"]))
                if is_withdrawal:
                    amount = -amount

                cursor.execute(
                    """INSERT INTO transactions
                    (transaction_date, amount, description,
                        cleaned_description, is_credit, is_kids,
                        is_one_off, account_id, upload_id,
                        party_id, receipt_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        receipt["date"],
                        amount,
                        receipt["vendor"],
                        receipt["vendor"],
                        1 if is_credit  else 0,
                        1 if is_kids    else 0,
                        1 if is_one_off else 0,
                        cash_account_id,
                        upload_id,
                        party_id,
                        receipt_id,
                    ),
                )
                new_id = cursor.lastrowid
                cursor.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (new_id,),
                )
                transaction = dict(cursor.fetchone())

                logger.info(
                    f"Generated cash transaction {transaction['id']} "
                    f"from receipt {receipt_id} "
                    f"(party_id={party_id}, is_withdrawal={is_withdrawal}, "
                    f"is_credit={is_credit}, is_kids={is_kids}, "
                    f"is_one_off={is_one_off}, upload_id={upload_id})"
                )
            return {"transaction": transaction, "upload_id": upload_id}

        except ValueError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to generate cash transaction from receipt "
                f"{receipt_id}: {e}"
            )
            raise DatabaseError(
                f"Failed to generate cash transaction from receipt: {e}"
            ) from e

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_synthetic_upload(cursor, row_count: int) -> int:
        """Insert a synthetic upload record for a generation batch.

        Args:
            cursor: Active database cursor (inside a transaction).
            row_count: Number of transactions being generated.

        Returns:
            The ``id`` of the new uploads row.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"cash_generation_{timestamp}"

        cursor.execute(
            """INSERT INTO uploads
               (original_filename, filename, file_type,
                row_count, column_count, columns)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                filename,
                filename,
                "generated",
                row_count,
                0,
                json.dumps([]),
            ),
        )
        return cursor.lastrowid

    @staticmethod
    def _build_result(
        created: List[Dict[str, Any]],
        skipped_ids: List[int],
        rejected_ids: List[int],
        upload_id: int | None,
    ) -> Dict[str, Any]:
        """Assemble the standard result dict."""
        return {
            "created_count": len(created),
            "skipped_count": len(skipped_ids),
            "rejected_count": len(rejected_ids),
            "upload_id": upload_id,
            "transactions": created,
            "skipped_ids": skipped_ids,
            "rejected_ids": rejected_ids,
        }