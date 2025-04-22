from flask import request, url_for
from math import ceil

def paginate(query, page, per_page, schema):
    """
    Apply pagination to a SQLAlchemy query and return formatted results
    
    Args:
        query: SQLAlchemy query object
        page (int): Current page number
        per_page (int): Items per page
        schema: Marshmallow schema for serialization
        
    Returns:
        dict: Pagination data with items and metadata
    """
    # Ensure valid pagination parameters
    page = max(1, page)
    per_page = min(100, max(1, per_page))
    
    # Get total items count
    total_items = query.count()
    
    # Calculate pagination values
    total_pages = ceil(total_items / per_page) if total_items > 0 else 0
    
    # Apply pagination to query
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    
    # Serialize items with schema
    serialized_items = schema.dump(items)
    
    # Build pagination metadata
    pagination = {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages
    }
    
    # Add next/prev page links
    if pagination['has_prev']:
        pagination['prev_page'] = page - 1
    
    if pagination['has_next']:
        pagination['next_page'] = page + 1
    
    return {
        'data': serialized_items,
        'pagination': pagination
    }
