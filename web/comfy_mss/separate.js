import { MSS_MAX_STEMS, SEPARATE_MIN_NODE_WIDTH, TYPE_COLORS, VR_MAX_STEMS } from "./constants.js";
import { colorNodeSlots, typeColor } from "./colors.js";
import { disconnectOutput, getWidget } from "./utils.js";

let catalog = null;
const NOT_DOWNLOADED_PREFIX = "[Not downloaded] ";
const NOT_DOWNLOADED_COLOR = "#8a8a8a";
let notDownloadedDisplayNames = new Set();
let menuStyleObserver = null;

async function getCatalog(api, force = false) {
  if (force || !catalog) {
    const response = await api.fetchApi("/comfy-mss/models?kind=all");
    const payload = await response.json();
    catalog = Array.isArray(payload) ? payload : payload.models;
    notDownloadedDisplayNames = new Set(
      catalog
        .filter((item) => item.downloaded === false)
        .map((item) => String(item.display_name ?? item.name).trim())
    );
    styleOpenModelMenus();
  }
  return catalog;
}

function modelKind(node) {
  return node.comfyClass === "vr_separate" || node.type === "vr_separate" ? "vr" : "mss";
}

function maxStems(node) {
  return modelKind(node) === "vr" ? VR_MAX_STEMS : MSS_MAX_STEMS;
}

function cleanModelDisplayName(value) {
  const text = String(value ?? "").trim();
  return text.startsWith(NOT_DOWNLOADED_PREFIX) ? text.slice(NOT_DOWNLOADED_PREFIX.length).trim() : text;
}

function normalizeModelName(value) {
  return cleanModelDisplayName(value)
    .replaceAll("\\", "/")
    .split("/")
    .pop()
    .trim()
    .toLowerCase();
}

function matchesModelName(item, modelName) {
  const target = normalizeModelName(modelName);
  const names = [item?.name, ...(item?.aliases ?? [])].map(normalizeModelName);
  return names.some((name) => target === name || target.endsWith(name));
}

function modelsForNode(models, node) {
  const kind = modelKind(node);
  return models.filter((item) => (kind === "vr" ? item.model_type === "vr" : item.model_type !== "vr"));
}

function styleOpenModelMenus() {
  if (!notDownloadedDisplayNames.size) {
    return;
  }
  for (const item of document.querySelectorAll(".litecontextmenu .litemenu-entry")) {
    const text = String(item.textContent ?? "").trim();
    if (notDownloadedDisplayNames.has(text)) {
      item.style.color = NOT_DOWNLOADED_COLOR;
      item.title = "Not downloaded";
    }
  }
}

function ensureModelMenuStyleObserver() {
  if (menuStyleObserver) {
    return;
  }
  menuStyleObserver = new MutationObserver(() => styleOpenModelMenus());
  menuStyleObserver.observe(document.body, {
    childList: true,
    subtree: true,
  });
}

async function refreshModelWidgetOptions(node, api) {
  const widget = getWidget(node, "model_name");
  if (!widget) {
    return;
  }
  const models = modelsForNode(await getCatalog(api, true), node);
  const values = models.map((item) => item.display_name ?? item.name);
  const currentName = cleanModelDisplayName(widget.value);
  const currentModel = models.find((item) => matchesModelName(item, currentName));

  widget.options ||= {};
  widget.options.values = values;
  if (currentModel) {
    widget.value = currentModel.display_name ?? currentModel.name;
  } else if (widget.value && !values.includes(widget.value)) {
    widget.options.values = [widget.value, ...values];
  } else if (!widget.value && values.length) {
    widget.value = values[0];
  }

  node.setDirtyCanvas(true, true);
}

async function stemsForNode(node, api) {
  const widget = getWidget(node, "model_name");
  const modelName = widget?.value;
  if (!modelName) {
    return null;
  }
  const kind = modelKind(node);
  const models = await getCatalog(api);
  const model = models.find(
    (item) => matchesModelName(item, modelName) && (kind === "vr" ? item.model_type === "vr" : item.model_type !== "vr")
  );
  if (!model) {
    console.warn("[comfy-mss] model not found in catalog", { modelName, kind });
  }
  return model?.stems?.length ? model.stems : null;
}

