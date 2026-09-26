import asyncio
import os
import shutil

import folder_paths
from aiohttp import web
from server import PromptServer

from ..constants import AUDIO_EXTENSIONS, MODEL_DIR_ENV_VARS
from ..paths import registered_model_dirs
from .catalog import custom_model_catalog, model_catalog


def _store_uploaded_file(upload_dir, filename, source):
    stem, ext = os.path.splitext(filename)
    for index in range(10000):
        candidate_name = filename if index == 0 else f"{stem} ({index}){ext}"
        candidate = os.path.realpath(os.path.join(upload_dir, candidate_name))
        if os.path.commonpath((upload_dir, candidate)) != upload_dir:
            raise ValueError("invalid audio filename")
        try:
            with open(candidate, "xb") as handle:
                shutil.copyfileobj(source, handle, length=1024 * 1024)
            return candidate
        except FileExistsError:
            continue
        except Exception:
            try:
                os.unlink(candidate)
            except OSError:
                pass
            raise
    raise FileExistsError("could not allocate a unique audio filename")


def register_routes():
    if PromptServer is None:
        return

    @PromptServer.instance.routes.get("/comfy-mss/models")
    async def get_comfy_mss_models(request):
        model_kind = request.query.get("kind", "all")
        if model_kind not in {"all", "mss", "vr", "custom"}:
            model_kind = "all"
        models = custom_model_catalog() if model_kind == "custom" else model_catalog(model_kind)
        return web.json_response(
            {
                "models": models,
                "model_dirs": registered_model_dirs(create=True),
                "env_vars": MODEL_DIR_ENV_VARS,
            }
        )

    @PromptServer.instance.routes.post("/comfy-mss/upload-audio")
    async def upload_comfy_mss_audio(request):
        # This endpoint writes to the server filesystem.  Match the PR
        # requirement by allowing only requests originating on the server.
        peer = request.remote
        if peer not in {None, "127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"}:
            return web.Response(status=403, text="audio upload is local-only")

        post = await request.post()
        upload = post.get("audio")
        if not upload or not upload.file:
            return web.Response(status=400, text="audio file is required")

        filename = os.path.basename(str(upload.filename or "").replace("\\", "/")).strip().strip(".")
        if not filename or not filename.lower().endswith(AUDIO_EXTENSIONS):
            return web.Response(status=400, text="unsupported audio file")

        upload_dir = os.path.realpath(folder_paths.get_input_directory())
        os.makedirs(upload_dir, exist_ok=True)
        try:
            path = await asyncio.to_thread(_store_uploaded_file, upload_dir, filename, upload.file)
        except ValueError:
            return web.Response(status=400, text="invalid audio filename")
        return web.json_response({"name": os.path.basename(path)})
