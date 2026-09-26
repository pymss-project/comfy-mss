let translationsPromise = null;
let translations = {};
const listeners = new Set();

function languageValue() {
  try { return window?.app?.ui?.settings?.getSettingValue?.("Comfy.Locale") || navigator.language; } catch (_) { return navigator.language; }
}

export function currentLanguage() {
  const value = String(languageValue() || "en").replaceAll("_", "-").toLowerCase();
  if (value.startsWith("zh-tw") || value.startsWith("zh-hk")) return "zh-TW";
  if (value.startsWith("zh")) return "zh";
  if (value.startsWith("ja")) return "ja";
  if (value.startsWith("ko")) return "ko";
  return "en";
}

export function languageChanged() {
  return false;
}

export function onTranslationsLoaded(listener) { listeners.add(listener); }

export function t(key, fallback = key) {
  return translations[currentLanguage()]?.comfyMss?.[key] ?? fallback;
}

export function translateNodeLabels(node, nodeType = node?.comfyClass ?? node?.type) {
  const locale = translations[currentLanguage()]?.nodeDefs?.[nodeType] ?? translations.en?.nodeDefs?.[nodeType];
  if (!locale || !node) return;
  if (locale.title) node.title = locale.title;
  for (const slot of node.inputs ?? []) slot.label = locale.inputs?.[slot.name] ?? slot.label;
  for (const slot of node.outputs ?? []) slot.label = locale.outputs?.[slot.name] ?? slot.label;
  for (const widget of node.widgets ?? []) widget.label = locale.widgets?.[widget.name] ?? widget.label;
  for (const widget of node.widgets ?? []) {
    if (widget.comfyMssI18nKey) {
      const label = t(widget.comfyMssI18nKey);
      widget.label = label;
      widget.localized_name = label;
    }
  }
}

export async function loadTranslations(api) {
  if (!translationsPromise) {
    translationsPromise = api.fetchApi("/i18n").then((r) => r.json()).then((data) => {
      translations = data ?? {};
      listeners.forEach((listener) => listener());
      return translations;
    });
  }
  return translationsPromise;
}

export function withTranslatedWidgetNames(node, callback) {
  const changed = [];
  try {
    for (const widget of node?.widgets ?? []) {
      const displayName = widget.localized_name ?? widget.displayName ?? widget.label;
      if (displayName && widget.name !== displayName) {
        changed.push([widget, widget.name]);
        widget.name = displayName;
      }
    }
    return callback();
  } finally {
    for (const [widget, name] of changed) {
      widget.name = name;
    }
  }
}

export function localizedModelDisplayName(model) {
  if (!model) {
    return "";
  }
  const language = currentLanguage();
  if (language === "zh" || language === "zh-TW") {
    return model.display_name_cn ?? model.display_name ?? model.name ?? "";
  }
  return model.display_name ?? model.name ?? "";
}
