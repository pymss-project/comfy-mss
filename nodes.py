from .comfy_mss.nodes.io import (
    PymssAudioEnsemble,
    PymssAudioInvertPhase,
    PymssAudioNormalize,
    PymssLoadAudio,
    PymssLoadAudioBatch,
    PymssSaveAudio,
)
from .comfy_mss.nodes.params import PymssMssParams, PymssVrParams
from .comfy_mss.nodes.separate import PymssCustomMssSeparate, PymssMssSeparate, PymssVrSeparate
from .comfy_mss.services.routes import register_routes


register_routes()


NODE_CLASS_MAPPINGS = {
    "mss_separate": PymssMssSeparate,
    "custom_mss_separate": PymssCustomMssSeparate,
    "vr_separate": PymssVrSeparate,
    "pymss_mss_params": PymssMssParams,
    "pymss_vr_params": PymssVrParams,
    "pymss_load_audio": PymssLoadAudio,
    "pymss_load_audio_batch": PymssLoadAudioBatch,
    "pymss_audio_invert_phase": PymssAudioInvertPhase,
    "pymss_audio_normalize": PymssAudioNormalize,
    "pymss_audio_ensemble": PymssAudioEnsemble,
    "pymss_save_audio": PymssSaveAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "mss_separate": "MSS Separate",
    "custom_mss_separate": "Custom MSS Separate",
    "vr_separate": "VR Separate",
    "pymss_mss_params": "MSS Params",
    "pymss_vr_params": "VR Params",
    "pymss_load_audio": "Load Audio",
    "pymss_load_audio_batch": "Load Audio Batch",
    "pymss_audio_invert_phase": "Audio Invert Phase",
    "pymss_audio_normalize": "Audio Normalize",
    "pymss_audio_ensemble": "Audio Ensemble",
    "pymss_save_audio": "Save Audio",
}
