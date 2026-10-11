from aiohttp import web
from server import PromptServer

from .catalog import custom_model_catalog, model_catalog


PUBLIC_MODEL_FIELDS = (
    "name",
    "display_name",
    "display_name_cn",
    "downloaded",
    "aliases",
    "model_type",
    "stems",
    "stems_complete",
)


def public_model_entry(entry):
    return {key: entry[key] for key in PUBLIC_MODEL_FIELDS if key in entry}


def register_routes():
    if PromptServer is None:
        return

    @PromptServer.instance.routes.get("/comfy-mss/models")
    async def get_comfy_mss_models(request):
        model_kind = request.query.get("kind", "all")
        if model_kind not in {"all", "mss", "vr", "custom"}:
            model_kind = "all"
        models = custom_model_catalog() if model_kind == "custom" else model_catalog(model_kind)
        return web.json_response({"models": [public_model_entry(item) for item in models]})
