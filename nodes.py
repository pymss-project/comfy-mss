import gc
import json
import os
import re
from functools import lru_cache

import numpy as np
import torch

import folder_paths

try:
    from aiohttp import web
    from server import PromptServer
except Exception:
    web = None
    PromptServer = None


CATEGORY = "audio/pymss"
MISSING_PYMSS_OPTION = "pymss is not installed"
MAX_STEMS = 64
MSS_PARAMS_TYPE = "PYMSS_MSS_PARAMS"
VR_PARAMS_TYPE = "PYMSS_VR_PARAMS"
MODEL_FOLDER_NAME = "pymss"
MODEL_DIR_ENV_VARS = ("COMFY_MSS_MODEL_DIR", "PYMSS_MODEL_DIR")
AUDIO_EXTENSIONS = (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aac", ".aiff", ".aif", ".wma", ".opus")


def _default_model_dir():
    return os.path.join(folder_paths.models_dir, MODEL_FOLDER_NAME)


def _resolve_model_dir(model_dir=None, create=True):
    resolved = _coerce_optional_path(model_dir)
    if resolved is None:
        for env_name in MODEL_DIR_ENV_VARS:
            resolved = _coerce_optional_path(os.environ.get(env_name))
            if resolved is not None:
                break
    if resolved is None:
        resolved = _default_model_dir()

    resolved = os.path.abspath(os.path.expanduser(os.path.expandvars(resolved)))
    if create:
        os.makedirs(resolved, exist_ok=True)
    return resolved


def _register_model_folder():
    model_dir = _resolve_model_dir(create=True)
    folder_paths.add_model_folder_path(MODEL_FOLDER_NAME, model_dir, is_default=True)
    return model_dir


def _import_pymss():
    try:
        import pymss
    except Exception as exc:
        raise RuntimeError(
            "pymss is required by comfy-mss. Install it with "
            "`python -m pip install pymss`, or for local development use "
            "`python -m pip install -e E:\\vs\\pymss` inside the ComfyUI environment."
        ) from exc
    return pymss


def _coerce_optional_path(value):
    value = str(value or "").strip()
    return value or None


DEFAULT_MODEL_DIR = _register_model_folder()


def _model_names(model_kind):
    try:
        return [item["name"] for item in _model_catalog(model_kind)]
    except Exception:
        return [MISSING_PYMSS_OPTION]


def _split_stems(value):
    return [item.strip() for item in re.split(r"[|/]", value or "") if item.strip()]


def _entry_stems(entry):
    stems = _split_stems(entry.config_instruments)
    if stems:
        return stems

    if entry.model_type == "vr":
        try:
            from pymss.modules.vocal_remover.vr_models import VR_MODEL_METADATA

            data = VR_MODEL_METADATA.get(entry.name)
            if data:
                return [data["primary_stem"], data["secondary_stem"]]
        except Exception:
            pass

    stems = _split_stems(entry.target_stem)
    return stems or ["audio"]


@lru_cache(maxsize=8)
def _model_catalog(model_kind="all"):
    pymss = _import_pymss()
    rows = []
    for entry in pymss.list_models(supported=True):
        if model_kind == "vr" and entry.model_type != "vr":
            continue
        if model_kind == "mss" and entry.model_type == "vr":
            continue
        rows.append(
            {
                "name": entry.name,
                "aliases": list(entry.aliases),
                "model_type": entry.model_type,
                "architecture": entry.architecture,
                "category": entry.category_path or entry.primary_category,
                "category_cn": " / ".join(
                    part for part in (entry.primary_category_cn, entry.secondary_category_cn) if part
                ),
                "target_stem": entry.target_stem,
                "stems": _entry_stems(entry),
            }
        )
    return rows


def _stem_names(model_name, model_kind):
    for item in _model_catalog(model_kind):
        if item["name"] == model_name:
            return item["stems"]
    return ["audio"]


def _audio_to_numpy(audio):
    if audio is None:
        raise ValueError("audio input is required.")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim != 3:
        raise ValueError(f"Expected ComfyUI AUDIO waveform [batch, channels, samples], got shape {tuple(waveform.shape)}.")
    if waveform.shape[0] != 1:
        raise ValueError("pymss separation currently expects a single audio item. Split batches before this node.")
    return waveform[0].detach().cpu().numpy().astype(np.float32, copy=False), sample_rate


def _numpy_to_audio(value, sample_rate):
    array = np.asarray(value, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    elif array.ndim == 2:
        # pymss returns most stems as [samples, channels]. ComfyUI wants [channels, samples].
        if array.shape[0] > array.shape[1] and array.shape[1] <= 8:
            array = array.T
    else:
        raise ValueError(f"Unsupported separated stem shape: {array.shape}")
    return {"waveform": torch.from_numpy(np.ascontiguousarray(array)).unsqueeze(0), "sample_rate": int(sample_rate)}


def _audio_batch_to_numpy(audio):
    if audio is None:
        raise ValueError("audio input is required.")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim != 3:
        raise ValueError(f"Expected ComfyUI AUDIO waveform [batch, channels, samples], got shape {tuple(waveform.shape)}.")
    return waveform.detach().cpu().numpy().astype(np.float32, copy=False), sample_rate


def _match_audio_for_binary_op(audio_a, audio_b):
    import torchaudio

    if audio_a is None or audio_b is None:
        raise ValueError("Both audio inputs are required.")

    waveform_a = audio_a["waveform"].detach().cpu().float()
    waveform_b = audio_b["waveform"].detach().cpu().float()
    sample_rate_a = int(audio_a["sample_rate"])
    sample_rate_b = int(audio_b["sample_rate"])

    if waveform_a.ndim != 3 or waveform_b.ndim != 3:
        raise ValueError("Expected ComfyUI AUDIO waveforms with shape [batch, channels, samples].")

    if sample_rate_a != sample_rate_b:
        waveform_b = torchaudio.functional.resample(waveform_b, sample_rate_b, sample_rate_a)

    batch_size = min(waveform_a.shape[0], waveform_b.shape[0])
    channels = min(waveform_a.shape[1], waveform_b.shape[1])
    length = min(waveform_a.shape[2], waveform_b.shape[2])
    if batch_size <= 0 or channels <= 0 or length <= 0:
        raise ValueError("Audio inputs must have non-empty batch, channel, and sample dimensions.")

    return (
        waveform_a[:batch_size, :channels, :length],
        waveform_b[:batch_size, :channels, :length],
        sample_rate_a,
    )


def _numpy_to_comfy_audio(audio, sample_rate):
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    elif array.ndim != 2:
        raise ValueError(f"Unsupported loaded audio shape: {array.shape}")
    return {"waveform": torch.from_numpy(np.ascontiguousarray(array)).unsqueeze(0), "sample_rate": int(sample_rate)}


def _resolve_input_path(path):
    path = str(path or "").strip().strip('"')
    if not path:
        return None
    path = os.path.expanduser(os.path.expandvars(path))
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(folder_paths.get_input_directory(), path))


def _parse_audio_file_list(audio_files):
    paths = []
    for line in str(audio_files or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        resolved = _resolve_input_path(line)
        if resolved is not None:
            paths.append(resolved)
    return paths


def _parse_extensions(extensions):
    parsed = []
    for item in re.split(r"[,;\s]+", str(extensions or "")):
        item = item.strip().lower()
        if not item:
            continue
        parsed.append(item if item.startswith(".") else f".{item}")
    return tuple(parsed or AUDIO_EXTENSIONS)


def _scan_audio_folder(folder, recursive, extensions):
    folder = _resolve_input_path(folder)
    if folder is None:
        raise ValueError("folder is required when input_mode is folder.")
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"folder does not exist: {folder}")

    matches = []
    extensions = tuple(ext.lower() for ext in extensions)
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for filename in files:
                if filename.lower().endswith(extensions):
                    matches.append(os.path.join(root, filename))
    else:
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path) and filename.lower().endswith(extensions):
                matches.append(path)
    return matches


