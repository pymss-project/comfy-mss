import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

import { applyLinkColorPatch, applyTypeColors, colorLink, colorNodeSlots, colorSlot } from "./comfy_mss/colors.js";
import {
  AUDIO_ENSEMBLE_NODE_TYPE,
  AUDIO_TOOL_NODE_TYPES,
  FIXED_260_NODE_TYPES,
  LOAD_AUDIO_NODE_TYPE,
  SAVE_AUDIO_NODE_TYPE,
  SEPARATE_LIST_NODE_TYPES,
  SEPARATE_NODE_TYPES,
} from "./comfy_mss/constants.js";
import { registerAudioToolNode } from "./comfy_mss/audio_tools.js";
import { registerAudioEnsembleNode } from "./comfy_mss/ensemble.js";
import { registerLoadAudioNode } from "./comfy_mss/load_audio.js";
import { registerSaveAudioNode } from "./comfy_mss/save_audio.js";
import { registerSeparateNode } from "./comfy_mss/separate.js";
import { registerFixedWidthNode } from "./comfy_mss/sizing.js";
import {
  currentLanguage,
  loadTranslations,
  onTranslationsLoaded,
  t,
  translateNodeLabels,
  withTranslatedWidgetNames,
} from "./comfy_mss/i18n.js";

function applyColorSetup() {
  applyTypeColors(app);
  applyLinkColorPatch(app);
}

const COMFY_MSS_NODE_TYPES = new Set([
  ...SEPARATE_NODE_TYPES,
  ...SEPARATE_LIST_NODE_TYPES,
  ...AUDIO_TOOL_NODE_TYPES,
  ...FIXED_260_NODE_TYPES,
  LOAD_AUDIO_NODE_TYPE,
  AUDIO_ENSEMBLE_NODE_TYPE,
  SAVE_AUDIO_NODE_TYPE,
]);

function refreshNodeLanguage(node, nodeName) {
  const language = currentLanguage();
  if (node.comfyMssLanguage === language) {
    translateNodeLabels(node, nodeName);
    return;
  }
  node.comfyMssLanguage = language;
  for (const widget of node.widgets ?? []) {
    if (widget.comfyMssI18nKey) {
      const label = t(widget.comfyMssI18nKey);
      widget.label = label;
      widget.localized_name = label;
    }
  }
  translateNodeLabels(node, nodeName);
}

function refreshGraphLanguage() {
  for (const node of app.graph?._nodes ?? []) {
    const nodeName = node?.comfyClass ?? node?.type;
    if (!COMFY_MSS_NODE_TYPES.has(nodeName)) {
      continue;
    }
    refreshNodeLanguage(node, nodeName);
  }
  app.graph?.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "comfy-mss.ui",

  setup() {
    applyColorSetup();
    loadTranslations(api);
    onTranslationsLoaded(refreshGraphLanguage);
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    applyColorSetup();
    loadTranslations(api);

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    function wrapOnNodeCreated(extra) {
      nodeType.prototype.onNodeCreated = function () {
        const result = originalOnNodeCreated?.apply(this, arguments);
        colorNodeSlots(this);
        extra?.call(this);
        refreshNodeLanguage(this, nodeData.name);
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

    if (!COMFY_MSS_NODE_TYPES.has(nodeData.name)) {
      return;
    }

    const originalOnDrawForeground = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (...args) {
      refreshNodeLanguage(this, nodeData.name);
      return withTranslatedWidgetNames(this, () => originalOnDrawForeground?.apply(this, args));
    };

    const originalOnDrawBackground = nodeType.prototype.onDrawBackground;
    nodeType.prototype.onDrawBackground = function (...args) {
      refreshNodeLanguage(this, nodeData.name);
      return withTranslatedWidgetNames(this, () => originalOnDrawBackground?.apply(this, args));
    };

    if (nodeData.name === LOAD_AUDIO_NODE_TYPE) {
      registerLoadAudioNode(nodeType, wrapOnNodeCreated, api);
      return;
    }

    if (nodeData.name === AUDIO_ENSEMBLE_NODE_TYPE) {
      registerAudioEnsembleNode(nodeType, wrapOnNodeCreated);
      return;
    }

    if (SEPARATE_NODE_TYPES.has(nodeData.name) || SEPARATE_LIST_NODE_TYPES.has(nodeData.name)) {
      registerSeparateNode(nodeType, wrapOnNodeCreated, api);
      return;
    }

    if (AUDIO_TOOL_NODE_TYPES.has(nodeData.name)) {
      registerAudioToolNode(wrapOnNodeCreated);
      return;
    }

    if (nodeData.name === SAVE_AUDIO_NODE_TYPE) {
      registerSaveAudioNode(nodeType, wrapOnNodeCreated);
      return;
    }

    if (FIXED_260_NODE_TYPES.has(nodeData.name)) {
      registerFixedWidthNode(wrapOnNodeCreated);
      return;
    }

  },
});
