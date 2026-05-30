def import_pymss():
    try:
        import pymss
    except Exception as exc:
        raise RuntimeError(
            "pymss is required by comfy-mss. Install it with "
            "`python -m pip install pymss`, or for local development use "
            "`python -m pip install -e E:\\vs\\pymss` inside the ComfyUI environment."
        ) from exc
    return pymss


def coerce_optional_path(value):
    value = str(value or "").strip()
    return value or None
