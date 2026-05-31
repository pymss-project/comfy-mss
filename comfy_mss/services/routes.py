import os
import folder_paths

from aiohttp import web
from server import PromptServer
from ..constants import AUDIO_EXTENSIONS
from ..constants import MODEL_DIR_ENV_VARS
from ..paths import resolve_model_dir
from .catalog import custom_model_catalog, model_catalog


def _safe_upload_filename(filename):
    filename = os.path.basename(str(filename or "").replace("\\", "/"))
    filename = filename.strip().strip(".")
    if not filename:
        return None
    if not filename.lower().endswith(AUDIO_EXTENSIONS):
        return None
    return filename


def _available_upload_path(upload_dir, filename):
    stem, ext = os.path.splitext(filename)
    path = os.path.join(upload_dir, filename)
    index = 1
    while os.path.exists(path):
        candidate = f"{stem} ({index}){ext}"
        path = os.path.join(upload_dir, candidate)
        index += 1
    return path


def register_routes():
    if PromptServer is None:
        return

    @PromptServer.instance.routes.get("/comfy-mss/models")
    async def get_comfy_mss_models(request):
        model_kind = request.query.get("kind", "all")
        if model_kind not in {"all", "mss", "vr", "custom"}:
            model_kind = "all"
        model_dir = request.query.get("model_dir")
        models = custom_model_catalog(model_dir or "Default/custom") if model_kind == "custom" else model_catalog(model_kind)
        return web.json_response(
            {
                "models": models,
                "model_dir": resolve_model_dir(create=True),
                "env_vars": MODEL_DIR_ENV_VARS,
            }
        )

    @PromptServer.instance.routes.post("/comfy-mss/upload-audio")
    async def upload_comfy_mss_audio(request):
        post = await request.post()
        upload = post.get("audio")
        if not upload or not upload.file:
            return web.Response(status=400, text="audio file is required")

        filename = _safe_upload_filename(upload.filename)
        if filename is None:
            return web.Response(status=400, text="unsupported audio file")

        upload_dir = folder_paths.get_input_directory()
        os.makedirs(upload_dir, exist_ok=True)
        path = _available_upload_path(upload_dir, filename)
        with open(path, "wb") as handle:
            handle.write(upload.file.read())

        return web.json_response({"name": os.path.basename(path)})
