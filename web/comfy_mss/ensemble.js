import { TYPE_COLORS } from "./constants.js";
import { colorSlot } from "./colors.js";
import { disconnectInput, getWidget } from "./utils.js";
import { setNodeWidth } from "./sizing.js";

function inputCountValue(node) {
  const widget = getWidget(node, "input_count");
  const value = Number.parseInt(widget?.value ?? "2", 10);
  return Math.max(2, Math.min(10, Number.isFinite(value) ? value : 2));
}

export function syncAudioEnsembleInputs(node) {
  const count = inputCountValue(node);
  const desired = Array.from({ length: count }, (_value, index) => `audio_${index + 1}`);

  node.inputs ||= [];
  for (let index = node.inputs.length - 1; index >= 0; index -= 1) {
    const input = node.inputs[index];
    const audioMatch = /^audio_(\d+)$/.exec(input.name ?? "");
    if (audioMatch && Number.parseInt(audioMatch[1], 10) > count) {
      if (typeof node.removeInput === "function") {
        node.removeInput(index);
      } else {
        disconnectInput(node, index);
        node.inputs.splice(index, 1);
      }
    }
  }

  for (const name of desired) {
    let input = node.inputs.find((candidate) => candidate.name === name);
    if (!input) {
      node.addInput(name, "AUDIO", {
        color_on: TYPE_COLORS.AUDIO,
        color_off: TYPE_COLORS.AUDIO,
      });
      input = node.inputs[node.inputs.length - 1];
    }
    colorSlot(input);
  }

  for (const widget of node.widgets ?? []) {
    const weightMatch = /^weight_(\d+)$/.exec(widget.name ?? "");
    if (weightMatch) {
      widget.hidden = Number.parseInt(weightMatch[1], 10) > count;
    }
  }
  setNodeWidth(node);
}

function scheduleSyncAudioEnsembleInputs(node) {
  setTimeout(() => syncAudioEnsembleInputs(node), 0);
  setTimeout(() => syncAudioEnsembleInputs(node), 250);
}

export function registerAudioEnsembleNode(nodeType, wrapOnNodeCreated) {
  wrapOnNodeCreated(function () {
    const widget = getWidget(this, "input_count");
    if (widget) {
      const callback = widget.callback;
      widget.callback = (value, canvas, node, pos, event) => {
        const callbackResult = callback?.call(widget, value, canvas, node, pos, event);
        scheduleSyncAudioEnsembleInputs(this);
        return callbackResult;
      };
    }
    scheduleSyncAudioEnsembleInputs(this);
  });

  const onConfigure = nodeType.prototype.onConfigure;
  nodeType.prototype.onConfigure = function (...args) {
    const result = onConfigure?.apply(this, args);
    scheduleSyncAudioEnsembleInputs(this);
    return result;
  };
}
