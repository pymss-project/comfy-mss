import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPES = new Set(["mss_separate", "vr_separate"]);
const MAX_STEMS = 64;

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
  const kind = modelKind(node);
  const models = await getCatalog();
  const model = models.find((item) => item.name === modelName && (kind === "vr" ? item.model_type === "vr" : item.model_type !== "vr"));
  return model?.stems?.length ? model.stems : ["audio"];
}

function setOutputName(output, name) {
  output.name = name;
  output.label = name;
  output.localized_name = name;
  output.type = "AUDIO";
}

function syncOutputs(node, stems) {
  const desired = stems.slice(0, MAX_STEMS);

  while ((node.outputs?.length ?? 0) > desired.length) {
    node.removeOutput(node.outputs.length - 1);
  }

  for (let index = 0; index < desired.length; index += 1) {
    const name = desired[index];
    if (!node.outputs?.[index]) {
      node.addOutput(name, "AUDIO");
      setOutputName(node.outputs[index], name);
    } else {
      setOutputName(node.outputs[index], name);
    }
  }

  node.setSize(node.computeSize());
  node.setDirtyCanvas(true, true);
}

async function refreshNodeOutputs(node) {
  try {
    syncOutputs(node, await stemsForNode(node));
  } catch (error) {
    console.warn("[comfy-mss] failed to refresh outputs", error);
  }
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
          refreshNodeOutputs(this);
          return callbackResult;
        };
      }
      refreshNodeOutputs(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      refreshNodeOutputs(this);
      return result;
    };
  },
});
