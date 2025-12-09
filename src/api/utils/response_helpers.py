from flask import jsonify


def success_response(data=None, message=None, status_code=200):
    """
    Format a successful API response.
    
    Args:
        data: Response data (optional)
        message: Optional success message
        status_code: HTTP status code
        
    Returns:
        Flask JSON response
    """
    response = {'success': True}
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    return jsonify(response), status_code


def error_response(message, errors=None, status_code=400):
    """
    Format an error API response.
    
    Args:
        message: Error message
        errors: Optional list of detailed errors
        status_code: HTTP status code
        
    Returns:
        Flask JSON response
    """
    response = {
        'success': False,
        'error': message
    }
    
    if errors:
        response['errors'] = errors
    
    return jsonify(response), status_code