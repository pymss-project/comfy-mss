import os
import folder_paths

from .constants import MODEL_DIR_ENV_VARS, MODEL_FOLDER_NAME


def coerce_optional_path(value):
    value = str(value or "").strip()
    return value or None


def default_model_dir():
    return os.path.join(folder_paths.models_dir, MODEL_FOLDER_NAME)


def registered_model_dirs(create=True):
    try:
        paths = folder_paths.get_folder_paths(MODEL_FOLDER_NAME)
    except KeyError:
        paths = []
    if not paths:
        paths = [default_model_dir()]

    resolved = []
    seen = set()
    for path in paths:
        value = os.path.abspath(os.path.expanduser(os.path.expandvars(path)))
        key = os.path.normcase(value)
        if key in seen:
            continue
        seen.add(key)
        if create:
            os.makedirs(value, exist_ok=True)
        resolved.append(value)
    return resolved


def resolve_model_dir(model_dir=None, create=True):
    if str(model_dir or "").strip().lower() == "default":
        model_dir = None
    resolved = coerce_optional_path(model_dir)
    if resolved is None:
        for env_name in MODEL_DIR_ENV_VARS:
            resolved = coerce_optional_path(os.environ.get(env_name))
            if resolved is not None:
                break
    if resolved is None:
        resolved = registered_model_dirs(create=create)[0]

    resolved = os.path.abspath(os.path.expanduser(os.path.expandvars(resolved)))
    if create:
        os.makedirs(resolved, exist_ok=True)
    return resolved


def register_model_folder():
    model_dir = resolve_model_dir(create=True)
    folder_paths.add_model_folder_path(MODEL_FOLDER_NAME, model_dir, is_default=True)
    return model_dir


DEFAULT_MODEL_DIR = register_model_folder()
