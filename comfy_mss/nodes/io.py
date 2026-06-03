import os

import folder_paths

from ..constants import AUDIO_EXTENSIONS, CATEGORY, ENSEMBLE_TYPES
from ..utils.audio import audio_name_from_path, load_audio_paths, save_comfy_audio, scan_audio_folder
from ..utils.ensemble import ensemble_audio_inputs


def parse_weight(value, index):
    text = str(value or "").strip()
    if not text:
        return 1.0
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"weight_{index} must be a number.") from exc


class PymssLoadAudio:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        os.makedirs(input_dir, exist_ok=True)
        files = [file for file in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, file))]
        files = folder_paths.filter_files_content_types(files, ["audio", "video"])
        return {
            "required": {
                "audio": (sorted(files),),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "audio_name")
    FUNCTION = "load"
    CATEGORY = CATEGORY

    def load(self, audio):
        from comfy_extras.nodes_audio import load

        audio_path = folder_paths.get_annotated_filepath(audio)
        waveform, sample_rate = load(audio_path)
        comfy_audio = {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
        return (comfy_audio, audio_name_from_path(audio_path))


class PymssLoadAudioBatch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "", "multiline": False}),
                "recursive": ("BOOLEAN", {"default": False}),
                "sort_files": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "audio_name")
    OUTPUT_IS_LIST = (True, True)
    FUNCTION = "load"
    CATEGORY = CATEGORY

    def load(self, folder, recursive, sort_files):
        paths = scan_audio_folder(folder, recursive, AUDIO_EXTENSIONS)
        audios, audio_names = load_audio_paths(
            paths=paths,
            sample_rate=0,
            mono=False,
            sort_files=bool(sort_files),
            limit=0,
        )
        return (audios, audio_names)


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
            "ensemble_type": (list(ENSEMBLE_TYPES), {"default": "avg_wave"}),
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


class PymssSaveAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "output_format": (["wav", "flac", "mp3"], {"default": "wav"}),
                "output_folder": ("STRING", {"default": "Default", "multiline": False}),
                "sample_rate": (["32000", "44100", "48000"], {"default": "44100"}),
                "wav_bit_depth": (["PCM_24", "PCM_16", "FLOAT"], {"default": "FLOAT"}),
                "flac_bit_depth": (["PCM_16", "PCM_24"], {"default": "PCM_24"}),
                "mp3_bit_rate": (["128k", "192k", "256k", "320k"], {"default": "320k"}),
            },
            "optional": {
                "filename": ("STRING", {"default": "", "multiline": False, "forceInput": True}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def save(
        self,
        audio,
        output_format,
        output_folder,
        sample_rate,
        wav_bit_depth,
        flac_bit_depth,
        mp3_bit_rate,
        filename="",
    ):
        saved_paths = save_comfy_audio(
            audio,
            output_folder,
            output_format,
            sample_rate,
            wav_bit_depth,
            flac_bit_depth,
            mp3_bit_rate,
            filename,
        )
        return {"ui": {"saved_paths": saved_paths}}
