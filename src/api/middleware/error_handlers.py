from flask import jsonify
from werkzeug.exceptions import HTTPException
import logging

from src.utils.tabular_files.exceptions import TabularProcessorError

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers with the Flask app."""
    
    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 errors."""
        return jsonify({
            'success': False,
            'error': 'Resource not found'
        }), 404
    
    @app.errorhandler(413)
    def file_too_large(e):
        """Handle file size errors."""
        return jsonify({
            'success': False,
            'error': 'File too large. Maximum size is 50MB.'
        }), 413
    
    @app.errorhandler(500)
    def internal_error(e):
        """Handle 500 errors."""
        logger.exception('Internal server error')
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
    
    @app.errorhandler(TabularProcessorError)
    def handle_tabular_error(e):
        """Handle tabular processing errors."""
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle HTTP exceptions."""
        return jsonify({
            'success': False,
            'error': e.description
        }), e.code
    
    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        """Handle unexpected exceptions."""
        logger.exception('Unexpected error')
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500