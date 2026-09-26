import hashlib
import ntpath
import os
import posixpath

import folder_paths

from ..constants import CATEGORY
from ..utils.audio import audio_name_from_path, save_comfy_audio


def resolve_input_audio_path(audio):
    value = str(audio or "").strip()
    normalized = value.replace("\\", "/")
    path_value = (
        normalized.rsplit("[", 1)[0].strip()
        if normalized.endswith(("[input]", "[output]", "[temp]"))
        else normalized
    )
    if not value or ntpath.isabs(path_value) or posixpath.isabs(path_value) or ".." in path_value.split("/"):
        raise ValueError("audio path must be relative to the ComfyUI input directory.")

    input_dir = os.path.realpath(folder_paths.get_input_directory())
    audio_path = os.path.realpath(folder_paths.get_annotated_filepath(value))
    input_key = os.path.normcase(input_dir)
    audio_key = os.path.normcase(audio_path)
    try:
        inside_input = os.path.commonpath((input_key, audio_key)) == input_key
    except ValueError:
        inside_input = False
    if not inside_input:
        raise ValueError("audio path must stay inside the ComfyUI input directory.")
    return audio_path


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
            },
            "optional": {
                # Metadata for downstream hosts (pymss DAG / pymss-studio): when the
                # audio file is absent at run time, the runtime input mapped to this
                # name feeds the node. Unused inside ComfyUI itself, where the audio
                # combo is always resolved locally.
                "input_name": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "audio_name")
    FUNCTION = "load"
    CATEGORY = CATEGORY

    def load(self, audio, input_name=""):
        from comfy_extras.nodes_audio import load

        audio_path = resolve_input_audio_path(audio)
        waveform, sample_rate = load(audio_path)
        comfy_audio = {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
        return (comfy_audio, audio_name_from_path(audio_path))

    @classmethod
    def VALIDATE_INPUTS(cls, audio, input_name=""):
        try:
            audio_path = resolve_input_audio_path(audio)
        except (OSError, TypeError, ValueError):
            return "Invalid audio file path."
        if not os.path.isfile(audio_path):
            return f"Invalid audio file: {audio}"
        return True

    @classmethod
    def IS_CHANGED(cls, audio, input_name=""):
        audio_path = resolve_input_audio_path(audio)
        digest = hashlib.sha256()
        with open(audio_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class PymssSaveAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "output_format": (["wav", "flac", "mp3"], {"default": "wav"}),
                "sample_rate": (["32000", "44100", "48000"], {"default": "44100"}),
                "wav_bit_depth": (["PCM_16", "PCM_24", "FLOAT"], {"default": "FLOAT"}),
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
        sample_rate,
        wav_bit_depth,
        flac_bit_depth,
        mp3_bit_rate,
        filename="",
    ):
        saved_paths = save_comfy_audio(
            audio,
            output_format,
            sample_rate,
            wav_bit_depth,
            flac_bit_depth,
            mp3_bit_rate,
            filename,
        )
        return {"ui": {"saved_paths": saved_paths}}
