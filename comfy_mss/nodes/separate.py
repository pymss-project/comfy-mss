import comfy.utils
import numpy as np
import torch

from pymss import MSSeparator
from ..constants import CATEGORY, MSS_MAX_STEMS, MSS_PARAMS_TYPE, VR_MAX_STEMS, VR_PARAMS_TYPE
from ..paths import resolve_model_dir
from ..services.catalog import (
    clean_model_display_name,
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


def collect_stem_outputs(results, stems, mix, sample_rate, source_path):
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
    return outputs, stem_outputs


def pair_stem_outputs(outputs, stem_outputs, max_stems):
    paired_outputs = []
    for index in range(max_stems):
        paired_outputs.append(outputs[index] if index < len(outputs) else None)
        paired_outputs.append(stem_outputs[index] if index < len(stem_outputs) else "")
    return tuple(paired_outputs)


def stem_return_types(max_stems):
    return tuple(item for _index in range(max_stems) for item in ("AUDIO", "STRING"))


def stem_return_names(max_stems):
    return tuple(
        name for index in range(max_stems) for name in (f"stem_{index + 1} (Audio)", f"stem_{index + 1} (String)")
    )


def params_and_tta(params):
    params = dict(params or {})
    return params, bool(params.pop("enable_tta", False))


def common_separator_kwargs(stems, params, device, device_ids_raw, use_tta, debug):
    return {
        "device": device,
        "device_ids": device_ids(device_ids_raw),
        "output_format": "wav",
        "use_tta": bool(use_tta),
        "store_dirs": {stem: "" for stem in stems},
        "debug": bool(debug),
        "progress_callback": make_comfy_progress_callback(),
        "inference_params": params or {},
    }


def run_separation(audio, stems, separator_factory):
    mix, sample_rate = audio_to_numpy(audio)
    source_path = audio_source_path(audio)

    with torch.inference_mode(False):
        with separator_factory() as separator:
            results = separator.separate(mix, pbar=True, stems=stems)

    return collect_stem_outputs(results, stems, mix, sample_rate, source_path)


def separate_model_audio(
    audio, model_name, model_kind, params, download_missing, source, device, device_ids_raw, use_tta, debug
):
    model_name = clean_model_display_name(model_name)
    stems = stem_names(model_name, model_kind)
    separator_kwargs = common_separator_kwargs(stems, params, device, device_ids_raw, use_tta, debug)

    def separator_factory():
        return MSSeparator.from_model_name(
            model_name,
            model_dir=resolve_model_dir(),
            download=bool(download_missing),
            source=source,
            **separator_kwargs,
        )

    return run_separation(audio, stems, separator_factory)


def separate_custom_model_audio(audio, model_name, model_type, params, device, device_ids_raw, use_tta, debug):
    entry = custom_model_entry(model_name)
    if entry is None:
        raise FileNotFoundError(f"custom model not found or missing yaml: {model_name}")

    stems = custom_stem_names(model_name)
    separator_kwargs = common_separator_kwargs(stems, params, device, device_ids_raw, use_tta, debug)

    def separator_factory():
        return MSSeparator(
            model_type=model_type,
            model_path=entry["model_path"],
            config_path=entry["config_path"],
            **separator_kwargs,
        )

    return run_separation(audio, stems, separator_factory)


def separate_audio(
    audio,
    model_name,
    model_kind,
    max_stems,
    params,
    download_missing,
    source,
    device,
    device_ids_raw,
    use_tta,
    debug,
):
    outputs, stem_outputs = separate_model_audio(
        audio=audio,
        model_name=model_name,
        model_kind=model_kind,
        params=params,
        download_missing=download_missing,
        source=source,
        device=device,
        device_ids_raw=device_ids_raw,
        use_tta=use_tta,
        debug=debug,
    )
    return pair_stem_outputs(outputs, stem_outputs, max_stems)


def separate_audio_list(
    audio,
    model_name,
    model_kind,
    params,
    download_missing,
    source,
    device,
    device_ids_raw,
    use_tta,
    debug,
):
    return separate_model_audio(
        audio=audio,
        model_name=model_name,
        model_kind=model_kind,
        params=params,
        download_missing=download_missing,
        source=source,
        device=device,
        device_ids_raw=device_ids_raw,
        use_tta=use_tta,
        debug=debug,
    )


def separate_custom_audio(audio, model_name, model_type, max_stems, params, device, device_ids_raw, use_tta, debug):
    outputs, stem_outputs = separate_custom_model_audio(
        audio=audio,
        model_name=model_name,
        model_type=model_type,
        params=params,
        device=device,
        device_ids_raw=device_ids_raw,
        use_tta=use_tta,
        debug=debug,
    )
    return pair_stem_outputs(outputs, stem_outputs, max_stems)


def separate_custom_audio_list(audio, model_name, model_type, params, device, device_ids_raw, use_tta, debug):
    return separate_custom_model_audio(
        audio=audio,
        model_name=model_name,
        model_type=model_type,
        params=params,
        device=device,
        device_ids_raw=device_ids_raw,
        use_tta=use_tta,
        debug=debug,
    )


class _SeparateOutputBase:
    MAX_STEMS = MSS_MAX_STEMS
    PARAM_TYPE = "*"
    RETURNS_LIST = False
    RETURN_TYPES = stem_return_types(MSS_MAX_STEMS)
    RETURN_NAMES = stem_return_names(MSS_MAX_STEMS)
    FUNCTION = "separate"
    CATEGORY = CATEGORY

    def format_outputs(self, outputs, stem_outputs):
        if self.RETURNS_LIST:
            return outputs, stem_outputs
        return pair_stem_outputs(outputs, stem_outputs, self.MAX_STEMS)


class _SeparateBase(_SeparateOutputBase):
    MODEL_KIND = "all"

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
                "device_ids": ("STRING", {"default": "0", "multiline": False}),
                "debug": ("BOOLEAN", {"default": False}),
            },
        }

    def separate(
        self,
        audio,
        model_name,
        device,
        download_missing,
        source,
        params=None,
        device_ids="0",
        debug=False,
    ):
        params, use_tta = params_and_tta(params)
        outputs, stem_outputs = separate_model_audio(
            audio=audio,
            model_name=model_name,
            model_kind=self.MODEL_KIND,
            params=params,
            download_missing=download_missing,
            source=source,
            device=device,
            device_ids_raw=device_ids,
            use_tta=use_tta,
            debug=debug,
        )
        return self.format_outputs(outputs, stem_outputs)