def _load_audio_paths(paths, sample_rate, mono, sort_files, limit):
    from pymss.audio_io import load_audio

    unique_paths = []
    seen = set()
    for path in paths:
        path = os.path.abspath(path)
        if path in seen:
            continue
        seen.add(path)
        unique_paths.append(path)

    if sort_files:
        unique_paths.sort(key=lambda item: item.lower())
    if limit > 0:
        unique_paths = unique_paths[:limit]
    if not unique_paths:
        raise ValueError("No audio files were found.")

    audios = []
    for path in unique_paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"audio file does not exist: {path}")
        audio, sr = load_audio(path, sr=None if sample_rate <= 0 else sample_rate, mono=mono)
        audios.append(_numpy_to_comfy_audio(audio, sr))
    return audios, unique_paths


def _resolve_save_dir(output_folder):
    output_folder = str(output_folder or "").strip()
    if not output_folder:
        save_dir = folder_paths.get_output_directory()
    elif os.path.isabs(output_folder):
        save_dir = output_folder
    else:
        save_dir = os.path.join(folder_paths.get_output_directory(), output_folder)
    save_dir = os.path.abspath(os.path.expanduser(os.path.expandvars(save_dir)))
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def _safe_filename_part(value, fallback):
    value = str(value or "").strip() or fallback
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.strip(" .")
    return value or fallback


