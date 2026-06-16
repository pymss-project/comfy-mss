from .comfy_mss.nodes.io import (
    PymssAudioEnsemble,
    PymssAudioInvertPhase,
    PymssAudioNormalize,
    PymssLoadAudio,
    PymssLoadAudioBatch,
    PymssSaveAudio,
)
from .comfy_mss.nodes.params import PymssMssParams, PymssVrParams
from .comfy_mss.nodes.separate import (
    PymssCustomMssSeparate,
    PymssCustomMssSeparateList,
    PymssMssSeparate,
    PymssMssSeparateList,
    PymssVrSeparate,
    PymssVrSeparateList,
)
from .comfy_mss.services.routes import register_routes


register_routes()


NODE_CLASS_MAPPINGS = {
    "mss_separate": PymssMssSeparate,
    "mss_separate_list": PymssMssSeparateList,
    "custom_mss_separate": PymssCustomMssSeparate,
    "custom_mss_separate_list": PymssCustomMssSeparateList,
    "vr_separate": PymssVrSeparate,
    "vr_separate_list": PymssVrSeparateList,
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
    "mss_separate_list": "MSS Separate List",
    "custom_mss_separate": "Custom MSS Separate",
    "custom_mss_separate_list": "Custom MSS Separate List",
    "vr_separate": "VR Separate",
    "vr_separate_list": "VR Separate List",
    "pymss_mss_params": "MSS Params",
    "pymss_vr_params": "VR Params",
    "pymss_load_audio": "Load Audio",
    "pymss_load_audio_batch": "Load Audio Batch",
    "pymss_audio_invert_phase": "Audio Invert Phase",
    "pymss_audio_normalize": "Audio Normalize",
    "pymss_audio_ensemble": "Audio Ensemble",
    "pymss_save_audio": "Save Audio",
}
