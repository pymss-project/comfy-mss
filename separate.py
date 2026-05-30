import gc

import comfy.utils
import numpy as np

from .audio_utils import audio_to_numpy, numpy_to_audio
from .catalog import model_names, stem_names
from .constants import CATEGORY, MAX_STEMS, MISSING_PYMSS_OPTION, MSS_PARAMS_TYPE, VR_PARAMS_TYPE
from .core import import_pymss
from .paths import resolve_model_dir


def device_ids(raw):
    values = [int(item.strip()) for item in str(raw or "0").split(",") if item.strip()]
    return values or [0]


def make_comfy_progress_callback():
    pbar_holder = {"pbar": None}

    def progress_callback(done, total, _message=None):
        total = max(1, int(total or 1))
        done = max(0, min(int(done or 0), total))
        if pbar_holder["pbar"] is None or pbar_holder["pbar"].total != total:
            pbar_holder["pbar"] = comfy.utils.ProgressBar(total)
        pbar_holder["pbar"].update_absolute(done, total)

    return progress_callback


def separate_audio(audio, model_name, model_kind, params, model_dir, download_missing, source, device, device_ids_raw, use_tta, debug):
    if model_name == MISSING_PYMSS_OPTION:
        import_pymss()

    pymss = import_pymss()
    mix, sample_rate = audio_to_numpy(audio)
    stems = stem_names(model_name, model_kind)
    store_dirs = {stem: "" for stem in stems}

    separator = pymss.MSSeparator.from_model_name(
        model_name,
        model_dir=resolve_model_dir(model_dir),
        download=bool(download_missing),
        source=source,
        device=device,
        device_ids=device_ids(device_ids_raw),
        output_format="wav",
        use_tta=bool(use_tta),
        store_dirs=store_dirs,
        debug=bool(debug),
        comfyui_mode=True,
        progress_callback=make_comfy_progress_callback(),
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
        outputs.append(numpy_to_audio(value if value is not None else np.zeros_like(mix), sample_rate))

    while len(outputs) < MAX_STEMS:
        outputs.append(None)
    return tuple(outputs[:MAX_STEMS])


class _SeparateBase:
    MODEL_KIND = "all"
    PARAM_TYPE = "*"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "model_name": (model_names(cls.MODEL_KIND),),
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
        return separate_audio(
            audio=audio,
            model_name=model_name,
            model_kind=self.MODEL_KIND,
            params=params,
            model_dir=model_dir,
            download_missing=download_missing,
            source=source,
            device=device,
            device_ids_raw=device_ids,
            use_tta=use_tta,
            debug=debug,
        )


class MssSeparate(_SeparateBase):
    MODEL_KIND = "mss"
    PARAM_TYPE = MSS_PARAMS_TYPE


class VrSeparate(_SeparateBase):
    MODEL_KIND = "vr"
    PARAM_TYPE = VR_PARAMS_TYPE
