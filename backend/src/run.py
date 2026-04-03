import os
import logging

from flask import send_from_directory

from src.api.app import create_app
from src.utils.logging import ContextLogger

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')

# Configure logging
ContextLogger.setup_logging()

logger = ContextLogger(__name__)

# Create the application
app = create_app()

@app.route('/docs/api/', defaults={'path': 'index.html'})
@app.route('/docs/api/<path:path>')
def api_docs(path):
    return send_from_directory(DOCS_DIR, path)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting application on port {port}, debug={debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )