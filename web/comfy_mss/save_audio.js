import { getWidget } from "./utils.js";
import { setNodeWidth } from "./sizing.js";

const FORMAT_WIDGETS = {
  wav: new Set(["wav_bit_depth"]),
  flac: new Set(["flac_bit_depth"]),
  mp3: new Set(["mp3_bit_rate"]),
};

function syncSaveAudioWidgets(node) {
  const format = String(getWidget(node, "output_format")?.value ?? "wav").toLowerCase();
  const visible = FORMAT_WIDGETS[format] ?? FORMAT_WIDGETS.wav;

  for (const widget of node.widgets ?? []) {
    if (widget.name === "wav_bit_depth" || widget.name === "flac_bit_depth" || widget.name === "mp3_bit_rate") {
      widget.hidden = !visible.has(widget.name);
    }
  }

  setNodeWidth(node);
}

function scheduleSyncSaveAudioWidgets(node) {
  setTimeout(() => syncSaveAudioWidgets(node), 0);
  setTimeout(() => syncSaveAudioWidgets(node), 250);
}

export function registerSaveAudioNode(nodeType, wrapOnNodeCreated) {
  wrapOnNodeCreated(function () {
    const widget = getWidget(this, "output_format");
    if (widget) {
      const callback = widget.callback;
      widget.callback = (value, canvas, node, pos, event) => {
        const callbackResult = callback?.call(widget, value, canvas, node, pos, event);
        scheduleSyncSaveAudioWidgets(this);
        return callbackResult;
      };
    }
    scheduleSyncSaveAudioWidgets(this);
  });

  const onConfigure = nodeType.prototype.onConfigure;
  nodeType.prototype.onConfigure = function (...args) {
    const result = onConfigure?.apply(this, args);
    scheduleSyncSaveAudioWidgets(this);
    return result;
  };
}
