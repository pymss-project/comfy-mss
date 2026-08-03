import os
import re
import pymss
import yaml

from functools import lru_cache
from pymss.modules.vocal_remover.vr_models import VR_MODEL_METADATA

from ..paths import registered_model_dirs
from ..constants import NOT_DOWNLOADED_PREFIX, CUSTOM_MODEL_DIR_NAME, CUSTOM_MODEL_EXTENSIONS


def clean_model_display_name(model_name):
    name = str(model_name or "").strip()
    if name.startswith(NOT_DOWNLOADED_PREFIX):
        name = name[len(NOT_DOWNLOADED_PREFIX) :].strip()
    try:
        for item in model_catalog("all"):
            names = [item["name"], item["display_name"], item.get("display_name_cn"), *item.get("aliases", [])]
            if name in names:
                return item["name"]
            if name.endswith(item["name"]) and name[: -len(item["name"])].strip().startswith("["):
                return item["name"]
    except Exception:
        pass
    return name


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


def entry_stems(entry):
    # ``config_instruments`` is only available in newer pymss releases.
    # Catalog loading must remain compatible with older ModelEntry objects.
    stems = split_stems(getattr(entry, "config_instruments", None))
    if stems:
        return stems

    if entry.model_type == "vr":
        data = VR_MODEL_METADATA.get(entry.name)
        if data:
            return [data["primary_stem"], data["secondary_stem"]]

    stems = split_stems(getattr(entry, "target_stem", None))
    return stems or ["audio"]


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
            except Exception:
                continue
            model_type = custom_entry_model_type(config)
            # Custom MSS nodes only instantiate MSST architectures. VR/UVR
            # models belong to the dedicated VR nodes and must not appear in
            # this custom-model menu even when accompanied by a YAML file.
            if model_type.strip().lower() == "vr":
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


def is_model_downloaded(entry, model_dir=None):
    if not entry.relpath:
        return False
    model_dirs = [model_dir] if model_dir else registered_model_dirs(create=True)
    return any(os.path.isfile(os.path.join(path, entry.relpath)) for path in model_dirs)


@lru_cache(maxsize=1)
def _base_model_entries():
    rows = []
    for entry in pymss.list_models(supported=True):
        rows.append(entry)
    return rows


def model_catalog(model_kind="all"):
    rows = []
    for entry in _base_model_entries():
        if model_kind == "vr" and entry.model_type != "vr":
            continue
        if model_kind == "mss" and entry.model_type == "vr":
            continue
        downloaded = is_model_downloaded(entry)
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
