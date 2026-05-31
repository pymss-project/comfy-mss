import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

import { applyLinkColorPatch, applyTypeColors, colorLink, colorNodeSlots, colorSlot } from "./comfy_mss/colors.js";
import { AUDIO_ENSEMBLE_NODE_TYPE, AUDIO_TOOL_NODE_TYPES, LOAD_AUDIO_NODE_TYPE, SEPARATE_NODE_TYPES } from "./comfy_mss/constants.js";
import { registerAudioToolNode } from "./comfy_mss/audio_tools.js";
import { registerAudioEnsembleNode } from "./comfy_mss/ensemble.js";
import { registerLoadAudioNode } from "./comfy_mss/load_audio.js";
import { registerSeparateNode } from "./comfy_mss/separate.js";

function applyColorSetup() {
  applyTypeColors(app);
  applyLinkColorPatch(app);
}

app.registerExtension({
  name: "comfy-mss.ui",

  setup() {
    applyColorSetup();
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    applyColorSetup();

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    function wrapOnNodeCreated(extra) {
      nodeType.prototype.onNodeCreated = function () {
        const result = originalOnNodeCreated?.apply(this, arguments);
        colorNodeSlots(this);
        extra?.call(this);
        return result;
      };
    }

    const originalOnConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (...args) {
      const result = originalOnConnectionsChange?.apply(this, args);
      const link = args[3];
      colorSlot(args[4]);
      colorLink(this.graph, link);
      colorNodeSlots(this);
      this.graph?.setDirtyCanvas?.(true, true);
      return result;
    };

    if (nodeData.name === LOAD_AUDIO_NODE_TYPE) {
      registerLoadAudioNode(nodeType, wrapOnNodeCreated, api);
      return;
    }

    if (nodeData.name === AUDIO_ENSEMBLE_NODE_TYPE) {
      registerAudioEnsembleNode(nodeType, wrapOnNodeCreated);
      return;
    }

    if (SEPARATE_NODE_TYPES.has(nodeData.name)) {
      registerSeparateNode(nodeType, wrapOnNodeCreated, api);
      return;
    }

    if (AUDIO_TOOL_NODE_TYPES.has(nodeData.name)) {
      registerAudioToolNode(wrapOnNodeCreated);
      return;
    }

    wrapOnNodeCreated();
  },
});
