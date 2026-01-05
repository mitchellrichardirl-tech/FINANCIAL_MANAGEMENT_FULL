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

def paginated_response(
    items: list,
    limit: int,
    offset: int,
    data_key: str = 'items',
    **extra_data
) -> tuple:
    """
    Build a paginated success response.
    
    Args:
        items: List of items to return
        limit: Page size limit
        offset: Pagination offset
        data_key: Key name for items in response
        extra_data: Additional data to include in response
    
    Returns:
        Flask JSON response tuple
    """
    response_data = {
        data_key: items,
        'pagination': {
            'limit': limit,
            'offset': offset,
            'count': len(items),
            'has_more': len(items) == limit
        }
    }
    response_data.update(extra_data)
    
    return success_response(data=response_data)

def search_response(
    results: list,
    search_params: dict,
    results_key: str = 'results'
) -> tuple:
    """
    Build a search results response with parameters echoed back.
    
    Args:
        results: Search results list
        search_params: Parameters used for search
        results_key: Key name for results in response
    
    Returns:
        Flask JSON response tuple
    """
    return success_response(data={
        results_key: results,
        'search_parameters': search_params,
        'count': len(results)
    })