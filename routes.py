try:
    from aiohttp import web
    from server import PromptServer
except Exception:
    web = None
    PromptServer = None

from .catalog import model_catalog
from .constants import MODEL_DIR_ENV_VARS
from .paths import resolve_model_dir


def register_routes():
    if PromptServer is None:
        return

    @PromptServer.instance.routes.get("/comfy-mss/models")
    async def get_comfy_mss_models(request):
        model_kind = request.query.get("kind", "all")
        if model_kind not in {"all", "mss", "vr"}:
            model_kind = "all"
        return web.json_response(
            {
                "models": model_catalog(model_kind),
                "model_dir": resolve_model_dir(create=True),
                "env_vars": MODEL_DIR_ENV_VARS,
            }
        )
