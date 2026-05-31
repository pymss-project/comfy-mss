import numpy as np
import torch


def align_audio_inputs(audios):
    import torchaudio

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
            waveform = torchaudio.functional.resample(waveform, source_sample_rate, sample_rate)
        waveforms.append(waveform)

    batch_size = min(item.shape[0] for item in waveforms)
    channels = min(item.shape[1] for item in waveforms)
    length = min(item.shape[2] for item in waveforms)
    if batch_size <= 0 or channels <= 0 or length <= 0:
        raise ValueError("Audio inputs must have non-empty batch, channel, and sample dimensions.")

    return [item[:batch_size, :channels, :length] for item in waveforms], sample_rate


def _weighted_average_waveform(waveforms, weights):
    weight_sum = float(np.sum(weights))
    if abs(weight_sum) < 1e-12:
        raise ValueError("Sum of weights must not be zero for avg_wave or avg_fft.")
    weighted = waveforms * weights.reshape((-1,) + (1,) * (waveforms.ndim - 1))
    return weighted.sum(axis=0) / weight_sum


def _select_by_abs(waveforms, mode):
    selector = np.argmax if mode == "max" else np.argmin
    indices = selector(np.abs(waveforms), axis=0, keepdims=True)
    return np.take_along_axis(waveforms, indices, axis=0).squeeze(axis=0)


def _stft_audio(waveform):
    import librosa

    batch, channels, _length = waveform.shape
    return [
        [
            librosa.stft(np.asfortranarray(waveform[batch_index, channel_index]), n_fft=2048, hop_length=1024)
            for channel_index in range(channels)
        ]
        for batch_index in range(batch)
    ]


def _istft_audio(specs, length):
    import librosa

    batch = len(specs)
    channels = len(specs[0]) if batch else 0
    output = np.zeros((batch, channels, length), dtype=np.float32)
    for batch_index in range(batch):
        for channel_index in range(channels):
            output[batch_index, channel_index] = librosa.istft(
                specs[batch_index][channel_index],
                hop_length=1024,
                length=length,
            ).astype(np.float32, copy=False)
    return output


def _ensemble_fft(waveforms, weights, ensemble_type):
    specs = [_stft_audio(waveform) for waveform in waveforms]
    stacked = np.asarray(specs)

    if ensemble_type == "avg_fft":
        result_specs = _weighted_average_waveform(stacked, weights)
    elif ensemble_type == "median_fft":
        result_specs = np.median(stacked, axis=0)
    elif ensemble_type == "min_fft":
        result_specs = _select_by_abs(stacked, "min")
    elif ensemble_type == "max_fft":
        result_specs = _select_by_abs(stacked, "max")
    else:
        raise ValueError(f"Unsupported ensemble_type: {ensemble_type}")

    return _istft_audio(result_specs, waveforms.shape[-1])


def ensemble_audio_inputs(audios, weights, ensemble_type):
    aligned, sample_rate = align_audio_inputs(audios)
    waveforms = torch.stack(aligned, dim=0).numpy().astype(np.float32, copy=False)
    weights = np.asarray(weights, dtype=np.float32)

    if ensemble_type == "avg_wave":
        result = _weighted_average_waveform(waveforms, weights)
    elif ensemble_type == "median_wave":
        result = np.median(waveforms, axis=0)
    elif ensemble_type == "min_wave":
        result = _select_by_abs(waveforms, "min")
    elif ensemble_type == "max_wave":
        result = _select_by_abs(waveforms, "max")
    elif ensemble_type in {"avg_fft", "median_fft", "min_fft", "max_fft"}:
        result = _ensemble_fft(waveforms, weights, ensemble_type)
    else:
        raise ValueError(f"Unsupported ensemble_type: {ensemble_type}")

    waveform = torch.from_numpy(np.ascontiguousarray(result.astype(np.float32, copy=False)))
    return {"waveform": waveform, "sample_rate": sample_rate}
