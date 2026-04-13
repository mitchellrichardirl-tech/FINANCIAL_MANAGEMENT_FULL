"""
Statement format registry and processor factory.

Unified entry point for resolving statement formats from any source
(built-in Python configs or user-defined DB rows) and building the
appropriate processor for them. Callers should use `get_processor()`
or `StatementFormatRegistry.get()` rather than importing configs
or processors directly.

Two sources of formats:
  - **Built-in**: `StatementConfig` instances defined in code under
    `src.statements.configs`. Read-only from the UI's perspective,
    may have an associated custom `StatementProcessor` subclass.
  - **User-defined**: rows in the `statement_formats` table, created
    and edited through the frontend. Always use the default
    `ConfigurableStatementProcessor`.

Formats are addressed by a tagged identifier string:
    "builtin:ptsb_current"  → built-in config keyed "ptsb_current"
    "user:42"               → user config with DB id 42

The registry performs no caching — user configs are queried on every
`get()` call. This is deliberate: the access pattern is low volume
(one lookup per upload), and the cost of cache invalidation bugs
outweighs the microseconds saved.

Typical usage:
    registry = StatementFormatRegistry()
    handle = registry.get("user:42")
    # or via the factory:
    processor = get_processor("builtin:ptsb_current", account_id=1, upload_id=99)
"""

from dataclasses import dataclass
from typing import Optional, Type

from src.statements.base import (
    StatementConfig,
    StatementProcessor,
    ConfigurableStatementProcessor,
)
from src.statements.configs import STATEMENT_CONFIGS
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.api.utils.errors import AppError, ErrorCode
from src.utils.logging import ContextLogger

from src.database.connection import RecordNotFound
from src.database.repositories.statement_format import StatementFormatRepository

logger = ContextLogger(__name__)


# Built-in formats whose parsing can't be expressed declaratively and
# require a custom `StatementProcessor` subclass. Keyed by the same
# string key used in `STATEMENT_CONFIGS`. User-defined formats can
# never have a custom processor — the UI only produces configs.
CUSTOM_PROCESSORS: dict[str, Type[StatementProcessor]] = {
    # 'revolut_current': RevolutStatementProcessor,
}


@dataclass(frozen=True)
class FormatHandle:
    """Resolved statement format ready to be turned into a processor.

    Bundles a `StatementConfig` with the metadata the factory needs
    to decide which processor class to instantiate. Returned by
    `StatementFormatRegistry.get()`.

    Attributes:
        identifier: Tagged identifier this handle was resolved from
            (e.g. `"builtin:ptsb_current"`, `"user:42"`). Safe to
            round-trip back through `get()`.
        source: Either `"builtin"` or `"user"`. Determines whether
            the format is editable through the UI.
        config: The `StatementConfig` describing how to parse
            statements in this format.
        custom_processor_cls: Optional custom `StatementProcessor`
            subclass to use instead of `ConfigurableStatementProcessor`.
            Only ever populated for built-in formats — user configs
            always use the default processor.
    """
    identifier: str
    source: str
    config: StatementConfig
    custom_processor_cls: Optional[Type[StatementProcessor]] = None

    @property
    def editable(self) -> bool:
        """True if this format can be edited or deleted through the UI.

        Built-in formats are defined in code and are always read-only;
        user formats live in the DB and are always editable.
        """
        return self.source == "user"


