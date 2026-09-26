import os
import re
from functools import lru_cache

import pymss
import yaml
from pymss.modules.vocal_remover.vr_models import VR_MODEL_METADATA

from ..constants import CUSTOM_MODEL_DIR_NAME, CUSTOM_MODEL_EXTENSIONS, NOT_DOWNLOADED_PREFIX
from ..paths import registered_model_dirs


def clean_model_display_name(model_name):
    name = str(model_name or "").strip()
    if name.startswith(NOT_DOWNLOADED_PREFIX):
        name = name[len(NOT_DOWNLOADED_PREFIX) :].strip()
    return re.sub(r"^\[[^\]]+\]\s*", "", name).strip()


def entry_category_label(entry):
    parts = [entry.primary_category, entry.secondary_category]
    value = "/".join(part for part in parts if part)
    return f"[{value}] " if value else ""


def entry_category_label_cn(entry):
    parts = [entry.primary_category_cn, entry.secondary_category_cn]
    value = "/".join(part for part in parts if part)
    return f"[{value}] " if value else ""


def entry_display_name(entry, downloaded):
    return f"{entry_category_label(entry)}{entry.name}"


def model_names(model_kind):
    names = []
    seen = set()
    for item in model_catalog(model_kind):
        for name in (item["display_name"], item.get("display_name_cn")):
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def custom_model_dirs():
    roots = []
    for model_dir in registered_model_dirs(create=True):
        root = os.path.join(model_dir, CUSTOM_MODEL_DIR_NAME)
        os.makedirs(root, exist_ok=True)
        roots.append(root)
    return roots


def custom_model_dir():
    return custom_model_dirs()[0]


def custom_model_names():
    return [item["display_name"] for item in custom_model_catalog()]


def split_stems(value):
    return [item.strip() for item in re.split(r"[|/]", value or "") if item.strip()]


def entry_stems(entry, model_dirs=None):
    # ``config_instruments`` is only available in newer pymss releases.
    # Catalog loading must remain compatible with older ModelEntry objects.
    stems = split_stems(getattr(entry, "config_instruments", None))
    if stems:
        return stems, True

    if entry.model_type == "vr":
        data = VR_MODEL_METADATA.get(entry.name)
        if data:
            return [data["primary_stem"], data["secondary_stem"]], True

    config_relpath = str(getattr(entry, "config_relpath", "") or "").strip()
    if config_relpath:
        for model_dir in model_dirs or registered_model_dirs(create=True):
            config_path = os.path.join(model_dir, config_relpath)
            if not os.path.isfile(config_path):
                continue
            try:
                stems = custom_entry_stems(_load_yaml(config_path))
            except (AttributeError, OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError):
                continue
            if stems != ["audio"]:
                return stems, True

    stems = split_stems(getattr(entry, "target_stem", None))
    # A slash-separated catalog target is already a complete multi-stem list.
    # A single target may omit the complementary residual stem, so preserve the
    # node's generic outputs until the model config is locally available.
    return stems or ["audio"], len(stems) > 1


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=yaml.FullLoader) or {}


def custom_entry_stems(config):
    instruments = config.get("training", {}).get("instruments", [])
    if not isinstance(instruments, list):
        return ["audio"]
    stems = [str(item).strip() for item in instruments if str(item).strip()]
    return stems or ["audio"]


def custom_entry_model_type(config):
    try:
        return pymss.detect_model_type(config)
    except pymss.ModelTypeDetectionError:
        return None


def custom_model_catalog():
    rows = []
    seen = set()
    for root in custom_model_dirs():
        try:
            model_dirs = sorted(
                (entry for entry in os.scandir(root) if entry.is_dir()),
                key=lambda entry: entry.name.lower(),
            )
        except OSError:
            continue

        for model_dir in model_dirs:
            try:
                files = sorted(
                    (entry for entry in os.scandir(model_dir.path) if entry.is_file()),
                    key=lambda entry: entry.name.lower(),
                )
            except OSError:
                continue

            model_files = [entry for entry in files if os.path.splitext(entry.name)[1].lower() in CUSTOM_MODEL_EXTENSIONS]
            config_files = [entry for entry in files if os.path.splitext(entry.name)[1].lower() == ".yaml"]
            if not model_files or not config_files:
                continue

            # A folder represents one custom model. Prefer a same-stem pair if
            # present for backwards-friendly determinism; otherwise the first
            # model and YAML in alphabetical order form the folder's pair.
            model_file = model_files[0]
            config_file = config_files[0]
            configs_by_stem = {os.path.splitext(entry.name)[0].lower(): entry for entry in config_files}
            for candidate in model_files:
                matching_config = configs_by_stem.get(os.path.splitext(candidate.name)[0].lower())
                if matching_config:
                    model_file = candidate
                    config_file = matching_config
                    break

            name = model_dir.name
            key = name.lower()
            if key in seen:
                continue
            try:
                config = _load_yaml(config_file.path)
            except (AttributeError, OSError, TypeError, UnicodeError, ValueError, yaml.YAMLError):
                continue
            if not isinstance(config, dict):
                continue
            model_type = custom_entry_model_type(config)
            # Custom MSS nodes only instantiate MSST architectures. VR/UVR
            # models belong to the dedicated VR nodes and must not appear in
            # this custom-model menu even when accompanied by a YAML file.
            if model_type and model_type.strip().lower() == "vr":
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "display_name": name,
                    "downloaded": True,
                    "model_type": model_type,
                    "model_path": model_file.path,
                    "config_path": config_file.path,
                    "stems": custom_entry_stems(config),
                }
            )
    rows.sort(key=lambda item: item["name"].lower())
    return rows


def custom_model_entry(model_name):
    model_name = str(model_name or "").replace("\\", "/").strip()
    for item in custom_model_catalog():
        if item["name"] == model_name or item["display_name"] == model_name:
            return item
    return None


def custom_stem_names(model_name):
    entry = custom_model_entry(model_name)
    return entry["stems"] if entry else ["audio"]


def is_model_downloaded(entry, model_dir=None, model_dirs=None):
    if not entry.relpath:
        return False
    if model_dirs is None:
        model_dirs = [model_dir] if model_dir else registered_model_dirs(create=True)
    required_relpaths = [entry.relpath]
    if getattr(entry, "config_relpath", ""):
        required_relpaths.append(entry.config_relpath)
    required_relpaths.extend(getattr(entry, "auxiliary_relpaths", ()) or ())
    return any(
        all(os.path.isfile(os.path.join(path, relpath)) for relpath in required_relpaths)
        for path in model_dirs
    )


@lru_cache(maxsize=1)
def _base_model_entries():
    return list(pymss.list_models(supported=True))


def model_catalog(model_kind="all"):
    rows = []
    model_dirs = registered_model_dirs(create=True)
    for entry in _base_model_entries():
        if model_kind == "vr" and entry.model_type != "vr":
            continue
        if model_kind == "mss" and entry.model_type == "vr":
            continue
        downloaded = is_model_downloaded(entry, model_dirs=model_dirs)
        stems, stems_complete = entry_stems(entry, model_dirs)
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
                "primary_category_cn": entry.primary_category_cn,
                "secondary_category": entry.secondary_category,
                "secondary_category_cn": entry.secondary_category_cn,
                "category_cn": " / ".join(part for part in (entry.primary_category_cn, entry.secondary_category_cn) if part),
                "display_name_cn": f"{entry_category_label_cn(entry)}{entry.name}",
                "target_stem": entry.target_stem,
                "stems": stems,
                "stems_complete": stems_complete,
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
