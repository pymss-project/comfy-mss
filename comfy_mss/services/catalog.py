import os
import re
import pymss

from functools import lru_cache
from pymss.modules.vocal_remover.vr_models import VR_MODEL_METADATA

from ..paths import resolve_model_dir


NOT_DOWNLOADED_PREFIX = "[Not downloaded] "


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
