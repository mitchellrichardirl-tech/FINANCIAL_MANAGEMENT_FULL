import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from src.config import load_settings
from src.api.middleware.error_handlers import register_error_handlers
from src.api.scheduler import init_scheduler
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


def create_app(config=None):
    """
    Create and configure the Flask application.

    Args:
        config: Configuration dictionary or object

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    settings = load_settings()
    settings.log_summary()

    app.config.update(
        # File upload settings
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50MB max file size
        ALLOWED_EXTENSIONS={
            "png",
            "jpg",
            "jpeg",
            "pdf",
            "csv",
            "xlsx",
            "xls",
            "tsv",
            "txt",
        },
        JSON_SORT_KEYS=False,
        **settings.to_flask_config(),
    )

    if config:
        logger.info(f"Applying config overrides: {list(config.keys())}")
        app.config.update(config)
        _validate_receipt_match_config(app)

    os.makedirs(app.config["DATA_DIR"], exist_ok=True)

    logger.debug(
        f"Config: upload_folder={app.config['UPLOAD_FOLDER']}, "
        f"db_path={app.config['DATABASE_PATH']}, "
        f"max_content_length={app.config['MAX_CONTENT_LENGTH']}, "
        f"allowed_extensions={app.config['ALLOWED_EXTENSIONS']}, "
        f"max_workers={app.config['MAX_WORKERS']}, "
        f"receipt_match_date_tolerance_days={app.config['RECEIPT_MATCH_DATE_TOLERANCE_DAYS']}, "
        f"receipt_match_amount_tolerance={app.config['RECEIPT_MATCH_AMOUNT_TOLERANCE']}, "
        f"receipt_auto_link_threshold={app.config['RECEIPT_AUTO_LINK_THRESHOLD']}"
    )

    # Enable CORS
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
    )
    logger.debug("CORS configured for /api/*")

    # Initialize database
    _init_database(app)

    # Register blueprints
    _register_blueprints(app)

    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        logger.debug(f"{rule.rule:50s} {sorted(rule.methods)}")
        
    # Register error handlers
    register_error_handlers(app)
    logger.debug("Error handlers registered")

    # Create upload folder
    upload_folder = app.config["UPLOAD_FOLDER"]
    created = not os.path.exists(upload_folder)
    os.makedirs(upload_folder, exist_ok=True)
    if created:
        logger.info(f"Created upload folder: {upload_folder}")

    # Initialize background scheduler (skip in reloader subprocess)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        init_scheduler(app)
        logger.info("Background scheduler initialized")
    else:
        logger.debug("Skipping scheduler init (reloader parent process)")

    logger.info("Application initialized successfully")

    return app


def _register_blueprints(app):
    """Register all route blueprints."""
    from src.api.routes import (
        health,
        receipts,
        tabular_files,
        accounts,
        categories,
        transactions,
        uploads,
        statement_format,
        hierarchy,
    )

    blueprints = [
        (health.bp, "/api"),
        (receipts.bp, "/api"),
        (tabular_files.bp, "/api/tabular"),
        (accounts.bp, "/api/accounts"),
        (categories.bp, "/api"),
        (transactions.bp, "/api/transactions"),
        (uploads.bp, "/api/uploads"),
        (statement_format.bp, "/api/statement-formats"),
        (hierarchy.bp, "/api/hierarchy"),
    ]

    for blueprint, prefix in blueprints:
        app.register_blueprint(blueprint, url_prefix=prefix)
        logger.debug(f"Registered blueprint: {blueprint.name} -> {prefix}")

    logger.info(f"Registered {len(blueprints)} blueprints")

def _validate_receipt_match_config(app):
    """Fail fast on nonsensical receipt-matching settings."""
    days = app.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"]
    if not isinstance(days, int) or days < 0:
        raise ValueError(
            f"RECEIPT_MATCH_DATE_TOLERANCE_DAYS must be a non-negative integer, got {days!r}"
        )
    amount = app.config["RECEIPT_MATCH_AMOUNT_TOLERANCE"]
    if amount < 0:
        raise ValueError(
            f"RECEIPT_MATCH_AMOUNT_TOLERANCE must be non-negative, got {amount!r}"
        )
    threshold = app.config["RECEIPT_AUTO_LINK_THRESHOLD"]
    if not 0.0 <= threshold <= 1.01:
        raise ValueError(
            f"RECEIPT_AUTO_LINK_THRESHOLD must be in [0, 1.01], got {threshold!r}"
        )

def _init_database(app):
    """Initialize database for the application."""
    from src.database import connection as db

    logger.debug(f"Initializing database: {app.config['DATABASE_PATH']}")

    manager = db.init_app(app)

    logger.info(f"Database initialized: {manager.db_path}")