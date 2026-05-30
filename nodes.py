from .io_nodes import PymssAudioSubtract, PymssLoadAudioBatch, PymssModelList, PymssSaveAudio
from .params import PymssMssParams, PymssVrParams
from .routes import register_routes
from .separate import MssSeparate, VrSeparate


register_routes()


NODE_CLASS_MAPPINGS = {
    "mss_separate": MssSeparate,
    "vr_separate": VrSeparate,
    "pymss_mss_params": PymssMssParams,
    "pymss_vr_params": PymssVrParams,
    "PymssModelList": PymssModelList,
    "pymss_load_audio_batch": PymssLoadAudioBatch,
    "pymss_audio_subtract": PymssAudioSubtract,
    "pymss_save_audio": PymssSaveAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "mss_separate": "mss_separate",
    "vr_separate": "vr_separate",
    "pymss_mss_params": "pymss MSS Params",
    "pymss_vr_params": "pymss VR Params",
    "PymssModelList": "pymss Model List",
    "pymss_load_audio_batch": "pymss Load Audio Batch",
    "pymss_audio_subtract": "pymss Audio Subtract",
    "pymss_save_audio": "pymss Save Audio",
}
