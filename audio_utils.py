import os
import re

import folder_paths
import numpy as np
import torch

from .constants import AUDIO_EXTENSIONS


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


def numpy_to_audio(value, sample_rate):
    array = np.asarray(value, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    elif array.ndim == 2:
        # pymss returns most stems as [samples, channels]. ComfyUI wants [channels, samples].
        if array.shape[0] > array.shape[1] and array.shape[1] <= 8:
            array = array.T
    else:
        raise ValueError(f"Unsupported separated stem shape: {array.shape}")
    return {"waveform": torch.from_numpy(np.ascontiguousarray(array)).unsqueeze(0), "sample_rate": int(sample_rate)}


def audio_batch_to_numpy(audio):
    if audio is None:
        raise ValueError("audio input is required.")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if waveform.ndim != 3:
        raise ValueError(f"Expected ComfyUI AUDIO waveform [batch, channels, samples], got shape {tuple(waveform.shape)}.")
    return waveform.detach().cpu().numpy().astype(np.float32, copy=False), sample_rate


def match_audio_for_binary_op(audio_a, audio_b):
    import torchaudio

    if audio_a is None or audio_b is None:
        raise ValueError("Both audio inputs are required.")

    waveform_a = audio_a["waveform"].detach().cpu().float()
    waveform_b = audio_b["waveform"].detach().cpu().float()
    sample_rate_a = int(audio_a["sample_rate"])
    sample_rate_b = int(audio_b["sample_rate"])

    if waveform_a.ndim != 3 or waveform_b.ndim != 3:
        raise ValueError("Expected ComfyUI AUDIO waveforms with shape [batch, channels, samples].")

    if sample_rate_a != sample_rate_b:
        waveform_b = torchaudio.functional.resample(waveform_b, sample_rate_b, sample_rate_a)

    batch_size = min(waveform_a.shape[0], waveform_b.shape[0])
    channels = min(waveform_a.shape[1], waveform_b.shape[1])
    length = min(waveform_a.shape[2], waveform_b.shape[2])
    if batch_size <= 0 or channels <= 0 or length <= 0:
        raise ValueError("Audio inputs must have non-empty batch, channel, and sample dimensions.")

    return (
        waveform_a[:batch_size, :channels, :length],
        waveform_b[:batch_size, :channels, :length],
        sample_rate_a,
    )


def numpy_to_comfy_audio(audio, sample_rate):
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    elif array.ndim != 2:
        raise ValueError(f"Unsupported loaded audio shape: {array.shape}")
    return {"waveform": torch.from_numpy(np.ascontiguousarray(array)).unsqueeze(0), "sample_rate": int(sample_rate)}


def resolve_input_path(path):
    path = str(path or "").strip().strip('"')
    if not path:
        return None
    path = os.path.expanduser(os.path.expandvars(path))
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(folder_paths.get_input_directory(), path))


def parse_audio_file_list(audio_files):
    paths = []
    for line in str(audio_files or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        resolved = resolve_input_path(line)
        if resolved is not None:
            paths.append(resolved)
    return paths


def parse_extensions(extensions):
    parsed = []
    for item in re.split(r"[,;\s]+", str(extensions or "")):
        item = item.strip().lower()
        if not item:
            continue
        parsed.append(item if item.startswith(".") else f".{item}")
    return tuple(parsed or AUDIO_EXTENSIONS)


def scan_audio_folder(folder, recursive, extensions):
    folder = resolve_input_path(folder)
    if folder is None:
        raise ValueError("folder is required when input_mode is folder.")
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"folder does not exist: {folder}")

    matches = []
    extensions = tuple(ext.lower() for ext in extensions)
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for filename in files:
                if filename.lower().endswith(extensions):
                    matches.append(os.path.join(root, filename))
    else:
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path) and filename.lower().endswith(extensions):
                matches.append(path)
    return matches


def load_audio_paths(paths, sample_rate, mono, sort_files, limit):
    from pymss.audio_io import load_audio

    unique_paths = []
    seen = set()
    for path in paths:
        path = os.path.abspath(path)
        if path in seen:
            continue
        seen.add(path)
        unique_paths.append(path)

    if sort_files:
        unique_paths.sort(key=lambda item: item.lower())
    if limit > 0:
        unique_paths = unique_paths[:limit]
    if not unique_paths:
        raise ValueError("No audio files were found.")

    audios = []
    for path in unique_paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"audio file does not exist: {path}")
        audio, sr = load_audio(path, sr=None if sample_rate <= 0 else sample_rate, mono=mono)
        audios.append(numpy_to_comfy_audio(audio, sr))
    return audios, unique_paths


def resolve_save_dir(output_folder):
    output_folder = str(output_folder or "").strip()
    if not output_folder:
        save_dir = folder_paths.get_output_directory()
    elif os.path.isabs(output_folder):
        save_dir = output_folder
    else:
        save_dir = os.path.join(folder_paths.get_output_directory(), output_folder)
    save_dir = os.path.abspath(os.path.expanduser(os.path.expandvars(save_dir)))
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def safe_filename_part(value, fallback):
    value = str(value or "").strip() or fallback
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.strip(" .")
    return value or fallback


def save_comfy_audio(audio, output_folder, filename_prefix, output_format, wav_bit_depth, flac_bit_depth, mp3_bit_rate, m4a_bit_rate, m4a_codec, m4a_aac_at_quality):
    from pymss.audio_io import save_audio

    waveform, sample_rate = audio_batch_to_numpy(audio)
    save_dir = resolve_save_dir(output_folder)
    prefix = safe_filename_part(filename_prefix, "ComfyUI")
    output_format = output_format.lower()
    audio_params = {
        "wav_bit_depth": wav_bit_depth,
        "flac_bit_depth": flac_bit_depth,
        "mp3_bit_rate": mp3_bit_rate,
        "m4a_bit_rate": m4a_bit_rate,
        "m4a_codec": m4a_codec,
        "m4a_aac_at_quality": m4a_aac_at_quality,
    }

    saved_paths = []
    batch_size = int(waveform.shape[0])
    for index, item in enumerate(waveform):
        # ComfyUI AUDIO is [channels, samples]; pymss/av saving expects [samples, channels].
        audio_array = np.ascontiguousarray(item.T)
        suffix = "" if batch_size == 1 else f"_{index:05d}"
        file_name = f"{prefix}{suffix}"
        path = os.path.join(save_dir, f"{file_name}.{output_format}")
        save_audio(path, audio_array, sample_rate, output_format, audio_params)
        saved_paths.append(path)
    return saved_paths