class PymssMssSeparate(_SeparateBase):
    MODEL_KIND = "mss"
    MAX_STEMS = MSS_MAX_STEMS
    PARAM_TYPE = MSS_PARAMS_TYPE


class _SeparateListBase(_SeparateBase):
    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audios", "stem_names")
    OUTPUT_IS_LIST = (True, True)
    RETURNS_LIST = True


class PymssMssSeparateList(_SeparateListBase):
    MODEL_KIND = "mss"
    MAX_STEMS = MSS_MAX_STEMS
    PARAM_TYPE = MSS_PARAMS_TYPE


class _CustomSeparateBase(_SeparateOutputBase):
    MODEL_KIND = "custom"
    PARAM_TYPE = MSS_PARAMS_TYPE
    MODEL_TYPES = [
        "mel_band_roformer",
        "bs_roformer",
        "bs_roformer_hyperace",
        "mdx23c",
        "htdemucs",
        "apollo",
        "bandit",
        "bandit_v2",
        "scnet",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "model_name": (custom_model_names(),),
                "model_type": (cls.MODEL_TYPES, {"default": "mel_band_roformer"}),
                "device": (["auto", "cpu", "cuda", "mps", "mlx"], {"default": "auto"}),
            },
            "optional": {
                "params": (cls.PARAM_TYPE,),
                "device_ids": ("STRING", {"default": "0", "multiline": False}),
                "debug": ("BOOLEAN", {"default": False}),
            },
        }

    def separate(
        self,
        audio,
        model_name,
        model_type,
        device,
        params=None,
        device_ids="0",
        debug=False,
    ):
        params, use_tta = params_and_tta(params)
        outputs, stem_outputs = separate_custom_model_audio(
            audio=audio,
            model_name=model_name,
            model_type=model_type,
            params=params,
            device=device,
            device_ids_raw=device_ids,
            use_tta=use_tta,
            debug=debug,
        )
        return self.format_outputs(outputs, stem_outputs)


class PymssCustomMssSeparate(_CustomSeparateBase):
    pass


class PymssCustomMssSeparateList(_CustomSeparateBase):
    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audios", "stem_names")
    OUTPUT_IS_LIST = (True, True)
    RETURNS_LIST = True


class PymssVrSeparate(_SeparateBase):
    MODEL_KIND = "vr"
    MAX_STEMS = VR_MAX_STEMS
    PARAM_TYPE = VR_PARAMS_TYPE
    RETURN_TYPES = stem_return_types(VR_MAX_STEMS)
    RETURN_NAMES = stem_return_names(VR_MAX_STEMS)


class PymssVrSeparateList(_SeparateListBase):
    MODEL_KIND = "vr"
    MAX_STEMS = VR_MAX_STEMS
    PARAM_TYPE = VR_PARAMS_TYPE
