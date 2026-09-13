"""
Single writer for receipt <-> transaction link state.
Invariant maintained by every method here, and nowhere else:
    receipt_links row exists
        <=> transactions.receipt_id is set
        <=> receipts.status == 'linked'
Nothing outside this service may write receipt_links, receipts.status,
receipts.confirmed_at, or transactions.receipt_id.
Cardinality note: links are 1:1 today, enforced by unique indexes
(uq_receipt_links_receipt_id / uq_receipt_links_transaction_id). When split
receipts land, relax the index and extend VALID_LINK_SOURCES - the service
API is deliberately shaped so callers never assume a single link.
"""

from src.api.utils.errors import conflict, invalid_value, not_found, required
from src.database import connection as db
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)
VALID_LINK_SOURCES = {"manual", "auto", "import"}
_NOW = "strftime('%Y-%m-%d %H:%M:%f', 'now')"


class ReceiptLinkService:
    """Links, unlinks, and confirms receipts. All writes are transactional."""

    def __init__(self, manager=None):
        self._manager = manager

    @property
    def db(self):
        return self._manager or db.get_manager()

    # ── Public API ────────────────────────────────────────────────────
    def link(
        self, receipt_id: int, transaction_id: int, source: str = "manual"
    ) -> dict:
        """Link a receipt to a live transaction.
        Raises:
            AppError(NOT_FOUND): receipt missing, or transaction missing /
                soft-deleted.
            AppError(CONFLICT): either side is already linked.
            AppError(INVALID_VALUE): unknown link source.
        """
        if source not in VALID_LINK_SOURCES:
            raise invalid_value(
                f"Unknown link source {source!r}. "
                f"Must be one of: {', '.join(sorted(VALID_LINK_SOURCES))}",
                field="source",
            )
        with self.db.transaction() as conn:
            self._get_receipt(conn, receipt_id)
            existing = self._link_for_receipt(conn, receipt_id)
            if existing:
                raise conflict(
                    "Receipt",
                    f"Receipt {receipt_id} is already linked to "
                    f"transaction {existing['transaction_id']}",
                    transaction_id=existing["transaction_id"],
                )
            txn = self._get_transaction(conn, transaction_id)
            if txn["deleted_at"] is not None:
                raise not_found("Transaction", transaction_id)
            existing = self._link_for_transaction(conn, transaction_id)
            if existing is None and txn["receipt_id"] is not None:
                # Legacy mirror-only link (pre-migration data written after
                # backfill, or a bug). Respect it rather than overwrite.
                existing = {"receipt_id": txn["receipt_id"]}
            if existing:
                raise conflict(
                    "Transaction",
                    f"Transaction {transaction_id} is already linked to "
                    f"receipt {existing['receipt_id']}",
                    receipt_id=existing["receipt_id"],
                )
            conn.execute(
                "INSERT INTO receipt_links (receipt_id, transaction_id, link_source) "
                "VALUES (?, ?, ?)",
                (receipt_id, transaction_id, source),
            )
            conn.execute(
                "UPDATE transactions SET receipt_id = ? WHERE id = ?",
                (receipt_id, transaction_id),
            )
            self._mark_receipt_linked(conn, receipt_id)
            logger.info(
                f"Linked receipt {receipt_id} to transaction {transaction_id} "
                f"(source={source})"
            )
            return {
                "receipt": self._get_receipt(conn, receipt_id),
                "transaction": self._get_transaction(conn, transaction_id),
            }

    def unlink_receipt(self, receipt_id: int) -> dict:
        """Remove a receipt's link, returning it to 'unlinked'.
        No-op if the receipt is not linked (idempotent - safe for UI retries).
        Raises:
            AppError(NOT_FOUND): receipt missing.
        """
        with self.db.transaction() as conn:
            self._get_receipt(conn, receipt_id)
            link = self._link_for_receipt(conn, receipt_id)
            if link is None:
                logger.debug(f"unlink_receipt({receipt_id}): no link, no-op")
                return {
                    "receipt": self._get_receipt(conn, receipt_id),
                    "transaction": None,
                }
            transaction_id = link["transaction_id"]
            self._remove_link(conn, receipt_id, transaction_id)
            logger.info(
                f"Unlinked receipt {receipt_id} from transaction {transaction_id}"
            )
            return {
                "receipt": self._get_receipt(conn, receipt_id),
                "transaction": self._get_transaction(conn, transaction_id),
            }

    def unlink_transaction(self, transaction_id: int) -> dict:
        """Remove a transaction's link, returning the receipt to 'unlinked'.
        Works on soft-deleted transactions (explicit "release receipt"
        actions). No-op if not linked. Not called automatically by any
        delete path - deleted transactions keep their receipts.
        Raises:
            AppError(NOT_FOUND): transaction missing.
        """
        with self.db.transaction() as conn:
            self._get_transaction(conn, transaction_id)
            link = self._link_for_transaction(conn, transaction_id)
            if link is None:
                # Clear any stale mirror value even without a link row.
                conn.execute(
                    "UPDATE transactions SET receipt_id = NULL WHERE id = ?",
                    (transaction_id,),
                )
                logger.debug(f"unlink_transaction({transaction_id}): no link, no-op")
                return {
                    "receipt": None,
                    "transaction": self._get_transaction(conn, transaction_id),
                }
            receipt_id = link["receipt_id"]
            self._remove_link(conn, receipt_id, transaction_id)
            logger.info(
                f"Unlinked transaction {transaction_id} from receipt {receipt_id}"
            )
            return {
                "receipt": self._get_receipt(conn, receipt_id),
                "transaction": self._get_transaction(conn, transaction_id),
            }

    def confirm(
        self,
        receipt_id: int,
        vendor=None,
        amount=None,
        date=None,
        confidence=None,
        raw_text=None,
    ) -> dict:
        """Persist user-reviewed fields; promote 'pending' to 'unlinked'.
        A 'linked' receipt keeps its status - fields remain editable but
        there is no path back to 'pending'.
        Raises:
            AppError(NOT_FOUND): receipt missing.
            AppError(REQUIRED_FIELD): no vendor when leaving 'pending'.
        """
        with self.db.transaction() as conn:
            receipt = self._get_receipt(conn, receipt_id)
            if receipt["status"] == "pending" and not (vendor and str(vendor).strip()):
                raise required("vendor")
            updates, params = [], []
            for column, value in (
                ("vendor", vendor),
                ("amount", amount),
                ("date", date),
                ("confidence", confidence),
                ("raw_text", raw_text),
            ):
                if value is not None:
                    updates.append(f"{column} = ?")
                    params.append(value)
            if receipt["status"] == "pending":
                updates.append("status = 'unlinked'")
                updates.append(f"confirmed_at = {_NOW}")
            if updates:
                params.append(receipt_id)
                conn.execute(
                    f"UPDATE receipts SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
            logger.info(f"Confirmed receipt {receipt_id}")
            return self._get_receipt(conn, receipt_id)

    # ── Internals ─────────────────────────────────────────────────────
    def _get_receipt(self, conn, receipt_id) -> dict:
        row = conn.execute(
            "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
        if row is None:
            raise not_found("Receipt", receipt_id)
        return dict(row)

    def _get_transaction(self, conn, transaction_id) -> dict:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if row is None:
            raise not_found("Transaction", transaction_id)
        return dict(row)

    def _link_for_receipt(self, conn, receipt_id):
        row = conn.execute(
            "SELECT * FROM receipt_links WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()
        return dict(row) if row else None

    def _link_for_transaction(self, conn, transaction_id):
        row = conn.execute(
            "SELECT * FROM receipt_links WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
        return dict(row) if row else None

    def _remove_link(self, conn, receipt_id, transaction_id):
        conn.execute(
            "DELETE FROM receipt_links WHERE receipt_id = ? AND transaction_id = ?",
            (receipt_id, transaction_id),
        )
        conn.execute(
            "UPDATE transactions SET receipt_id = NULL WHERE id = ?",
            (transaction_id,),
        )
        conn.execute(
            "UPDATE receipts SET status = 'unlinked' WHERE id = ?",
            (receipt_id,),
        )

    def _mark_receipt_linked(self, conn, receipt_id):
        # Separate method: the final write in link(), patchable in tests to
        # verify the whole operation rolls back atomically.
        conn.execute(
            f"UPDATE receipts SET status = 'linked', "
            f"confirmed_at = COALESCE(confirmed_at, {_NOW}) "
            f"WHERE id = ?",
            (receipt_id,),
        )