def _save_comfy_audio(audio, output_folder, filename_prefix, output_format, wav_bit_depth, flac_bit_depth, mp3_bit_rate, m4a_bit_rate, m4a_codec, m4a_aac_at_quality):
    from pymss.audio_io import save_audio

    waveform, sample_rate = _audio_batch_to_numpy(audio)
    save_dir = _resolve_save_dir(output_folder)
    prefix = _safe_filename_part(filename_prefix, "ComfyUI")
    output_format = output_format.lower()
    audio_params = {
        "wav_bit_depth": wav_bit_depth,
        "flac_bit_depth": flac_bit_depth,
        "mp3_bit_rate": mp3_bit_rate,
        "m4a_bit_rate": m4a_bit_rate,
        "m4a_codec": m4a_codec,
        "m4a_aac_at_quality": m4a_aac_at_quality,
    }

    saved_paths = []
    batch_size = int(waveform.shape[0])
    for index, item in enumerate(waveform):
        # ComfyUI AUDIO is [channels, samples]; pymss/av saving expects [samples, channels].
        audio_array = np.ascontiguousarray(item.T)
        suffix = "" if batch_size == 1 else f"_{index:05d}"
        file_name = f"{prefix}{suffix}"
        path = os.path.join(save_dir, f"{file_name}.{output_format}")
        save_audio(path, audio_array, sample_rate, output_format, audio_params)
        saved_paths.append(path)
    return saved_paths


def _device_ids(raw):
    values = [int(item.strip()) for item in str(raw or "0").split(",") if item.strip()]
    return values or [0]


def _clean_none(params):
    return {key: value for key, value in params.items() if value is not None}


def _separate_audio(audio, model_name, model_kind, params, model_dir, download_missing, source, device, device_ids, use_tta, debug):
    if model_name == MISSING_PYMSS_OPTION:
        _import_pymss()

    pymss = _import_pymss()
    mix, sample_rate = _audio_to_numpy(audio)
    stems = _stem_names(model_name, model_kind)
    store_dirs = {stem: "" for stem in stems}

    separator = pymss.MSSeparator.from_model_name(
        model_name,
        model_dir=_resolve_model_dir(model_dir),
        download=bool(download_missing),
        source=source,
        device=device,
        device_ids=_device_ids(device_ids),
        output_format="wav",
        use_tta=bool(use_tta),
        store_dirs=store_dirs,
        debug=bool(debug),
        inference_params=params or {},
    )
    try:
        results = separator.separate(mix, pbar=False, stems=None)
    finally:
        separator.del_cache()
        gc.collect()

    outputs = []
    for stem in stems:
        value = results.get(stem)
        if value is None:
            lower = stem.lower()
            value = next((audio_value for key, audio_value in results.items() if key.lower() == lower), None)
        outputs.append(_numpy_to_audio(value if value is not None else np.zeros_like(mix), sample_rate))

    while len(outputs) < MAX_STEMS:
        outputs.append(None)
    return tuple(outputs[:MAX_STEMS])


class PymssMssParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "override_batch_size": ("BOOLEAN", {"default": False}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 128, "step": 1}),
                "override_overlap_size": ("BOOLEAN", {"default": False}),
                "overlap_size": ("INT", {"default": 2048, "min": 0, "max": 2147483647, "step": 1024}),
                "override_chunk_size": ("BOOLEAN", {"default": False}),
                "chunk_size": ("INT", {"default": 352800, "min": 1, "max": 2147483647, "step": 1024}),
                "override_normalize": ("BOOLEAN", {"default": False}),
                "normalize": ("BOOLEAN", {"default": False}),
                "override_stem_batch_size": ("BOOLEAN", {"default": False}),
                "stem_batch_size": ("INT", {"default": 1, "min": 1, "max": MAX_STEMS, "step": 1}),
                "mask_mode": (["default", "no_segm", "soft", "hard"], {"default": "default"}),
                "override_use_amp": ("BOOLEAN", {"default": False}),
                "use_amp": ("BOOLEAN", {"default": True}),
                "extra_params_json": ("STRING", {"default": "{}", "multiline": True}),
            }
        }

    RETURN_TYPES = (MSS_PARAMS_TYPE,)
    RETURN_NAMES = ("mss_params",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(
        self,
        override_batch_size,
        batch_size,
        override_overlap_size,
        overlap_size,
        override_chunk_size,
        chunk_size,
        override_normalize,
        normalize,
        override_stem_batch_size,
        stem_batch_size,
        mask_mode,
        override_use_amp,
        use_amp,
        extra_params_json,
    ):
        params = {
            "batch_size": batch_size if override_batch_size else None,
            "overlap_size": overlap_size if override_overlap_size else None,
            "chunk_size": chunk_size if override_chunk_size else None,
            "normalize": bool(normalize) if override_normalize else None,
            "stem_batch_size": stem_batch_size if override_stem_batch_size else None,
            "mask_mode": None if mask_mode == "default" else mask_mode,
            "use_amp": bool(use_amp) if override_use_amp else None,
        }
        params.update(_parse_extra_params(extra_params_json))
        return (_clean_none(params),)


class PymssVrParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "batch_size": ("INT", {"default": 2, "min": 1, "max": 128, "step": 1}),
                "window_size": ("INT", {"default": 512, "min": 128, "max": 4096, "step": 128}),
                "aggression": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "enable_tta": ("BOOLEAN", {"default": False}),
                "enable_post_process": ("BOOLEAN", {"default": False}),
                "post_process_threshold": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01}),
                "high_end_process": ("BOOLEAN", {"default": False}),
                "use_amp": ("BOOLEAN", {"default": True}),
                "extra_params_json": ("STRING", {"default": "{}", "multiline": True}),
            }
        }

    RETURN_TYPES = (VR_PARAMS_TYPE,)
    RETURN_NAMES = ("vr_params",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(
        self,
        batch_size,
        window_size,
        aggression,
        enable_tta,
        enable_post_process,
        post_process_threshold,
        high_end_process,
        use_amp,
        extra_params_json,
    ):
        params = {
            "batch_size": batch_size,
            "window_size": window_size,
            "aggression": aggression,
            "enable_tta": bool(enable_tta),
            "enable_post_process": bool(enable_post_process),
            "post_process_threshold": post_process_threshold,
            "high_end_process": bool(high_end_process),
            "use_amp": bool(use_amp),
        }
        params.update(_parse_extra_params(extra_params_json))
        return (_clean_none(params),)


def _parse_extra_params(raw):
    raw = str(raw or "").strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("extra_params_json must be a JSON object.")
    return parsed


class _SeparateBase:
    MODEL_KIND = "all"
    PARAM_TYPE = "*"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "model_name": (_model_names(cls.MODEL_KIND),),
                "device": (["auto", "cpu", "cuda", "mps", "mlx"], {"default": "auto"}),
                "download_missing": ("BOOLEAN", {"default": False}),
                "source": (["modelscope", "huggingface", "hf-mirror"], {"default": "modelscope"}),
            },
            "optional": {
                "params": (cls.PARAM_TYPE,),
                "model_dir": ("STRING", {"default": "", "multiline": False}),
                "device_ids": ("STRING", {"default": "0", "multiline": False}),
                "debug": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("AUDIO",) * MAX_STEMS
    RETURN_NAMES = tuple(f"stem_{index + 1}" for index in range(MAX_STEMS))
    FUNCTION = "separate"
    CATEGORY = CATEGORY

    def separate(
        self,
        audio,
        model_name,
        device,
        download_missing,
        source,
        params=None,
        model_dir="",
        device_ids="0",
        debug=False,
    ):
        params = dict(params or {})
        use_tta = bool(params.pop("enable_tta", False))
        return _separate_audio(
            audio=audio,
            model_name=model_name,
            model_kind=self.MODEL_KIND,
            params=params,
            model_dir=model_dir,
            download_missing=download_missing,
            source=source,
            device=device,
            device_ids=device_ids,
            use_tta=use_tta,
            debug=debug,
        )


class MssSeparate(_SeparateBase):
    MODEL_KIND = "mss"
    PARAM_TYPE = MSS_PARAMS_TYPE


class VrSeparate(_SeparateBase):
    MODEL_KIND = "vr"
    PARAM_TYPE = VR_PARAMS_TYPE


class PymssModelList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_kind": (["all", "mss", "vr"], {"default": "all"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_metadata_json",)
    FUNCTION = "list_models"
    CATEGORY = CATEGORY

    def list_models(self, model_kind):
        return (json.dumps(_model_catalog(model_kind), ensure_ascii=False, indent=2),)