class StatementFormatRegistry:
    """Unified lookup for built-in and user-defined statement formats.

    Built-ins are loaded from `src.statements.configs` at import time
    and never change for the life of the process. User configs live in
    the `statement_formats` table and are queried on demand — no
    caching, because the access pattern is low-volume and the cost of
    invalidation bugs outweighs the saved microseconds.

    Identifiers are tagged strings that encode the format's source:
      * `"builtin:<key>"` — a built-in config from `STATEMENT_CONFIGS`
      * `"user:<id>"`     — a user config from the DB

    For backwards compatibility `get()` also accepts a bare built-in
    key (e.g. `"ptsb_current"`), logging a hint when it does. New
    callers should always use the tagged form.

    All lookup failures raise `AppError` with an appropriate
    `ErrorCode` and HTTP status, so the API layer can surface them
    directly without additional translation.

    Attributes:
        BUILTIN_PREFIX: Prefix marking a built-in identifier.
        USER_PREFIX: Prefix marking a user-config identifier.
    """

    BUILTIN_PREFIX = "builtin:"
    USER_PREFIX = "user:"

    def __init__(
        self,
        statement_format_repo: Optional[StatementFormatRepository] = None,
        builtin_configs: Optional[dict[str, StatementConfig]] = None,
        custom_processors: Optional[dict[str, Type[StatementProcessor]]] = None,
    ):
        """Initialize the registry.

        All three dependencies are injectable for testing. In
        production code you can construct with no arguments and the
        module-level defaults are used.

        Args:
            statement_format_repo: Repository for DB-backed user
                configs. Defaults to a fresh `StatementFormatRepository`.
            builtin_configs: Mapping of built-in key → `StatementConfig`.
                Defaults to `STATEMENT_CONFIGS`.
            custom_processors: Mapping of built-in key → custom
                `StatementProcessor` subclass for formats that can't be
                handled declaratively. Defaults to `CUSTOM_PROCESSORS`.
        """
        self._repo = statement_format_repo or StatementFormatRepository()
        self._builtin = builtin_configs or STATEMENT_CONFIGS
        self._custom = custom_processors or CUSTOM_PROCESSORS

    # ---------- lookup ----------

    def get(self, identifier: str) -> FormatHandle:
        """Resolve a tagged identifier to a `FormatHandle`.

        Accepts three forms:
          * `"builtin:<key>"` — explicit built-in lookup
          * `"user:<id>"`     — user-config lookup by DB id
          * `"<key>"`         — bare built-in key (back-compat; logged)

        Args:
            identifier: One of the tagged identifier forms above.

        Returns:
            A `FormatHandle` bundling the resolved config with the
            metadata needed by the processor factory.

        Raises:
            AppError (NOT_FOUND): The identifier doesn't match any
                built-in key or user config row.
            AppError (INVALID_FORMAT): A user config was found but its
                stored JSON is malformed or no longer conforms to the
                current `StatementConfig` schema.
        """
        if identifier.startswith(self.BUILTIN_PREFIX):
            return self._get_builtin(identifier[len(self.BUILTIN_PREFIX):])
        if identifier.startswith(self.USER_PREFIX):
            return self._get_user(int(identifier[len(self.USER_PREFIX):]))

        # Back-compat: bare key = built-in
        if identifier in self._builtin:
            logger.debug(
                f"Resolving bare key {identifier!r} as built-in "
                f"(consider using '{self.BUILTIN_PREFIX}{identifier}')"
            )
            return self._get_builtin(identifier)

        raise AppError(
            code=ErrorCode.NOT_FOUND,
            message=f"Unknown statement format: '{identifier}'.",
            status_code=404,
            entity="StatementFormat",
        )

    def _get_builtin(self, key: str) -> FormatHandle:
        """Look up a built-in config by its registry key.

        Args:
            key: The unprefixed key (e.g. `"ptsb_current"`).

        Returns:
            A `FormatHandle` with `source="builtin"` and
            `custom_processor_cls` populated if the key is registered
            in `CUSTOM_PROCESSORS`.

        Raises:
            AppError (NOT_FOUND): No built-in config is registered
                under this key. The error message lists all available
                keys to aid debugging.
        """
        if key not in self._builtin:
            available = ", ".join(sorted(self._builtin))
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                message=(
                    f"Unknown built-in statement format: '{key}'. "
                    f"Available: {available}."
                ),
                status_code=404,
                entity="StatementFormat",
            )
        return FormatHandle(
            identifier=f"{self.BUILTIN_PREFIX}{key}",
            source="builtin",
            config=self._builtin[key],
            custom_processor_cls=self._custom.get(key),
        )

    def _get_user(self, format_id: int) -> FormatHandle:
        """Look up a user-defined config by its database id.

        Loads the row, validates that the stored JSON is well-formed,
        and reconstructs the `StatementConfig` via `from_dict()`. A
        stored config that no longer validates against the current
        schema is treated as a 500 — the DB is in an inconsistent
        state that the user can't fix through the UI.

        Args:
            format_id: Primary key of the row in `statement_formats`.

        Returns:
            A `FormatHandle` with `source="user"`.

        Raises:
            AppError (NOT_FOUND, 404): No row exists with this id.
            AppError (INVALID_FORMAT, 500): Row exists but its
                `config_json` is malformed JSON, or the reconstructed
                config fails `StatementConfig` validation (e.g. after
                a breaking schema change).
        """
        try:
            row = self._repo.get_format_by_id(format_id)
        except RecordNotFound:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                message=f"Statement format {format_id} not found.",
                status_code=404,
                entity="StatementFormat",
            )

        if row["config_json"] is None:
            raise AppError(
                code=ErrorCode.INVALID_FORMAT,
                message=f"Stored format {format_id} has malformed config_json.",
                status_code=500,
                entity="StatementFormat",
            )

        try:
            config = StatementConfig.from_dict(row["config_json"])
        except (ValueError, TypeError) as e:
            logger.exception(f"Stored config {format_id} failed to load")
            raise AppError(
                code=ErrorCode.INVALID_FORMAT,
                message=f"Stored format {format_id} is no longer valid: {e}",
                status_code=500,
                entity="StatementFormat",
            ) from e

        return FormatHandle(
            identifier=f"{self.USER_PREFIX}{format_id}",
            source="user",
            config=config,
        )

    # ---------- listing ----------

    def list_all(self) -> list[dict]:
        """Return metadata for every known format, built-in and user.

        Used by the API to populate the format picker in the UI.
        Built-ins are listed first in the order they appear in
        `STATEMENT_CONFIGS`; user formats follow in whatever order the
        repository returns them (currently bank name then account
        type).

        Unlike `get()`, this method is tolerant of malformed stored
        configs: a row with unparseable `config_json` or a config that
        fails validation is logged and skipped, so the listing
        endpoint never fails because of one bad row.

        Returns:
            List of dicts, each containing:
                - `identifier`: Tagged id usable with `get()`.
                - `source`: `"builtin"` or `"user"`.
                - `editable`: True iff the UI should allow editing.
                - `bank_name`: Human-readable bank name.
                - `account_type`: Account variant.
                - `display_name`: `"{bank_name} {account_type}"`.
                - `has_custom_processor`: True if this format uses a
                  `StatementProcessor` subclass rather than the default
                  configurable processor. Always False for user configs.
        """
        out: list[dict] = []

        for key, cfg in self._builtin.items():
            out.append({
                "identifier": f"{self.BUILTIN_PREFIX}{key}",
                "source": "builtin",
                "editable": False,
                "bank_name": cfg.bank_name,
                "account_type": cfg.account_type,
                "display_name": cfg.display_name,
                "has_custom_processor": key in self._custom,
            })

        for row in self._repo.get_all_formats():
            # List-view shouldn't blow up if one stored config is broken
            if row['config_json'] is None:
                logger.error(f"Skipping malformed stored format {row['id']}")
                continue
            try:
                cfg = StatementConfig.from_dict(row['config_json'])
                out.append({
                    "identifier": f"{self.USER_PREFIX}{row['id']}",
                    "source": "user",
                    "editable": True,
                    "bank_name": cfg.bank_name,
                    "account_type": cfg.account_type,
                    "display_name": cfg.display_name,
                    "has_custom_processor": False,
                })
            except Exception:
                logger.exception(f"Skipping malformed stored format {row['id']}")

        return out

    # ---------- collision check for the write side ----------

    def builtin_display_names(self) -> set[str]:
        """Return the `display_name` of every built-in format.

        Used by the create/update API handlers to reject user configs
        that would collide with a built-in — the `(bank_name,
        account_type)` UNIQUE constraint only prevents user-vs-user
        duplicates, so the built-in collision check has to live in
        application code.

        Returns:
            Set of display-name strings. Empty set if no built-ins are
            registered.
        """
        return {cfg.display_name for cfg in self._builtin.values()}
    
