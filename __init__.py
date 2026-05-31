try:
    import pymss  # noqa: F401
except Exception as exc:
    import sys

    python = sys.executable
    raise RuntimeError(f'pymss is required by comfy-mss. Install it with "{python} -m pip install pymss"') from exc

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ("NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS")
