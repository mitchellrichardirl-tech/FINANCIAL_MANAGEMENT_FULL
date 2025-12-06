import logging
import os
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

from .middleware.error_handlers import register_error_handlers
from .routes import health, receipts, tabular_files

logger = logging.getLogger(__name__)


def create_app(config=None):
    """
    Create and configure the Flask application.

    Args:
        config: Configuration dictionary or object

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    logger.info(f"Base directory: {BASE_DIR}")
    # Default configuration
    app.config.update(
        # File upload settings
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50MB max file size
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", "/tmp/uploads"),
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
        # Database settings
        DATABASE_PATH=os.getenv("DATABASE_PATH", str(Path(BASE_DIR, "data", "app.db"))),
        # JSON settings
        JSON_SORT_KEYS=False,
    )

    # Override with provided config
    if config:
        app.config.update(config)

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

    # Initialize database
    _init_database(app)
    logger.info(f"Database path: {app.config['DATABASE_PATH']}")

    # Register blueprints
    app.register_blueprint(health.bp, url_prefix="/api")
    app.register_blueprint(receipts.bp, url_prefix="/api")
    app.register_blueprint(tabular_files.bp, url_prefix="/api/tabular")

    # Register error handlers
    register_error_handlers(app)

    # Create upload folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    logger.info("Flask application created successfully")

    return app


def _init_database(app):
    """Initialize database for the application."""
    from src.database import connection as db

    manager = db.init_app(app)
    logger.info(f"Database manager initialized: {manager.db_path}")

    # Optionally run migrations or create tables
    # _run_migrations(app)
