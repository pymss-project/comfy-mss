import os

import folder_paths

from .constants import MODEL_DIR_ENV_VARS, MODEL_FOLDER_NAME
from .core import coerce_optional_path


def default_model_dir():
    return os.path.join(folder_paths.models_dir, MODEL_FOLDER_NAME)


def resolve_model_dir(model_dir=None, create=True):
    resolved = coerce_optional_path(model_dir)
    if resolved is None:
        for env_name in MODEL_DIR_ENV_VARS:
            resolved = coerce_optional_path(os.environ.get(env_name))
            if resolved is not None:
                break
    if resolved is None:
        resolved = default_model_dir()

    resolved = os.path.abspath(os.path.expanduser(os.path.expandvars(resolved)))
    if create:
        os.makedirs(resolved, exist_ok=True)
    return resolved


def register_model_folder():
    model_dir = resolve_model_dir(create=True)
    folder_paths.add_model_folder_path(MODEL_FOLDER_NAME, model_dir, is_default=True)
    return model_dir


DEFAULT_MODEL_DIR = register_model_folder()
