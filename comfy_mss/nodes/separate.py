import gc
import time

import comfy.utils
import numpy as np
import torch

from pymss import MSSeparator
from ..constants import CATEGORY, MSS_MAX_STEMS, MSS_PARAMS_TYPE, VR_MAX_STEMS, VR_PARAMS_TYPE
from ..paths import resolve_model_dir
from ..services.catalog import (
    clean_model_display_name,
    custom_model_dir,
    custom_model_entry,
    custom_model_names,
    custom_stem_names,
    model_names,
    stem_names,
)
from ..utils.audio import audio_source_path, audio_to_numpy, numpy_to_audio


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


def separate_audio(audio, model_name, model_kind, max_stems, params, model_dir, download_missing, source, device, device_ids_raw, use_tta, debug):
    model_name = clean_model_display_name(model_name)
    timings = {}
    total_start = time.perf_counter()
    step_start = time.perf_counter()
    mix, sample_rate = audio_to_numpy(audio)
    timings["audio_to_numpy"] = time.perf_counter() - step_start
    source_path = audio_source_path(audio)
    stems = stem_names(model_name, model_kind)
    store_dirs = {stem: "" for stem in stems}

    with torch.inference_mode(False):
        step_start = time.perf_counter()
        separator = MSSeparator.from_model_name(
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
            progress_callback=make_comfy_progress_callback(),
            inference_params=params or {},
        )
        timings["load_model"] = time.perf_counter() - step_start
        try:
            step_start = time.perf_counter()
            results = separator.separate(mix, pbar=True, stems=stems)
            timings["separate"] = time.perf_counter() - step_start
        finally:
            step_start = time.perf_counter()
            separator.del_cache()
            gc.collect()
            timings["cleanup"] = time.perf_counter() - step_start

    step_start = time.perf_counter()
    outputs = []
    stem_outputs = []
    for stem in stems:
        value = results.get(stem)
        if value is None:
            lower = stem.lower()
            value = next((audio_value for key, audio_value in results.items() if key.lower() == lower), None)
        outputs.append(
            numpy_to_audio(
                value if value is not None else np.zeros_like(mix),
                sample_rate,
                stem_name=stem,
                source_path=source_path,
            )
        )
        stem_outputs.append(stem)

    paired_outputs = []
    for index in range(max_stems):
        paired_outputs.append(outputs[index] if index < len(outputs) else None)
        paired_outputs.append(stem_outputs[index] if index < len(stem_outputs) else "")
    timings["numpy_to_audio"] = time.perf_counter() - step_start
    timings["total"] = time.perf_counter() - total_start
    return tuple(paired_outputs)


def separate_custom_audio(audio, model_name, model_type, max_stems, params, model_dir, device, device_ids_raw, use_tta, debug):
    timings = {}
    total_start = time.perf_counter()
    step_start = time.perf_counter()
    mix, sample_rate = audio_to_numpy(audio)
    timings["audio_to_numpy"] = time.perf_counter() - step_start
    source_path = audio_source_path(audio)
    entry = custom_model_entry(model_name, model_dir)
    if entry is None:
        raise FileNotFoundError(f"custom model not found or missing yaml: {model_name}")
    stems = custom_stem_names(model_name, model_dir)
    store_dirs = {stem: "" for stem in stems}

    with torch.inference_mode(False):
        step_start = time.perf_counter()
        separator = MSSeparator(
            model_type=model_type,
            model_path=entry["model_path"],
            config_path=entry["config_path"],
            device=device,
            device_ids=device_ids(device_ids_raw),
            output_format="wav",
            use_tta=bool(use_tta),
            store_dirs=store_dirs,
            debug=bool(debug),
            progress_callback=make_comfy_progress_callback(),
            inference_params=params or {},
        )
        timings["load_model"] = time.perf_counter() - step_start
        try:
            step_start = time.perf_counter()
            results = separator.separate(mix, pbar=True, stems=stems)
            timings["separate"] = time.perf_counter() - step_start
        finally:
            step_start = time.perf_counter()
            separator.del_cache()
            gc.collect()
            timings["cleanup"] = time.perf_counter() - step_start

    step_start = time.perf_counter()
    outputs = []
    stem_outputs = []
    for stem in stems:
        value = results.get(stem)
        if value is None:
            lower = stem.lower()
            value = next((audio_value for key, audio_value in results.items() if key.lower() == lower), None)
        outputs.append(
            numpy_to_audio(
                value if value is not None else np.zeros_like(mix),
                sample_rate,
                stem_name=stem,
                source_path=source_path,
            )
        )
        stem_outputs.append(stem)

    paired_outputs = []
    for index in range(max_stems):
        paired_outputs.append(outputs[index] if index < len(outputs) else None)
        paired_outputs.append(stem_outputs[index] if index < len(stem_outputs) else "")
    timings["numpy_to_audio"] = time.perf_counter() - step_start
    timings["total"] = time.perf_counter() - total_start
    return tuple(paired_outputs)


