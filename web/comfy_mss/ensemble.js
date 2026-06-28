import { TYPE_COLORS } from "./constants.js";
import { colorSlot } from "./colors.js";
import { disconnectInput, getWidget } from "./utils.js";
import { setNodeWidth } from "./sizing.js";

function inputCountValue(node) {
  const widget = getWidget(node, "input_count");
  const value = Number.parseInt(widget?.value ?? "2", 10);
  return Math.max(2, Math.min(10, Number.isFinite(value) ? value : 2));
}

function syncAudioEnsembleInputs(node) {
  const count = inputCountValue(node);
  const desired = Array.from({ length: count }, (_value, index) => `audio_${index + 1}`);

  node.inputs ||= [];
  for (let index = node.inputs.length - 1; index >= 0; index -= 1) {
    const input = node.inputs[index];
    const audioMatch = /^audio_(\d+)$/.exec(input.name ?? "");
    if (audioMatch && Number.parseInt(audioMatch[1], 10) > count) {
      disconnectInput(node, index);
      if (typeof node.removeInput === "function") {
        node.removeInput(index);
      } else {
        node.inputs.splice(index, 1);
      }
    }
  }

  for (let index = 0; index < desired.length; index += 1) {
    const name = desired[index];
    if (!node.inputs[index] || node.inputs[index].name !== name) {
      const existingIndex = node.inputs.findIndex((input) => input.name === name);
      if (existingIndex >= 0) {
        const [existing] = node.inputs.splice(existingIndex, 1);
        node.inputs.splice(index, 0, existing);
      } else {
        node.addInput(name, "AUDIO", {
          color_on: TYPE_COLORS.AUDIO,
          color_off: TYPE_COLORS.AUDIO,
        });
        const [created] = node.inputs.splice(node.inputs.length - 1, 1);
        node.inputs.splice(index, 0, created);
      }
    }
    colorSlot(node.inputs[index]);
  }
  node.inputs.length = desired.length;

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
