export const SEPARATE_NODE_TYPES = new Set(["mss_separate", "vr_separate"]);
export const LOAD_AUDIO_NODE_TYPE = "pymss_load_audio";
export const AUDIO_ENSEMBLE_NODE_TYPE = "pymss_audio_ensemble";

export const MSS_MAX_STEMS = 16;
export const VR_MAX_STEMS = 2;
export const SEPARATE_MIN_NODE_WIDTH = 420;
export const AUDIO_ENSEMBLE_MIN_NODE_WIDTH = 250;

export const TYPE_COLORS = {
  AUDIO: "#22c55e",
  STRING: "#f2c94c",
  PYMSS_MSS_PARAMS: "#f472b6",
  PYMSS_VR_PARAMS: "#f472b6",
};

export const TYPE_ALIASES = {
  AUDIO: ["AUDIO", "audio"],
  STRING: ["STRING", "string"],
  PYMSS_MSS_PARAMS: ["PYMSS_MSS_PARAMS", "pymss_mss_params"],
  PYMSS_VR_PARAMS: ["PYMSS_VR_PARAMS", "pymss_vr_params"],
};
