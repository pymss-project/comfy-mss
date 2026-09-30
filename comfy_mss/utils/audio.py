import os
import re
import time

import folder_paths
import numpy as np
import torch

from pymss.audio_io import load_audio, save_audio


SUPPORTED_OUTPUT_FORMATS = {"wav", "flac", "mp3"}


def audio_to_numpy(audio):
    if audio is None:
        raise ValueError("audio input is required.")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim != 3:
        raise ValueError(f"Expected ComfyUI AUDIO waveform [batch, channels, samples], got shape {tuple(waveform.shape)}.")
    if waveform.shape[0] != 1:
        raise ValueError("pymss separation currently expects a single audio item. Split batches before this node.")
    return waveform[0].detach().cpu().numpy().astype(np.float32, copy=False), sample_rate


def numpy_to_audio(value, sample_rate, stem_name=None, source_path=None):
    array = np.asarray(value, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    elif array.ndim == 2:
        # MSSeparator.separate() returns sample-major [samples, channels].
        array = array.T
    else:
        raise ValueError(f"Unsupported separated stem shape: {array.shape}")
    audio = {"waveform": torch.from_numpy(np.ascontiguousarray(array)).unsqueeze(0), "sample_rate": int(sample_rate)}
    return attach_audio_metadata(audio, source_path=source_path, stem_name=stem_name)


def audio_batch_to_numpy(audio):
    if audio is None:
        raise ValueError("audio input is required.")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim != 3:
        raise ValueError(f"Expected ComfyUI AUDIO waveform [batch, channels, samples], got shape {tuple(waveform.shape)}.")
    if waveform.shape[0] < 1:
        raise ValueError("audio batch must contain at least one item.")
    if waveform.shape[1] < 1:
        raise ValueError("audio must contain at least one channel.")
    if waveform.shape[2] < 1:
        raise ValueError("audio must contain at least one sample.")
    if sample_rate <= 0:
        raise ValueError("sample rate must be a positive integer.")
    return waveform.detach().cpu().numpy().astype(np.float32, copy=False), sample_rate


def numpy_to_comfy_audio(audio, sample_rate):
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    elif array.ndim != 2:
        raise ValueError(f"Unsupported loaded audio shape: {array.shape}")
    return {"waveform": torch.from_numpy(np.ascontiguousarray(array)).unsqueeze(0), "sample_rate": int(sample_rate)}


def resample_audio(waveform, source_sample_rate, target_sample_rate):
    source_sample_rate = int(source_sample_rate)
    target_sample_rate = int(target_sample_rate)
    array = np.asarray(waveform, dtype=np.float32)
    if source_sample_rate <= 0 or target_sample_rate <= 0:
        raise ValueError("sample rates must be positive integers.")
    if source_sample_rate == target_sample_rate or array.size == 0:
        return array, source_sample_rate

    # Match pymss' graph execution path. pymss guarantees librosa as a
    # dependency, while torchaudio is not part of pymss' public requirements.
    from pymss.plugins.builtins import resample

    converted = resample(array, source_sample_rate, target_sample_rate)
    return np.asarray(converted, dtype=np.float32), target_sample_rate


def attach_audio_metadata(audio, source_path=None, stem_name=None):
    audio = dict(audio)
    if source_path:
        audio["pymss_source_path"] = str(source_path)
    if stem_name:
        audio["pymss_stem_name"] = str(stem_name)
    return audio


def audio_name_from_path(path):
    return safe_filename_part(os.path.splitext(os.path.basename(str(path or "")))[0], "")


def resolve_save_dir():
    save_dir = folder_paths.get_output_directory()
    save_dir = os.path.abspath(os.path.expanduser(os.path.expandvars(save_dir)))
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def safe_filename_part(value, fallback):
    value = str(value or "").strip() or fallback
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.strip(" .")
    return value or fallback


def source_stem_from_path(source_path):
    source_path = str(source_path or "").strip().strip('"')
    if not source_path:
        return ""
    stem = os.path.splitext(os.path.basename(source_path))[0]
    return safe_filename_part(stem, "")


def audio_source_path(audio):
    if not isinstance(audio, dict):
        return ""
    return str(audio.get("pymss_source_path") or audio.get("source_path") or "")


def audio_stem_name(audio):
    if not isinstance(audio, dict):
        return ""
    stem = audio.get("pymss_stem_name") or audio.get("stem_name")
    return safe_filename_part(stem, "") if stem else ""


def timestamp_audio_name():
    return f"audio_{time.strftime('%Y%m%d_%H%M%S')}"


def make_audio_file_name(filename, audio, batch_index=None):
    file_name = safe_filename_part(filename, "") if filename else ""
    if not file_name:
        file_name = timestamp_audio_name()
    if batch_index is not None:
        file_name = f"{file_name}_{batch_index:05d}"
    return safe_filename_part(file_name, "audio")


def reserve_unique_output_path(save_dir, file_name, output_format):
    counter = 0
    while True:
        suffix = "" if counter == 0 else f"_{counter:05d}"
        candidate = os.path.join(save_dir, f"{file_name}{suffix}.{output_format}")
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        except FileExistsError:
            counter += 1
            continue
        else:
            os.close(descriptor)
            return candidate


def resample_audio_batch(waveform, source_sample_rate, target_sample_rate):
    target_sample_rate = int(target_sample_rate)
    source_sample_rate = int(source_sample_rate)
    if source_sample_rate <= 0 or target_sample_rate <= 0:
        raise ValueError("sample rates must be positive integers.")
    if target_sample_rate == source_sample_rate:
        return waveform, source_sample_rate

    import torchaudio

    tensor = torch.from_numpy(np.ascontiguousarray(waveform))
    tensor = torchaudio.functional.resample(tensor, source_sample_rate, target_sample_rate)
    return tensor.numpy().astype(np.float32, copy=False), target_sample_rate


def save_comfy_audio(
    audio,
    output_format,
    target_sample_rate,
    wav_bit_depth,
    flac_bit_depth,
    mp3_bit_rate,
    filename="",
):
    output_format = str(output_format or "").strip().lower()
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported audio output format: {output_format or '<empty>'}")
    waveform, sample_rate = audio_batch_to_numpy(audio)
    if output_format == "mp3" and waveform.shape[1] > 2:
        raise ValueError("MP3 export supports mono or stereo audio only.")
    waveform, sample_rate = resample_audio_batch(waveform, sample_rate, target_sample_rate)
    save_dir = resolve_save_dir()
    audio_params = {
        "wav_bit_depth": wav_bit_depth,
        "flac_bit_depth": flac_bit_depth,
        "mp3_bit_rate": mp3_bit_rate,
    }

    saved_paths = []
    batch_size = int(waveform.shape[0])
    for index, item in enumerate(waveform):
        # ComfyUI AUDIO is [channels, samples]; pymss/av saving expects [samples, channels].
        audio_array = np.ascontiguousarray(item.T)
        batch_index = None if batch_size == 1 else index
        file_name = make_audio_file_name(filename, audio, batch_index)
        path = reserve_unique_output_path(save_dir, file_name, output_format)
        try:
            save_audio(path, audio_array, sample_rate, output_format, audio_params)
        except BaseException:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        saved_paths.append(path)
    return saved_paths
