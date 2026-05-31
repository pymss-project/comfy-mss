# comfy-mss

ComfyUI custom nodes for [pymss](https://pypi.org/project/pymss/), a Python music source separation package.

## Nodes

Display names shown in ComfyUI:

- `pymss MSS Separate`: separates a ComfyUI `AUDIO` stream with non-VR pymss models.
- `pymss Custom MSS Separate`: separates audio with user-provided MSS models from `models/pymss/custom`.
- `pymss VR Separate`: separates a ComfyUI `AUDIO` stream with VR/UVR pymss models.
- `pymss MSS Params`: optional parameter input for `pymss MSS Separate`.
- `pymss VR Params`: optional parameter input for `pymss VR Separate`.
- `pymss Load Audio`: loads one audio file and outputs its file name without extension.
- `pymss Load Audio Batch`: loads audio files from a folder as a ComfyUI list output.
- `pymss Audio Invert Phase`: inverts audio input `a` and outputs `-a`.
- `pymss Audio Normalize`: normalizes only when the peak is above 0 dBFS.
- `pymss Save Audio`: saves ComfyUI `AUDIO` streams as `wav`, `flac`, or `mp3`.

The internal node IDs are kept stable for workflow compatibility:

- `mss_separate`
- `custom_mss_separate`
- `vr_separate`
- `pymss_mss_params`
- `pymss_vr_params`
- `pymss_load_audio`
- `pymss_load_audio_batch`
- `pymss_audio_invert_phase`
- `pymss_audio_normalize`
- `pymss_save_audio`

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

## Model Folder

Model files default to:

```text
ComfyUI/models/pymss
```

The folder is created automatically when the custom node loads.

The model folder can be changed with environment variables:

- `COMFY_MSS_MODEL_DIR`
- `PYMSS_MODEL_DIR`

The separator nodes also expose `model_dir`. Its default value is `Default`, which means:

1. Use `COMFY_MSS_MODEL_DIR` if set.
2. Otherwise use `PYMSS_MODEL_DIR` if set.
3. Otherwise use `ComfyUI/models/pymss`.

Entering a path in `model_dir` overrides the environment variables for that execution.

## Separator Nodes

`pymss MSS Separate` and `pymss VR Separate` both accept a ComfyUI `AUDIO` input and output dynamically named stems based on the selected model metadata.

The frontend extension in `web/comfy_mss.js` refreshes visible outputs after a model is selected. Each stem is exposed as an `AUDIO` output followed by a matching `STRING` stem-name output, for example `Vocals` and `Vocals_name`.

Downloaded models are shown first in the `model_name` list. Each item includes its catalog category prefix, for example `[vocal/vocal_instrumental_dual] model.ckpt`. Models that are not present in the configured model folder are shown after downloaded models in gray text. The category prefix is display-only; comfy-mss strips it before looking up stems or calling pymss.

`pymss MSS Separate` declares up to 16 audio/name output pairs. `pymss VR Separate` declares 2 audio/name output pairs.

`pymss Custom MSS Separate` scans `Default/custom`, which resolves to `ComfyUI/models/pymss/custom` by default. The folder is created automatically. Custom model files must be paired with a same-name YAML config in the same folder, for example `my_model.ckpt` and `my_model.yaml`. Supported model extensions include `.ckpt`, `.pth`, `.pt`, `.safetensors`, `.safetensor`, and `.bin`; config files must use `.yaml`. The node reads `training.instruments` from the YAML to determine dynamic stem outputs. Use the node's `model_type` dropdown to choose the correct pymss architecture, then click `Refresh Models` after adding or changing files.

Common inputs:

- `audio`: ComfyUI `AUDIO`.
- `model_name`: pymss model name.
- `device`: `auto`, `cpu`, `cuda`, `mps`, or `mlx`.
- `download_missing`: defaults to `true`.
- `source`: `modelscope`, `huggingface`, or `hf-mirror`.
- `params`: optional params node output.
- `model_dir`: defaults to `Default`.
- `device_ids`: defaults to `0`.
- `debug`: prints timing information when enabled.

## Params Nodes

`pymss MSS Params`:

- `batch_size`: defaults to `1`.
- `overlap_size`: defaults to `Default`.
- `chunk_size`: defaults to `Default`.
- `normalize`: defaults to `false`.
- `enable_tta`: defaults to `false`.

`Default` for `overlap_size` and `chunk_size` means the selected model's YAML values are used. Enter a positive integer to override either value.

When `normalize` is `false`, comfy-mss does not pass a `normalize` override to pymss. When it is `true`, comfy-mss passes `normalize=True`.

`pymss VR Params`:

- `batch_size`: defaults to `2`.
- `window_size`: defaults to `512`.
- `aggression`: defaults to `5`.
- `enable_tta`: defaults to `false`.
- `high_end_process`: defaults to `false`.
- `enable_post_process`: defaults to `false`.
- `post_process_threshold`: defaults to `0.2`.

VR `use_amp` is not exposed in the node UI and is passed as `true`.

## Audio Utility Nodes

`pymss Load Audio` is based on ComfyUI's built-in `Load Audio` implementation, but it also outputs `audio_name`, the selected file name without extension.

`pymss Load Audio Batch` inputs:

- `folder`: folder path.
- `recursive`: scan subfolders when enabled.
- `sort_files`: sort matched files by path when enabled.

Relative folder paths are resolved from ComfyUI's input folder. Absolute paths are used directly.

`pymss Load Audio Batch` outputs:

- `audio`: list of ComfyUI `AUDIO` objects.
- `audio_name`: list of loaded file names without extension.

Normal downstream ComfyUI nodes execute once per loaded list item, which is useful for batch separation workflows.

`pymss Audio Invert Phase` multiplies the waveform by `-1`.

`pymss Audio Normalize` checks the peak level. If the peak is above `1.0`, it scales the audio to `0.999`; otherwise it leaves the audio unchanged.

`pymss Save Audio` is an output node. It saves audio directly and does not need a downstream node.

Save behavior:

- `output_folder` set to `Default` or left empty: save into ComfyUI's default output folder.
- Relative `output_folder`: create/use that folder inside ComfyUI's output folder.
- Absolute `output_folder`: use that folder directly.
- `filename`: optional text input. Connect a composed file name such as `audio_name + "_" + stem_name`.
- If `filename` is not connected or is empty, saved files fall back to `audio_YYYYMMDD_HHMMSS`.
- Existing files are not overwritten. If a target path already exists, comfy-mss appends a numeric suffix.
- `sample_rate`: `32000`, `44100`, or `48000`; defaults to `44100`.

Supported formats:

- `wav`: `FLOAT`, `PCM_24`, `PCM_16`
- `flac`: `PCM_24`, `PCM_16`
- `mp3`: `128k`, `192k`, `256k`, `320k`

## Project Structure

ComfyUI loads the custom node through the root files:

- `__init__.py`: exposes ComfyUI node mappings and `WEB_DIRECTORY`.
- `nodes.py`: registers routes and declares node class/display mappings.
- `web/comfy_mss.js`: frontend extension entrypoint.
- `web/comfy_mss/`: frontend modules for slot colors, dynamic separator outputs, load-audio upload, and audio ensemble UI behavior.

Implementation code lives in `comfy_mss/`:

```text
comfy_mss/
  constants.py
  paths.py
  nodes/
    io.py
    params.py
    separate.py
  services/
    catalog.py
    routes.py
  utils/
    audio.py
    ensemble.py
web/
  comfy_mss.js
  comfy_mss/
    colors.js
    constants.js
    ensemble.js
    load_audio.js
    separate.js
    utils.js
```

Module responsibilities:

- `comfy_mss/nodes/io.py`: audio loading, batch audio loading, audio utility, audio ensemble, and audio saving nodes.
- `comfy_mss/nodes/params.py`: MSS and VR params nodes.
- `comfy_mss/nodes/separate.py`: MSS/VR separator nodes and pymss execution wrapper.
- `comfy_mss/services/catalog.py`: pymss model catalog and stem metadata helpers.
- `comfy_mss/services/routes.py`: HTTP route used by the frontend extension.
- `comfy_mss/utils/audio.py`: ComfyUI audio conversion, folder scanning, and save helpers.
- `comfy_mss/utils/ensemble.py`: audio ensemble alignment and merge algorithms.
- `comfy_mss/paths.py`: model directory resolution, path coercion, and ComfyUI model folder registration.
- `comfy_mss/constants.py`: shared constants.
- `web/comfy_mss/*.js`: frontend modules split by responsibility.
