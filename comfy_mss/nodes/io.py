import os

import folder_paths

from ..constants import AUDIO_EXTENSIONS, CATEGORY
from ..utils.audio import audio_name_from_path, load_audio_paths, save_comfy_audio, scan_audio_folder


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


class PymssSaveAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "output_format": (["wav", "flac", "mp3"], {"default": "wav"}),
                "output_folder": ("STRING", {"default": "Default", "multiline": False}),
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
