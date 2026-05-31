from ..constants import CATEGORY, MSS_PARAMS_TYPE, VR_PARAMS_TYPE


def clean_none(params):
    return {key: value for key, value in params.items() if value is not None}


def parse_default_int(value, name):
    text = str(value or "").strip()
    if not text or text.lower() == "default":
        return None
    try:
        parsed = int(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be Default or an integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be Default or a positive integer.")
    return parsed


class PymssMssParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 128, "step": 1}),
                "overlap_size": ("STRING", {"default": "Default", "multiline": False}),
                "chunk_size": ("STRING", {"default": "Default", "multiline": False}),
                "normalize": ("BOOLEAN", {"default": False}),
                "enable_tta": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = (MSS_PARAMS_TYPE,)
    RETURN_NAMES = ("mss_params",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, batch_size, overlap_size, chunk_size, normalize, enable_tta):
        params = clean_none(
            {
                "batch_size": batch_size,
                "overlap_size": parse_default_int(overlap_size, "overlap_size"),
                "chunk_size": parse_default_int(chunk_size, "chunk_size"),
            }
        )
        if normalize:
            params["normalize"] = True
        params["enable_tta"] = bool(enable_tta)
        return (params,)


class PymssVrParams:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 128, "step": 1}),
                "window_size": ("INT", {"default": 512, "min": 128, "max": 4096, "step": 128}),
                "aggression": ("INT", {"default": 5, "min": 0, "max": 100, "step": 1}),
                "enable_tta": ("BOOLEAN", {"default": False}),
                "high_end_process": ("BOOLEAN", {"default": False}),
                "enable_post_process": ("BOOLEAN", {"default": False}),
                "post_process_threshold": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01}),
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
        high_end_process,
        enable_post_process,
        post_process_threshold,
    ):
        params = {
            "batch_size": batch_size,
            "window_size": window_size,
            "aggression": aggression,
            "enable_tta": bool(enable_tta),
            "enable_post_process": bool(enable_post_process),
            "post_process_threshold": post_process_threshold,
            "high_end_process": bool(high_end_process),
            "use_amp": True,
        }
        return (clean_none(params),)
