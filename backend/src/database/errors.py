"""
Error classes for database operations
"""


class DatabaseError(Exception):
    """Raised when a database operation fails.

    Wraps lower-level `sqlite3.Error` exceptions and other failures
    (e.g. backup I/O errors) with a consistent exception type so callers
    can catch a single error class.
    """

    pass


class RecordNotFound(DatabaseError):
    """Requested record does not exist. Safe to map to HTTP 404."""
    def __init__(self, entity: str, **criteria):
        self.entity = entity
        self.criteria = criteria
        parts = ", ".join(f"{k}={v!r}" for k, v in criteria.items())
        super().__init__(f"{entity} not found: {parts}")


# --- Soft-delete reasons -------------------------------------------------
# Recorded in transactions.deleted_reason. NULL when the row is live.
DELETED_REASON_USER = 'user'              # user pressed Delete
DELETED_REASON_CASCADE = 'cascade'        # source transaction was deleted
DELETED_REASON_SUPERSEDED = 'superseded'  # replaced by its split children
DELETED_REASON_UNSPLIT = 'unsplit'        # discarded when a split was reversed

# --- Source relationships ------------------------------------------------
# Recorded in transactions.source_relationship on the *child* row.
SOURCE_GENERATED = 'generated'  # child coexists with parent (cash lodgement)
SOURCE_SPLIT = 'split'          # child replaces parent (split line item)

# Only deletions the user performed themselves can be undone directly.
RESTORABLE_REASONS = frozenset({DELETED_REASON_USER})

# SQL expression for "now", matching the format used by created_at.
_NOW = "strftime('%Y-%m-%d %H:%M:%f', 'now')"

# Explanations surfaced when a restore is rejected.
_RESTORE_HELP = {
    DELETED_REASON_CASCADE: (
        "it was deleted automatically when its source transaction was deleted. "
        "Restore the source transaction instead."
    ),
    DELETED_REASON_SUPERSEDED: (
        "it was replaced by its split children. Unsplit it instead."
    ),
    DELETED_REASON_UNSPLIT: (
        "it was discarded when its source transaction was unsplit. "
        "Re-split the source transaction instead."
    ),
}


class TransactionRuleError(Exception):
    """Raised when an operation would break a transaction relationship invariant.
    Deliberately not a subclass of `DatabaseError`: the database is fine,
    the request isn't. Map to HTTP 409 Conflict at the route layer.
    """
