import { FIXED_420_NODE_WIDTH, MSS_MAX_STEMS, TYPE_COLORS, VR_MAX_STEMS } from "./constants.js";
import { colorNodeSlots, typeColor } from "./colors.js";
import { currentLanguage, localizedModelDisplayName, t, translateNodeLabels } from "./i18n.js";
import { resizeNodeKeepingWidth } from "./sizing.js";
import { disconnectOutput, getWidget } from "./utils.js";

const catalogByKind = new Map();
const catalogPendingByKind = new Map();
const NOT_DOWNLOADED_PREFIX = "[Not downloaded] ";
const NOT_DOWNLOADED_COLOR = "#8a8a8a";
let notDownloadedDisplayNames = new Set();
let menuStyleObserver = null;
let notDownloadedByKey = new Map();

function catalogKey(node) {
  if (modelKind(node) !== "custom") {
    return "all";
  }
  return "custom";
}

export async function getCatalog(api, node, force = false) {
  const key = catalogKey(node);
  if (catalogPendingByKind.has(key)) {
    return catalogPendingByKind.get(key);
  }
  if (!force && catalogByKind.has(key)) {
    return catalogByKind.get(key);
  }

  const kind = modelKind(node) === "custom" ? "custom" : "all";
  const params = new URLSearchParams({ kind });
  const request = (async () => {
    const response = await api.fetchApi(`/comfy-mss/models?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to load model catalog: ${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    const catalog = Array.isArray(payload) ? payload : payload.models;
    catalogByKind.set(key, catalog);
    rebuildNotDownloadedDisplayNames();
    styleOpenModelMenus();
    return catalog;
  })();
  catalogPendingByKind.set(key, request);
  try {
    return await request;
  } finally {
    if (catalogPendingByKind.get(key) === request) {
      catalogPendingByKind.delete(key);
    }
  }
}

function rebuildNotDownloadedDisplayNames() {
  notDownloadedByKey = new Map();
  for (const [key, catalog] of catalogByKind.entries()) {
    notDownloadedByKey.set(
      key,
      new Set(
        catalog
          .filter((item) => item.downloaded === false)
          .map((item) => String(localizedModelDisplayName(item)).trim())
      )
    );
  }
  notDownloadedDisplayNames = new Set([...notDownloadedByKey.values()].flatMap((names) => [...names]));
}

function modelKind(node) {
  if (
    node.comfyClass === "pymss_custom_mss_separate" ||
    node.type === "pymss_custom_mss_separate" ||
    node.comfyClass === "pymss_custom_mss_separate_list" ||
    node.type === "pymss_custom_mss_separate_list"
  ) {
    return "custom";
  }
  return (
    node.comfyClass === "pymss_vr_separate" ||
    node.type === "pymss_vr_separate" ||
    node.comfyClass === "pymss_vr_separate_list" ||
    node.type === "pymss_vr_separate_list"
  )
    ? "vr"
    : "mss";
}

function isListNode(node) {
  return String(node.comfyClass ?? node.type ?? "").endsWith("_list");
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
    .replace(/^\[[^\]]+\]\s*/, "")
    .replaceAll("\\", "/")
    .split("/")
    .pop()
    .trim()
    .toLowerCase();
}

export function matchesModelName(item, modelName) {
  const target = normalizeModelName(modelName);
  const names = [item?.name, item?.display_name, item?.display_name_cn, ...(item?.aliases ?? [])]
    .map(normalizeModelName)
    .filter(Boolean);
  return Boolean(target) && names.includes(target);
}

function modelsForNode(models, node) {
  const kind = modelKind(node);
  if (kind === "custom") {
    return models;
  }
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

async function refreshModelWidgetOptions(node, api, force = false) {
  const widget = getWidget(node, "model_name");
  if (!widget) {
    return false;
  }
  const models = modelsForNode(await getCatalog(api, node, force), node);
  const values = models.map((item) => localizedModelDisplayName(item));
  const currentName = cleanModelDisplayName(widget.value);
  const currentModel = models.find((item) => matchesModelName(item, currentName));

  widget.options ||= {};
  widget.options.values = values;
  if (currentModel) {
    widget.value = localizedModelDisplayName(currentModel);
  } else if (widget.value && !values.includes(widget.value)) {
    widget.options.values = [widget.value, ...values];
  } else if (!widget.value && values.length) {
    widget.value = values[0];
  }

  node.setDirtyCanvas(true, true);
  return true;
}

export async function tryRefreshModelWidgetOptions(node, api, force = false) {
  try {
    return await refreshModelWidgetOptions(node, api, force);
  } catch (error) {
    console.warn("[comfy-mss] failed to refresh model options", error);
    return false;
  }
}

async function stemsForNode(node, api) {
  const widget = getWidget(node, "model_name");
  const modelName = widget?.value;
  if (!modelName) {
    return null;
  }
  const kind = modelKind(node);
  const models = await getCatalog(api, node);
  const model = models.find(
    (item) => matchesModelName(item, modelName) && (kind === "vr" ? item.model_type === "vr" : item.model_type !== "vr")
  );
  if (!model) {
    console.warn("[comfy-mss] model not found in catalog", { modelName, kind });
  }
  if (model?.stems_complete === false) {
    return null;
  }
  return model?.stems?.length ? model.stems : null;
}

function setOutput(output, name, type) {
  output.name = name;
  output.label = name;
  output.type = type;
  const color = typeColor(type);
  output.color_on = color ?? output.color_on;
  output.color_off = color ?? output.color_off;
  output.color = color ?? output.color;
}

export function syncOutputs(node, stems) {
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
    if (typeof node.removeOutput === "function") {
      node.removeOutput(index);
    } else {
      disconnectOutput(node, index);
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

  translateNodeLabels(node);
  resizeNodeKeepingWidth(node, FIXED_420_NODE_WIDTH);
  colorNodeSlots(node);
  node.arrange?.();
  node.graph?.setDirtyCanvas?.(true, true);
  node.setDirtyCanvas(true, true);
}

export async function refreshNodeOutputs(node, api, generation = node.comfyMssOutputRefreshGeneration ?? 0) {
  if (isListNode(node)) {
    return;
  }
  const selectedModel = getWidget(node, "model_name")?.value;
  try {
    const stems = await stemsForNode(node, api);
    if (
      generation !== (node.comfyMssOutputRefreshGeneration ?? 0) ||
      selectedModel !== getWidget(node, "model_name")?.value
    ) {
      return;
    }
    syncOutputs(node, stems);
  } catch (error) {
    console.warn("[comfy-mss] failed to refresh outputs", error);
  }
}

function scheduleRefreshNodeOutputs(node, api) {
  const generation = (node.comfyMssOutputRefreshGeneration ?? 0) + 1;
  node.comfyMssOutputRefreshGeneration = generation;
  setTimeout(() => refreshNodeOutputs(node, api, generation), 0);
  setTimeout(() => refreshNodeOutputs(node, api, generation), 250);
  setTimeout(() => refreshNodeOutputs(node, api, generation), 1000);
  setTimeout(() => refreshNodeOutputs(node, api, generation), 2000);
}

function addRefreshModelsButton(node, api) {
  if (node.comfyMssRefreshModelsButtonAdded) {
    return;
  }
  node.comfyMssRefreshModelsButtonAdded = true;
  const button = node.addWidget("button", t("refreshModels", "Refresh Models"), null, async () => {
    if (await tryRefreshModelWidgetOptions(node, api, true)) {
      scheduleRefreshNodeOutputs(node, api);
    }
  });
  button.comfyMssI18nKey = "refreshModels";
}

function syncLanguage(node, api) {
  const language = currentLanguage();
  if (node.comfyMssSeparateLanguage === language) {
    translateNodeLabels(node);
    return;
  }
  node.comfyMssSeparateLanguage = language;
  rebuildNotDownloadedDisplayNames();
  for (const widget of node.widgets ?? []) {
    if (widget.comfyMssI18nKey) {
      const label = t(widget.comfyMssI18nKey, widget.label);
      widget.label = label;
      widget.localized_name = label;
    }
  }
  const finishRefresh = () => {
    scheduleRefreshNodeOutputs(node, api);
    translateNodeLabels(node);
  };
  tryRefreshModelWidgetOptions(node, api).then((refreshed) => {
    if (refreshed) {
      finishRefresh();
      return;
    }
    setTimeout(async () => {
      if (node.comfyMssSeparateLanguage !== language) {
        return;
      }
      if (await tryRefreshModelWidgetOptions(node, api)) {
        finishRefresh();
      }
    }, 1000);
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
    tryRefreshModelWidgetOptions(this, api).then((refreshed) => {
      if (refreshed) scheduleRefreshNodeOutputs(this, api);
    });
    scheduleRefreshNodeOutputs(this, api);
    syncLanguage(this, api);
  });

  const onConfigure = nodeType.prototype.onConfigure;
  nodeType.prototype.onConfigure = function (...args) {
    const result = onConfigure?.apply(this, args);
    colorNodeSlots(this);
    setTimeout(() => {
      addRefreshModelsButton(this, api);
      tryRefreshModelWidgetOptions(this, api).then((refreshed) => {
        if (refreshed) scheduleRefreshNodeOutputs(this, api);
      });
      syncLanguage(this, api);
    }, 0);
    scheduleRefreshNodeOutputs(this, api);
    return result;
  };

  const onDrawForeground = nodeType.prototype.onDrawForeground;
  nodeType.prototype.onDrawForeground = function (...args) {
    syncLanguage(this, api);
    colorNodeSlots(this);
    return onDrawForeground?.apply(this, args);
  };
}
