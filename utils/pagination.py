from math import ceil

def _as_int(value, default):
    """
    Convert any value to int, falling back to ``default`` if conversion
    fails or the value is ``None``.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def paginate(query, page, per_page, schema):
    """
    Apply pagination to a SQLAlchemy *query* and return a dictionary
    containing serialized items plus pagination metadata.

    Args:
        query: SQLAlchemy query object.
        page (int | None): Current page number (1-based). If ``None`` or not
            numeric, defaults to 1.
        per_page (int | None): Items per page. Defaults to 10, with a hard
            upper limit of 100.
        schema: Marshmallow schema used to serialize each item.

    Returns:
        dict: ``{"data": [...], "pagination": {...}}``
    """
    # Sanitize parameters -----------------------------------------------------
    page = max(1, _as_int(page, 1))
    per_page = min(100, max(1, _as_int(per_page, 10)))

    # -------------------------------------------------------------------------
    total_items = query.count()
    total_pages = ceil(total_items / per_page) if total_items else 0

    items = (
        query.limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    serialized_items = schema.dump(items)

    pagination = {
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }
    if pagination["has_prev"]:
        pagination["prev_page"] = page - 1
    if pagination["has_next"]:
        pagination["next_page"] = page + 1

    return {"data": serialized_items, "pagination": pagination}