def get_processor(
    identifier: str,
    account_id: int,
    upload_id: int,
    registry: Optional[StatementFormatRegistry] = None,
    categorizer: Optional["TransactionCategorizer"] = None,
    **kwargs,
) -> StatementProcessor:
    """Build a processor for the given statement format identifier.

    The single entry point for obtaining a ready-to-run processor.
    Checks the registry for a matching format, dispatches to a custom
    `StatementProcessor` subclass if one is registered, and otherwise
    returns a `ConfigurableStatementProcessor` wrapping the config.

    Args:
        identifier: Tagged format identifier — see
            `StatementFormatRegistry.get()` for accepted forms.
        account_id: FK stamped on every produced transaction.
        upload_id: FK identifying the import batch.
        registry: Registry to look up through. Defaults to a fresh
            `StatementFormatRegistry()`; inject one for testing or to
            share built-in caches across calls.
        categorizer: Optional `TransactionCategorizer` to inject.
            Defaults to whatever the processor constructs internally.
        **kwargs: Forwarded to custom processor constructors only.
            Ignored when the default configurable processor is used.

    Returns:
        A ready-to-use `StatementProcessor` instance.

    Raises:
        AppError: Propagated from `StatementFormatRegistry.get()` — see
            that method for the specific error codes.
    """

    registry = registry or StatementFormatRegistry()
    handle = registry.get(identifier)

    if handle.custom_processor_cls is not None:
        logger.debug(
            f"Using custom processor: {handle.custom_processor_cls.__name__}"
        )
        return handle.custom_processor_cls(
            account_id=account_id,
            upload_id=upload_id,
            categorizer=categorizer,
            **kwargs,
        )

    logger.debug(
        f"Using configurable processor for: {handle.config.display_name}"
    )
    return ConfigurableStatementProcessor(
        statement_config=handle.config,
        account_id=account_id,
        upload_id=upload_id,
        categorizer=categorizer,
    )