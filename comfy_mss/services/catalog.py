import os
import re
import pymss
import yaml

from functools import lru_cache
from pymss.modules.vocal_remover.vr_models import VR_MODEL_METADATA

from ..paths import resolve_model_dir


NOT_DOWNLOADED_PREFIX = "[Not downloaded] "
CUSTOM_MODEL_EXTENSIONS = (".ckpt", ".pth", ".pt", ".safetensors", ".safetensor", ".bin")
CUSTOM_MODEL_DIR_NAME = "custom"


def clean_model_display_name(model_name):
    name = str(model_name or "").strip()
    if name.startswith(NOT_DOWNLOADED_PREFIX):
        name = name[len(NOT_DOWNLOADED_PREFIX) :].strip()
    try:
        for entry in _base_model_entries():
            if name == entry.name or name in entry.aliases:
                return entry.name
            if name.endswith(entry.name) and name[: -len(entry.name)].strip().startswith("["):
                return entry.name
    except Exception:
        pass
    return name


def entry_category_label(entry):
    parts = [entry.primary_category, entry.secondary_category]
    value = "/".join(part for part in parts if part)
    return f"[{value}] " if value else ""


def entry_display_name(entry, downloaded):
    return f"{entry_category_label(entry)}{entry.name}"


def model_names(model_kind):
    return [item["display_name"] for item in model_catalog(model_kind)]


def custom_model_dir(model_dir="Default/custom"):
    text = str(model_dir or "").strip()
    if not text or text.lower() in {"default", "default/custom"}:
        root = os.path.join(resolve_model_dir(create=True), CUSTOM_MODEL_DIR_NAME)
    elif text.lower() == "custom":
        root = os.path.join(resolve_model_dir(create=True), CUSTOM_MODEL_DIR_NAME)
    elif text.replace("\\", "/").lower().endswith("/custom"):
        root = os.path.abspath(os.path.expanduser(os.path.expandvars(text)))
    else:
        root = os.path.join(resolve_model_dir(text, create=True), CUSTOM_MODEL_DIR_NAME)
    os.makedirs(root, exist_ok=True)
    return root


def custom_model_names(model_dir="Default/custom"):
    return [item["display_name"] for item in custom_model_catalog(model_dir)]


def split_stems(value):
    return [item.strip() for item in re.split(r"[|/]", value or "") if item.strip()]


def entry_stems(entry):
    stems = split_stems(entry.config_instruments)
    if stems:
        return stems

    if entry.model_type == "vr":
        data = VR_MODEL_METADATA.get(entry.name)
        if data:
            return [data["primary_stem"], data["secondary_stem"]]

    stems = split_stems(entry.target_stem)
    return stems or ["audio"]


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def custom_entry_stems(config):
    instruments = config.get("training", {}).get("instruments", [])
    if not isinstance(instruments, list):
        return ["audio"]
    stems = [str(item).strip() for item in instruments if str(item).strip()]
    return stems or ["audio"]


def custom_entry_model_type(config):
    for path in (
        ("model_type",),
        ("model", "type"),
        ("model", "model_type"),
        ("model", "architecture"),
        ("training", "model_type"),
    ):
        value = config
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value:
            return str(value)
    return "mel_band_roformer"


def custom_model_catalog(model_dir="Default/custom"):
    root = custom_model_dir(model_dir)
    rows = []
    for current_root, _dirs, files in os.walk(root):
        file_set = set(files)
        for filename in files:
            stem, ext = os.path.splitext(filename)
            if ext.lower() not in CUSTOM_MODEL_EXTENSIONS:
                continue
            config_name = f"{stem}.yaml"
            if config_name not in file_set:
                continue
            model_path = os.path.join(current_root, filename)
            config_path = os.path.join(current_root, config_name)
            relpath = os.path.relpath(model_path, root).replace("\\", "/")
            try:
                config = _load_yaml(config_path)
            except Exception as exc:
                print(f"[comfy-mss] failed to load custom model yaml {config_path}: {exc}")
                continue
            rows.append(
                {
                    "name": relpath,
                    "display_name": relpath,
                    "downloaded": True,
                    "model_type": custom_entry_model_type(config),
                    "model_path": model_path,
                    "config_path": config_path,
                    "stems": custom_entry_stems(config),
                }
            )
    rows.sort(key=lambda item: item["name"].lower())
    return rows


def custom_model_entry(model_name, model_dir="Default/custom"):
    model_name = str(model_name or "").replace("\\", "/").strip()
    for item in custom_model_catalog(model_dir):
        if item["name"] == model_name or item["display_name"] == model_name:
            return item
    return None


def custom_stem_names(model_name, model_dir="Default/custom"):
    entry = custom_model_entry(model_name, model_dir)
    return entry["stems"] if entry else ["audio"]


def is_model_downloaded(entry, model_dir=None):
    if not entry.relpath:
        return False
    model_dir = model_dir or resolve_model_dir(create=True)
    return os.path.isfile(os.path.join(model_dir, entry.relpath))


@lru_cache(maxsize=1)
def _base_model_entries():
    rows = []
    for entry in pymss.list_models(supported=True):
        rows.append(entry)
    return rows


def model_catalog(model_kind="all"):
    model_dir = resolve_model_dir(create=True)
    rows = []
    for entry in _base_model_entries():
        if model_kind == "vr" and entry.model_type != "vr":
            continue
        if model_kind == "mss" and entry.model_type == "vr":
            continue
        downloaded = is_model_downloaded(entry, model_dir)
        display_name = entry_display_name(entry, downloaded)
        rows.append(
            {
                "name": entry.name,
                "display_name": display_name,
                "downloaded": downloaded,
                "aliases": list(entry.aliases),
                "model_type": entry.model_type,
                "architecture": entry.architecture,
                "category": entry.category_path or entry.primary_category,
                "primary_category": entry.primary_category,
                "secondary_category": entry.secondary_category,
                "category_cn": " / ".join(
                    part for part in (entry.primary_category_cn, entry.secondary_category_cn) if part
                ),
                "target_stem": entry.target_stem,
                "stems": entry_stems(entry),
            }
        )
    rows.sort(
        key=lambda item: (
            not item["downloaded"],
            item["primary_category"] or "",
            item["secondary_category"] or "",
            item["name"].lower(),
        )
    )
    return rows


def stem_names(model_name, model_kind):
    model_name = clean_model_display_name(model_name)
    for item in model_catalog(model_kind):
        if item["name"] == model_name:
            return item["stems"]
    return ["audio"]