class PymssLoadAudioBatch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_mode": (["files", "folder"], {"default": "files"}),
                "audio_files": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                    },
                ),
                "folder": ("STRING", {"default": "", "multiline": False}),
                "recursive": ("BOOLEAN", {"default": False}),
                "extensions": ("STRING", {"default": ",".join(AUDIO_EXTENSIONS), "multiline": False}),
                "sort_files": ("BOOLEAN", {"default": True}),
                "limit": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1}),
                "sample_rate": ("INT", {"default": 0, "min": 0, "max": 384000, "step": 1000}),
                "mono": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "path")
    OUTPUT_IS_LIST = (True, True)
    FUNCTION = "load"
    CATEGORY = CATEGORY

    def load(self, input_mode, audio_files, folder, recursive, extensions, sort_files, limit, sample_rate, mono):
        exts = _parse_extensions(extensions)
        if input_mode == "folder":
            paths = _scan_audio_folder(folder, recursive, exts)
        else:
            paths = _parse_audio_file_list(audio_files)

        audios, loaded_paths = _load_audio_paths(
            paths=paths,
            sample_rate=int(sample_rate),
            mono=bool(mono),
            sort_files=bool(sort_files),
            limit=int(limit),
        )
        return (audios, loaded_paths)


class PymssAudioSubtract:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_a": ("AUDIO",),
                "audio_b": ("AUDIO",),
                "normalize_if_clipped": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "subtract"
    CATEGORY = CATEGORY

    def subtract(self, audio_a, audio_b, normalize_if_clipped):
        waveform_a, waveform_b, sample_rate = _match_audio_for_binary_op(audio_a, audio_b)
        result = waveform_a - waveform_b
        if normalize_if_clipped:
            peak = result.abs().amax()
            if peak > 1.0:
                result = result / peak
        return ({"waveform": result, "sample_rate": sample_rate},)


class PymssSaveAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {"default": "audio", "multiline": False}),
                "output_format": (["wav", "flac", "mp3", "m4a"], {"default": "wav"}),
                "output_folder": ("STRING", {"default": "", "multiline": False}),
                "wav_bit_depth": (["FLOAT", "PCM_24", "PCM_16"], {"default": "FLOAT"}),
                "flac_bit_depth": (["PCM_24", "PCM_16"], {"default": "PCM_24"}),
                "mp3_bit_rate": (["128k", "192k", "256k", "320k"], {"default": "320k"}),
                "m4a_bit_rate": (["128k", "192k", "256k", "320k"], {"default": "192k"}),
                "m4a_codec": (["aac", "aac_at"], {"default": "aac"}),
                "m4a_aac_at_quality": ("INT", {"default": 2, "min": 0, "max": 14, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("saved_paths_json", "first_path")
    FUNCTION = "save"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def save(
        self,
        audio,
        filename_prefix,
        output_format,
        output_folder,
        wav_bit_depth,
        flac_bit_depth,
        mp3_bit_rate,
        m4a_bit_rate,
        m4a_codec,
        m4a_aac_at_quality,
    ):
        saved_paths = _save_comfy_audio(
            audio,
            output_folder,
            filename_prefix,
            output_format,
            wav_bit_depth,
            flac_bit_depth,
            mp3_bit_rate,
            m4a_bit_rate,
            m4a_codec,
            m4a_aac_at_quality,
        )
        return (json.dumps(saved_paths, ensure_ascii=False, indent=2), saved_paths[0] if saved_paths else "")


if PromptServer is not None:
    @PromptServer.instance.routes.get("/comfy-mss/models")
    async def get_comfy_mss_models(request):
        model_kind = request.query.get("kind", "all")
        if model_kind not in {"all", "mss", "vr"}:
            model_kind = "all"
        return web.json_response(
            {
                "models": _model_catalog(model_kind),
                "model_dir": _resolve_model_dir(create=True),
                "env_vars": MODEL_DIR_ENV_VARS,
            }
        )


NODE_CLASS_MAPPINGS = {
    "mss_separate": MssSeparate,
    "vr_separate": VrSeparate,
    "pymss_mss_params": PymssMssParams,
    "pymss_vr_params": PymssVrParams,
    "PymssModelList": PymssModelList,
    "pymss_load_audio_batch": PymssLoadAudioBatch,
    "pymss_audio_subtract": PymssAudioSubtract,
    "pymss_save_audio": PymssSaveAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "mss_separate": "mss_separate",
    "vr_separate": "vr_separate",
    "pymss_mss_params": "pymss MSS Params",
    "pymss_vr_params": "pymss VR Params",
    "PymssModelList": "pymss Model List",
    "pymss_load_audio_batch": "pymss Load Audio Batch",
    "pymss_audio_subtract": "pymss Audio Subtract",
    "pymss_save_audio": "pymss Save Audio",
}
