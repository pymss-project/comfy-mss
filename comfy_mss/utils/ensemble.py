import numpy as np
import torch
from pymss.ensemble import average_waveforms

from .audio import resample_audio


def align_audio_inputs(audios):
    if len(audios) < 2:
        raise ValueError("At least two audio inputs are required.")

    sample_rate = int(audios[0]["sample_rate"])
    waveforms = []
    for index, audio in enumerate(audios, start=1):
        if audio is None:
            raise ValueError(f"audio_{index} is required.")
        waveform = audio["waveform"].detach().cpu().float()
        if waveform.ndim != 3:
            raise ValueError(f"audio_{index} must be a ComfyUI AUDIO waveform with shape [batch, channels, samples].")
        source_sample_rate = int(audio["sample_rate"])
        if source_sample_rate != sample_rate:
            resampled, _sample_rate = resample_audio(waveform.numpy(), source_sample_rate, sample_rate)
            waveform = torch.from_numpy(np.ascontiguousarray(resampled))
        waveforms.append(waveform)

    batch_size = max(item.shape[0] for item in waveforms)
    channels = max(item.shape[1] for item in waveforms)
    length = min(item.shape[2] for item in waveforms)
    if batch_size <= 0 or channels <= 0 or length <= 0:
        raise ValueError("Audio inputs must have non-empty batch, channel, and sample dimensions.")

    aligned = []
    for index, waveform in enumerate(waveforms, start=1):
        if waveform.shape[0] == 1 and batch_size > 1:
            waveform = waveform.repeat(batch_size, 1, 1)
        elif waveform.shape[0] != batch_size:
            raise ValueError(
                f"audio_{index} has batch size {waveform.shape[0]}, expected 1 or {batch_size}."
            )
        if waveform.shape[1] == 1 and channels > 1:
            waveform = waveform.repeat(1, channels, 1)
        elif waveform.shape[1] != channels:
            raise ValueError(
                f"audio_{index} has {waveform.shape[1]} channels, expected 1 or {channels}."
            )
        aligned.append(waveform[..., :length])

    return aligned, sample_rate


def ensemble_audio_inputs(audios, weights, ensemble_type):
    aligned, sample_rate = align_audio_inputs(audios)
    waveforms = torch.stack(aligned, dim=0).numpy().astype(np.float32, copy=False)
    weights = np.asarray(weights, dtype=np.float32)
    batch_results = [
        average_waveforms(waveforms[:, batch_index], weights=weights, algorithm=ensemble_type)
        for batch_index in range(waveforms.shape[1])
    ]
    result = np.stack(batch_results, axis=0)
    waveform = torch.from_numpy(np.ascontiguousarray(result.astype(np.float32, copy=False)))
    return {"waveform": waveform, "sample_rate": sample_rate}
