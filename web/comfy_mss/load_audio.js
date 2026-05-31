import { getWidget } from "./utils.js";

function refreshComboWidget(widget, value) {
  if (Array.isArray(widget.options?.values) && !widget.options.values.includes(value)) {
    widget.options.values.push(value);
    widget.options.values.sort((left, right) => left.localeCompare(right));
  }
  widget.value = value;
  widget.callback?.(value);
}

function addAudioUploadButton(node, api) {
  const widget = getWidget(node, "audio");
  if (!widget || node.comfyMssUploadButtonAdded) {
    return;
  }
  node.comfyMssUploadButtonAdded = true;
  node.addWidget("button", "upload audio", null, async () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "audio/*,video/*,.wav,.flac,.mp3,.m4a,.ogg,.aac,.aiff,.aif,.wma,.opus";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) {
        return;
      }
      const body = new FormData();
      body.append("audio", file);
      const response = await api.fetchApi("/comfy-mss/upload-audio", {
        method: "POST",
        body,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      refreshComboWidget(widget, result.name);
      node.setDirtyCanvas(true, true);
    };
    input.click();
  });
}

export function registerLoadAudioNode(nodeType, wrapOnNodeCreated, api) {
  wrapOnNodeCreated(function () {
    addAudioUploadButton(this, api);
  });
}
