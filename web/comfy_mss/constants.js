export const SEPARATE_NODE_TYPES = new Set(["mss_separate", "custom_mss_separate", "vr_separate"]);
export const LOAD_AUDIO_NODE_TYPE = "pymss_load_audio";
export const AUDIO_ENSEMBLE_NODE_TYPE = "pymss_audio_ensemble";
export const SAVE_AUDIO_NODE_TYPE = "pymss_save_audio";
export const AUDIO_TOOL_NODE_TYPES = new Set(["pymss_audio_invert_phase", "pymss_audio_normalize"]);
export const FIXED_260_NODE_TYPES = new Set([
  "pymss_vr_params",
  "pymss_mss_params",
  "pymss_load_audio_batch",
]);

export const MSS_MAX_STEMS = 16;
export const VR_MAX_STEMS = 2;
export const SEPARATE_MIN_NODE_WIDTH = 420;
export const STANDARD_NODE_WIDTH = 260;
export const AUDIO_ENSEMBLE_MIN_NODE_WIDTH = STANDARD_NODE_WIDTH;
export const AUDIO_TOOL_MIN_NODE_WIDTH = 200;
export const SAVE_AUDIO_MIN_NODE_WIDTH = STANDARD_NODE_WIDTH;

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
