# comfy-mss

ComfyUI custom nodes for [pymss](https://pypi.org/project/pymss/), a Python music source separation package.

## Nodes

- `mss_separate`: separates a ComfyUI `AUDIO` stream with non-VR pymss models.
- `vr_separate`: separates a ComfyUI `AUDIO` stream with VR/UVR pymss models.
- `pymss MSS Params`: optional parameter input for `mss_separate`.
- `pymss VR Params`: optional parameter input for `vr_separate`.
- `pymss Load Audio Batch`: loads multiple audio files from a newline-separated file list or a folder.
- `pymss Audio Subtract`: subtracts one `AUDIO` stream from another to produce residual tracks.
- `pymss Save Audio`: saves ComfyUI `AUDIO` streams as `wav`, `flac`, `mp3`, or `m4a`.
- `pymss Model List`: lists known pymss models and stem metadata as JSON.

## Install pymss

From PyPI:

```powershell
.\.venv\Scripts\python.exe -m pip install pymss
```

For local pymss development from `E:\vs\pymss`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e E:\vs\pymss
```

Restart ComfyUI after installing or changing the dependency.

## Notes

- Use ComfyUI's built-in `Load Audio` node for loading audio. `pymss Save Audio` can save separated stems with selectable format, quality, and folder.
- `pymss Load Audio Batch` outputs lists. Normal downstream nodes execute once per loaded file, which is useful for batch separation workflows.
- In `pymss Load Audio Batch`, relative file and folder paths are resolved from ComfyUI's input folder. Absolute paths are used directly.
- `pymss Audio Subtract` aligns sample rate, channel count, batch size, and duration before subtracting. If durations differ, the shorter length is used.
- `pymss Save Audio` defaults to ComfyUI's output folder. A relative `output_folder` is created inside the output folder; an absolute `output_folder` is used directly.
- `mss_separate` and `vr_separate` outputs are refreshed by the frontend extension after choosing a model.
- The backend declares up to 64 audio stems, which covers the current pymss catalog maximum of 53 stems.
- Model files default to `ComfyUI/models/pymss`. The folder is created automatically when the node loads.
- The default model folder can be changed at runtime with `COMFY_MSS_MODEL_DIR`. `PYMSS_MODEL_DIR` is also supported for pymss compatibility.
- The node-level `model_dir` input overrides both environment variables for that execution.
- Both parameter nodes include `extra_params_json` for advanced pymss inference overrides, for example:

```json
{
  "batch_size": 2,
  "chunk_size": 352800
}
```