function setOutput(output, name, type) {
  output.name = name;
  output.label = name;
  output.localized_name = name;
  output.type = type;
  const color = typeColor(type);
  output.color_on = color ?? output.color_on;
  output.color_off = color ?? output.color_off;
  output.color = color ?? output.color;
}

function syncOutputs(node, stems) {
  if (!stems?.length) {
    if (modelKind(node) === "vr") {
      stems = ["primary", "secondary"];
    } else {
      return;
    }
  }

  const visibleStems = stems.slice(0, maxStems(node));
  const desired = visibleStems.flatMap((stem) => [
    { name: `${stem} (Audio)`, type: "AUDIO" },
    { name: `${stem} (String)`, type: "STRING" },
  ]);

  for (let index = (node.outputs?.length ?? 0) - 1; index >= desired.length; index -= 1) {
    disconnectOutput(node, index);
    if (typeof node.removeOutput === "function") {
      node.removeOutput(index);
    } else {
      node.outputs?.splice(index, 1);
    }
  }

  node.outputs ||= [];
  node.outputs.length = Math.min(node.outputs.length, desired.length);
  for (let index = 0; index < desired.length; index += 1) {
    const outputInfo = desired[index];
    if (!node.outputs[index]) {
      node.addOutput(outputInfo.name, outputInfo.type, {
        color_on: TYPE_COLORS[outputInfo.type],
        color_off: TYPE_COLORS[outputInfo.type],
      });
    }
    setOutput(node.outputs[index], outputInfo.name, outputInfo.type);
  }

  node.setSize(node.computeSize());
  node.size[0] = Math.max(node.size[0], SEPARATE_MIN_NODE_WIDTH);
  colorNodeSlots(node);
  node.arrange?.();
  node.graph?.setDirtyCanvas?.(true, true);
  node.setDirtyCanvas(true, true);
}

async function refreshNodeOutputs(node, api) {
  try {
    syncOutputs(node, await stemsForNode(node, api));
  } catch (error) {
    console.warn("[comfy-mss] failed to refresh outputs", error);
  }
}

function scheduleRefreshNodeOutputs(node, api) {
  setTimeout(() => refreshNodeOutputs(node, api), 0);
  setTimeout(() => refreshNodeOutputs(node, api), 250);
  setTimeout(() => refreshNodeOutputs(node, api), 1000);
  setTimeout(() => refreshNodeOutputs(node, api), 2000);
}

function addRefreshModelsButton(node, api) {
  if (node.comfyMssRefreshModelsButtonAdded) {
    return;
  }
  node.comfyMssRefreshModelsButtonAdded = true;
  node.addWidget("button", "refresh models", null, async () => {
    await refreshModelWidgetOptions(node, api);
    scheduleRefreshNodeOutputs(node, api);
  });
}

export function registerSeparateNode(nodeType, wrapOnNodeCreated, api) {
  wrapOnNodeCreated(function () {
    ensureModelMenuStyleObserver();
    addRefreshModelsButton(this, api);
    const widget = getWidget(this, "model_name");
    if (widget) {
      const callback = widget.callback;
      widget.callback = (value, canvas, node, pos, event) => {
        const callbackResult = callback?.call(widget, value, canvas, node, pos, event);
        scheduleRefreshNodeOutputs(this, api);
        return callbackResult;
      };
    }
    refreshModelWidgetOptions(this, api).then(() => scheduleRefreshNodeOutputs(this, api));
    scheduleRefreshNodeOutputs(this, api);
  });

  const onConfigure = nodeType.prototype.onConfigure;
  nodeType.prototype.onConfigure = function (...args) {
    const result = onConfigure?.apply(this, args);
    colorNodeSlots(this);
    setTimeout(() => {
      addRefreshModelsButton(this, api);
      refreshModelWidgetOptions(this, api).then(() => scheduleRefreshNodeOutputs(this, api));
    }, 0);
    scheduleRefreshNodeOutputs(this, api);
    return result;
  };

  const onDrawForeground = nodeType.prototype.onDrawForeground;
  nodeType.prototype.onDrawForeground = function (...args) {
    colorNodeSlots(this);
    return onDrawForeground?.apply(this, args);
  };
}