class _SeparateBase:
    MODEL_KIND = "all"
    MAX_STEMS = MSS_MAX_STEMS
    PARAM_TYPE = "*"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "model_name": (model_names(cls.MODEL_KIND),),
                "device": (["auto", "cpu", "cuda", "mps", "mlx"], {"default": "auto"}),
                "download_missing": ("BOOLEAN", {"default": True}),
                "source": (["modelscope", "huggingface", "hf-mirror"], {"default": "modelscope"}),
            },
            "optional": {
                "params": (cls.PARAM_TYPE,),
                "model_dir": ("STRING", {"default": resolve_model_dir(create=True), "multiline": False}),
                "device_ids": ("STRING", {"default": "0", "multiline": False}),
                "debug": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = tuple(item for _index in range(MSS_MAX_STEMS) for item in ("AUDIO", "STRING"))
    RETURN_NAMES = tuple(
        name
        for index in range(MSS_MAX_STEMS)
        for name in (f"stem_{index + 1} (Audio)", f"stem_{index + 1} (String)")
    )
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
            max_stems=self.MAX_STEMS,
            params=params,
            model_dir=model_dir,
            download_missing=download_missing,
            source=source,
            device=device,
            device_ids_raw=device_ids,
            use_tta=use_tta,
            debug=debug,
        )


class PymssMssSeparate(_SeparateBase):
    MODEL_KIND = "mss"
    MAX_STEMS = MSS_MAX_STEMS
    PARAM_TYPE = MSS_PARAMS_TYPE


class PymssCustomMssSeparate:
    MODEL_KIND = "custom"
    MAX_STEMS = MSS_MAX_STEMS
    PARAM_TYPE = MSS_PARAMS_TYPE

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "model_name": (custom_model_names(),),
                "model_type": (
                    [
                        "mel_band_roformer",
                        "bs_roformer",
                        "bs_roformer_hyperace",
                        "mdx23c",
                        "htdemucs",
                        "apollo",
                        "bandit",
                        "bandit_v2",
                        "scnet",
                    ],
                    {"default": "mel_band_roformer"},
                ),
                "device": (["auto", "cpu", "cuda", "mps", "mlx"], {"default": "auto"}),
            },
            "optional": {
                "params": (MSS_PARAMS_TYPE,),
                "model_dir": ("STRING", {"default": custom_model_dir(), "multiline": False}),
                "device_ids": ("STRING", {"default": "0", "multiline": False}),
                "debug": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = tuple(item for _index in range(MSS_MAX_STEMS) for item in ("AUDIO", "STRING"))
    RETURN_NAMES = tuple(
        name
        for index in range(MSS_MAX_STEMS)
        for name in (f"stem_{index + 1} (Audio)", f"stem_{index + 1} (String)")
    )
    FUNCTION = "separate"
    CATEGORY = CATEGORY

    def separate(
        self,
        audio,
        model_name,
        model_type,
        device,
        params=None,
        model_dir="Default/custom",
        device_ids="0",
        debug=False,
    ):
        params = dict(params or {})
        use_tta = bool(params.pop("enable_tta", False))
        return separate_custom_audio(
            audio=audio,
            model_name=model_name,
            model_type=model_type,
            max_stems=self.MAX_STEMS,
            params=params,
            model_dir=model_dir,
            device=device,
            device_ids_raw=device_ids,
            use_tta=use_tta,
            debug=debug,
        )


class PymssVrSeparate(_SeparateBase):
    MODEL_KIND = "vr"
    MAX_STEMS = VR_MAX_STEMS
    PARAM_TYPE = VR_PARAMS_TYPE
    RETURN_TYPES = tuple(item for _index in range(VR_MAX_STEMS) for item in ("AUDIO", "STRING"))
    RETURN_NAMES = tuple(
        name
        for index in range(VR_MAX_STEMS)
        for name in (f"stem_{index + 1} (Audio)", f"stem_{index + 1} (String)")
    )
