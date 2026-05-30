import re
from functools import lru_cache

from .constants import MISSING_PYMSS_OPTION
from .core import import_pymss


def model_names(model_kind):
    try:
        return [item["name"] for item in model_catalog(model_kind)]
    except Exception:
        return [MISSING_PYMSS_OPTION]


def split_stems(value):
    return [item.strip() for item in re.split(r"[|/]", value or "") if item.strip()]


def entry_stems(entry):
    stems = split_stems(entry.config_instruments)
    if stems:
        return stems

    if entry.model_type == "vr":
        try:
            from pymss.modules.vocal_remover.vr_models import VR_MODEL_METADATA

            data = VR_MODEL_METADATA.get(entry.name)
            if data:
                return [data["primary_stem"], data["secondary_stem"]]
        except Exception:
            pass

    stems = split_stems(entry.target_stem)
    return stems or ["audio"]


@lru_cache(maxsize=8)
def model_catalog(model_kind="all"):
    pymss = import_pymss()
    rows = []
    for entry in pymss.list_models(supported=True):
        if model_kind == "vr" and entry.model_type != "vr":
            continue
        if model_kind == "mss" and entry.model_type == "vr":
            continue
        rows.append(
            {
                "name": entry.name,
                "aliases": list(entry.aliases),
                "model_type": entry.model_type,
                "architecture": entry.architecture,
                "category": entry.category_path or entry.primary_category,
                "category_cn": " / ".join(
                    part for part in (entry.primary_category_cn, entry.secondary_category_cn) if part
                ),
                "target_stem": entry.target_stem,
                "stems": entry_stems(entry),
            }
        )
    return rows


def stem_names(model_name, model_kind):
    for item in model_catalog(model_kind):
        if item["name"] == model_name:
            return item["stems"]
    return ["audio"]
