# src/api/blueprints/statement_formats.py

from flask import Blueprint, request

from src.api.utils.response_helpers import success_response
from src.api.utils.route_helpers import handle_errors
from src.api.utils.errors import invalid_value

from src.statements.base import (
    StatementConfig,
    ConfigurableStatementProcessor,
)
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger, log_route

bp = Blueprint('statement_formats', __name__)
logger = ContextLogger(__name__)


# Cap on how many rows we'll run through the pipeline in a preview call.
# High enough to surface real data issues, low enough that the wizard
# stays snappy when the user iterates on the config.
PREVIEW_MAX_INPUT_ROWS = 200

# Cap on how many parsed rows we return to the client. The pipeline may
# drop rows (exclude_patterns, unparseable dates), so this is applied
# after processing.
PREVIEW_MAX_OUTPUT_ROWS = 50


@bp.route('/preview', methods=['POST'])
@handle_errors(entity='StatementFormat')
@log_route(logger)
def preview_format():
    """Run a draft config against sample rows without persisting anything.

    Body:
        {
            "config": {...},     # StatementConfig.to_dict() shape
            "rows":   [{...}],   # raw rows as returned by /files/preview
        }

    Returns:
        {
            "total_parsed": int,
            "preview_rows": [...],  # capped at PREVIEW_MAX_OUTPUT_ROWS
            "warnings":     [...],  # ProcessingWarning.to_dict() list
        }

    Raises (via handle_errors):
        AppError (INVALID_VALUE, 400):  Malformed request body.
        AppError (INVALID_FORMAT, 422): Config validation failed, or the
            processing pipeline rejected the rows (e.g. no columns
            matched, no dates parseable). The `details` dict carries
            structured info for the ColumnMismatchPanel.
    """
    body = request.get_json(silent=True) or {}
    config_dict = body.get('config')
    rows = body.get('rows')

    if not isinstance(config_dict, dict):
        raise invalid_value("Request body must contain a 'config' object.")
    if not isinstance(rows, list):
        raise invalid_value("Request body must contain a 'rows' array.")

    if len(rows) > PREVIEW_MAX_INPUT_ROWS:
        logger.debug(
            f"Truncating preview input from {len(rows)} to "
            f"{PREVIEW_MAX_INPUT_ROWS} rows"
        )
        rows = rows[:PREVIEW_MAX_INPUT_ROWS]

    # StatementConfig.__post_init__ does shape + defaults validation.
    # Translate ValueError into a structured AppError so the UI can
    # point at the offending field.
    try:
        config = StatementConfig.from_dict(config_dict)
    except (ValueError, TypeError) as e:
        raise invalid_value(f"Invalid statement config: {e}")

    logger.info(
        f"Previewing config {config.display_name!r} against {len(rows)} rows"
    )

    # Dummy ids — nothing is persisted. A real categorizer is used so
    # the preview reflects what the user would actually get.
    processor = ConfigurableStatementProcessor(
        statement_config=config,
        account_id=-1,
        upload_id=-1,
        categorizer=TransactionCategorizer(),
    )

    # AppError raised here (missing columns, unparseable dates, etc.)
    # propagates to handle_errors with its full details dict intact.
    transactions_df = processor.process_statement(rows)

    preview_rows = (
        transactions_df.head(PREVIEW_MAX_OUTPUT_ROWS)
        .to_dict(orient='records')
    )

    logger.info(
        f"Preview complete: {len(transactions_df)} parsed, "
        f"{len(processor.warnings)} warning(s)"
    )

    return success_response({
        'total_parsed': int(len(transactions_df)),
        'preview_rows': preview_rows,
        'warnings': [w.to_dict() for w in processor.warnings],
    })