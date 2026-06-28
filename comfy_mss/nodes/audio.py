from pymss.ensemble import ENSEMBLE_ALGORITHMS

from ..constants import CATEGORY
from ..utils.ensemble import ensemble_audio_inputs


def parse_weight(value, index):
    text = str(value or "").strip()
    if not text:
        return 1.0
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"weight_{index} must be a number.") from exc


class PymssAudioInvertPhase:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "a": ("AUDIO",),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("-a",)
    FUNCTION = "invert"
    CATEGORY = CATEGORY

    def invert(self, a):
        if a is None:
            raise ValueError("audio input a is required.")
        audio = dict(a)
        audio["waveform"] = -a["waveform"]
        return (audio,)


class PymssAudioNormalize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "normalize"
    CATEGORY = CATEGORY

    def normalize(self, audio):
        if audio is None:
            raise ValueError("audio input is required.")
        result = dict(audio)
        waveform = audio["waveform"].clone()
        peak = waveform.abs().amax()
        if peak > 1.0:
            waveform = waveform * (0.999 / peak)
        result["waveform"] = waveform
        return (result,)


class PymssAudioEnsemble:
    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "input_count": ([str(value) for value in range(2, 11)], {"default": "2"}),
            "ensemble_type": (list(ENSEMBLE_ALGORITHMS), {"default": "avg_wave"}),
        }
        for index in range(1, 11):
            required[f"weight_{index}"] = ("STRING", {"default": "1", "multiline": False})

        return {
            "required": required,
            "optional": {f"audio_{index}": ("AUDIO",) for index in range(1, 11)},
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "ensemble"
    CATEGORY = CATEGORY

    def ensemble(self, input_count, ensemble_type, **kwargs):
        input_count = int(input_count)
        audios = [kwargs.get(f"audio_{index}") for index in range(1, input_count + 1)]
        if any(audio is None for audio in audios):
            missing = [f"audio_{index}" for index, audio in enumerate(audios, start=1) if audio is None]
            raise ValueError(f"Missing required audio inputs: {', '.join(missing)}")
        weights = [parse_weight(kwargs.get(f"weight_{index}", "1"), index) for index in range(1, input_count + 1)]
        return (ensemble_audio_inputs(audios, weights, ensemble_type),)
