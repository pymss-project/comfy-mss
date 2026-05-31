from .comfy_mss.nodes.io import PymssAudioEnsemble, PymssAudioSubtract, PymssLoadAudio, PymssLoadAudioBatch, PymssSaveAudio
from .comfy_mss.nodes.params import PymssMssParams, PymssVrParams
from .comfy_mss.nodes.separate import PymssMssSeparate, PymssVrSeparate
from .comfy_mss.services.routes import register_routes


register_routes()


NODE_CLASS_MAPPINGS = {
    "mss_separate": PymssMssSeparate,
    "vr_separate": PymssVrSeparate,
    "pymss_mss_params": PymssMssParams,
    "pymss_vr_params": PymssVrParams,
    "pymss_load_audio": PymssLoadAudio,
    "pymss_load_audio_batch": PymssLoadAudioBatch,
    "pymss_audio_subtract": PymssAudioSubtract,
    "pymss_audio_ensemble": PymssAudioEnsemble,
    "pymss_save_audio": PymssSaveAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "mss_separate": "MSS Separate",
    "vr_separate": "VR Separate",
    "pymss_mss_params": "MSS Params",
    "pymss_vr_params": "VR Params",
    "pymss_load_audio": "Load Audio",
    "pymss_load_audio_batch": "Load Audio Batch",
    "pymss_audio_subtract": "Audio Subtract",
    "pymss_audio_ensemble": "Audio Ensemble",
    "pymss_save_audio": "Save Audio",
}
