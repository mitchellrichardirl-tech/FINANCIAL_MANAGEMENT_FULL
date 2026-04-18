from flask import Blueprint, jsonify
import sys

from src.utils.logging import ContextLogger, log_route

bp = Blueprint('health', __name__)
logger = ContextLogger(__name__)


@bp.route('/health', methods=['GET'])
@log_route(logger)
def health_check():
   """Health check endpoint."""
   return jsonify({
       'status': 'healthy',
       'version': '1.0.0',
       'python_version': sys.version
   })


@bp.route('/status', methods=['GET'])
@log_route(logger)
def status():
   """Detailed status endpoint."""
   return jsonify({
       'status': 'operational',
       'services': {
           'receipts': 'available',
           'tabular_files': 'available'
       }
   })