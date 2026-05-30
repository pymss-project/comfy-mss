import json

from .constants import CATEGORY, MSS_PARAMS_TYPE, VR_PARAMS_TYPE


def parse_extra_params(raw):
    raw = str(raw or "").strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("extra_params_json must be a JSON object.")
    return parsed


def clean_none(params):
    return {key: value for key, value in params.items() if value is not None}


class PymssMssParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 128, "step": 1}),
                "overlap_size": ("INT", {"default": 24000, "min": 0, "max": 2147483647, "step": 1000}),
                "chunk_size": ("INT", {"default": 480000, "min": 1, "max": 2147483647, "step": 1000}),
                "normalize": ("BOOLEAN", {"default": False}),
                "enable_tta": ("BOOLEAN", {"default": False}),
                "extra_params_json": ("STRING", {"default": "{}", "multiline": True}),
            }
        }

    RETURN_TYPES = (MSS_PARAMS_TYPE,)
    RETURN_NAMES = ("mss_params",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, batch_size, overlap_size, chunk_size, normalize, enable_tta, extra_params_json):
        params = {
            "batch_size": batch_size,
            "overlap_size": overlap_size,
            "chunk_size": chunk_size,
            "normalize": bool(normalize),
            "enable_tta": bool(enable_tta),
        }
        params.update(parse_extra_params(extra_params_json))
        return (params,)


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
        params.update(parse_extra_params(extra_params_json))
        return (clean_none(params),)
