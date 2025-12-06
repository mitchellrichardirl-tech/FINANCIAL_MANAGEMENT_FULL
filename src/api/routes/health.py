from flask import Blueprint, jsonify
import sys

bp = Blueprint('health', __name__)


@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'python_version': sys.version
    })


@bp.route('/status', methods=['GET'])
def status():
    """Detailed status endpoint."""
    return jsonify({
        'status': 'operational',
        'services': {
            'receipts': 'available',
            'tabular_files': 'available'
        }
    })