import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPES = new Set(["mss_separate", "vr_separate"]);
const MAX_STEMS = 64;
const MIN_NODE_WIDTH = 420;

let catalog = null;

async function getCatalog() {
  if (!catalog) {
    const response = await api.fetchApi("/comfy-mss/models?kind=all");
    const payload = await response.json();
    catalog = Array.isArray(payload) ? payload : payload.models;
  }
  return catalog;
}

function getWidget(node, name) {
  return node.widgets?.find((widget) => widget.name === name);
}

function modelKind(node) {
  return node.comfyClass === "vr_separate" ? "vr" : "mss";
}

async function stemsForNode(node) {
  const widget = getWidget(node, "model_name");
  const modelName = widget?.value;
  if (!modelName) {
    return null;
  }
  const kind = modelKind(node);
  const models = await getCatalog();
  const model = models.find((item) => item.name === modelName && (kind === "vr" ? item.model_type === "vr" : item.model_type !== "vr"));
  return model?.stems?.length ? model.stems : null;
}

function setOutputName(output, name) {
  output.name = name;
  output.label = name;
  output.localized_name = name;
  output.type = "AUDIO";
}

function outputHasLinks(output) {
  return Array.isArray(output?.links) && output.links.length > 0;
}

function syncOutputs(node, stems) {
  if (!stems?.length) {
    return;
  }

  const desired = stems.slice(0, MAX_STEMS);

  while ((node.outputs?.length ?? 0) > desired.length && !outputHasLinks(node.outputs[node.outputs.length - 1])) {
    node.removeOutput(node.outputs.length - 1);
  }

  const outputCount = Math.max(desired.length, node.outputs?.length ?? 0);
  for (let index = 0; index < outputCount; index += 1) {
    const name = desired[index] ?? node.outputs?.[index]?.name ?? `stem_${index + 1}`;
    if (!node.outputs?.[index]) {
      node.addOutput(name, "AUDIO");
      setOutputName(node.outputs[index], name);
    } else {
      setOutputName(node.outputs[index], name);
    }
  }

  node.setSize(node.computeSize());
  node.size[0] = Math.max(node.size[0], MIN_NODE_WIDTH);
  node.setDirtyCanvas(true, true);
}

async function refreshNodeOutputs(node) {
  try {
    syncOutputs(node, await stemsForNode(node));
  } catch (error) {
    console.warn("[comfy-mss] failed to refresh outputs", error);
  }
}

function scheduleRefreshNodeOutputs(node) {
  setTimeout(() => refreshNodeOutputs(node), 0);
}

app.registerExtension({
  name: "comfy-mss.dynamic-outputs",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODE_TYPES.has(nodeData.name)) {
      return;
    }

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      const widget = getWidget(this, "model_name");
      if (widget) {
        const callback = widget.callback;
        widget.callback = (value, canvas, node, pos, event) => {
          const callbackResult = callback?.call(widget, value, canvas, node, pos, event);
          scheduleRefreshNodeOutputs(this);
          return callbackResult;
        };
      }
      scheduleRefreshNodeOutputs(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      scheduleRefreshNodeOutputs(this);
      return result;
    };
  },
});
