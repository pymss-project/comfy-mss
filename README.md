# comfy-mss

ComfyUI custom nodes for [pymss](https://pypi.org/project/pymss/), a Python music source separation package.

## Nodes

- `mss_separate`: separates a ComfyUI `AUDIO` stream with non-VR pymss models.
- `vr_separate`: separates a ComfyUI `AUDIO` stream with VR/UVR pymss models.
- `pymss MSS Params`: optional parameter input for `mss_separate`.
- `pymss VR Params`: optional parameter input for `vr_separate`.
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

- Use ComfyUI's built-in `Load Audio` and `Save Audio` / `Preview Audio` nodes for IO.
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
