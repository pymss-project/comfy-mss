def coerce_optional_path(value):
    value = str(value or "").strip()
    return value or None
