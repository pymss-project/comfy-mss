import json

from .audio_utils import (
    load_audio_paths,
    match_audio_for_binary_op,
    parse_audio_file_list,
    parse_extensions,
    save_comfy_audio,
    scan_audio_folder,
)
from .catalog import model_catalog
from .constants import AUDIO_EXTENSIONS, CATEGORY


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
        return (json.dumps(model_catalog(model_kind), ensure_ascii=False, indent=2),)


class PymssLoadAudioBatch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_mode": (["files", "folder"], {"default": "files"}),
                "audio_files": ("STRING", {"default": "", "multiline": True}),
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
        exts = parse_extensions(extensions)
        if input_mode == "folder":
            paths = scan_audio_folder(folder, recursive, exts)
        else:
            paths = parse_audio_file_list(audio_files)

        audios, loaded_paths = load_audio_paths(
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
        waveform_a, waveform_b, sample_rate = match_audio_for_binary_op(audio_a, audio_b)
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
        saved_paths = save_comfy_audio(
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
