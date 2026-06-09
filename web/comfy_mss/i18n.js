const LANGUAGE_PREFIXES = {
  en: ["en", "en-us", "en-gb", "english"],
  "zh-TW": ["zh-tw", "zh-hk", "zh-mo", "zh-hant", "zh-hant-tw", "zh-hant-hk", "zh-hant-mo", "tw", "hk"],
  zh: ["zh", "zh-cn", "zh-hans", "zh-hans-cn", "cn", "chinese", "simplified chinese"],
  ja: ["ja", "ja-jp", "jp", "japanese"],
  ko: ["ko", "ko-kr", "kr", "korean"],
};

const STRINGS = {
  en: {
    refreshModels: "Refresh Models",
    uploadAudio: "Upload Audio",
    notDownloaded: "Not downloaded",
  },
  zh: {
    refreshModels: "刷新模型",
    uploadAudio: "上传音频",
    notDownloaded: "未下载",
  },
  "zh-TW": {
    refreshModels: "重新整理模型",
    uploadAudio: "上傳音訊",
    notDownloaded: "未下載",
  },
  ja: {
    refreshModels: "モデルを更新",
    uploadAudio: "音声をアップロード",
    notDownloaded: "未ダウンロード",
  },
  ko: {
    refreshModels: "모델 새로고침",
    uploadAudio: "오디오 업로드",
    notDownloaded: "다운로드 안 됨",
  },
};

let translationsPromise = null;
let translations = null;
let lastLanguage = null;
const listeners = new Set();

function readSetting(key) {
  try {
    return window?.app?.ui?.settings?.getSettingValue?.(key);
  } catch (_error) {
    return null;
  }
}

function normalizeLanguageValue(candidate) {
  const value = String(candidate ?? "").trim().toLowerCase();
  if (!value) {
    return "";
  }
  return value.replaceAll("_", "-");
}

function languageFromValue(candidate) {
  const value = normalizeLanguageValue(candidate);
  if (!value) {
    return null;
  }
  for (const [language, prefixes] of Object.entries(LANGUAGE_PREFIXES)) {
    if (prefixes.some((prefix) => value === prefix || value.startsWith(`${prefix}-`))) {
      return language;
    }
  }
  return null;
}

export function currentLanguage() {
  const settingCandidates = [
    readSetting("Comfy.Locale"),
    readSetting("Comfy.Language"),
    readSetting("Comfy.Locale.Language"),
    readSetting("ComfyUI.Locale"),
    readSetting("ComfyUI.Language"),
    readSetting("AGL.Locale"),
    readSetting("AGL.Language"),
  ];

  for (const candidate of settingCandidates) {
    const language = languageFromValue(candidate);
    if (language) {
      return language;
    }
  }

  for (const candidate of [document.documentElement?.lang, navigator.language, ...(navigator.languages ?? [])]) {
    const language = languageFromValue(candidate);
    if (language) {
      return language;
    }
  }

  return "en";
}

export function languageChanged() {
  const language = currentLanguage();
  const changed = lastLanguage !== null && lastLanguage !== language;
  lastLanguage = language;
  return changed;
}

export function onTranslationsLoaded(listener) {
  listeners.add(listener);
}

function notifyTranslationsLoaded() {
  for (const listener of listeners) {
    try {
      listener();
    } catch (error) {
      console.warn("[comfy-mss] i18n listener failed", error);
    }
  }
}

export function t(key) {
  const language = currentLanguage();
  return STRINGS[language]?.[key] ?? STRINGS.en[key] ?? key;
}

function localeCodes(language = currentLanguage()) {
  if (language === "zh-TW") {
    return ["zh-TW", "zh-tw", "zh_HANT", "zh-Hant", "zh"];
  }
  if (language === "zh") {
    return ["zh", "zh-CN", "zh-cn"];
  }
  return [language, language.toLowerCase(), "en"];
}

export async function loadTranslations(api) {
  if (!translationsPromise) {
    translationsPromise = api
      .fetchApi("/i18n")
      .then((response) => response.json())
      .then((payload) => {
        translations = payload ?? {};
        notifyTranslationsLoaded();
        return translations;
      })
      .catch((error) => {
        console.warn("[comfy-mss] failed to load i18n translations", error);
        translations = {};
        return translations;
      });
  }
  return translationsPromise;
}

function nodeLocale(nodeType, language = currentLanguage()) {
  const all = translations ?? {};
  for (const code of localeCodes(language)) {
    const locale = all[code]?.nodeDefs?.[nodeType];
    if (locale) {
      return locale;
    }
  }
  return all.en?.nodeDefs?.[nodeType] ?? null;
}

export function translateNodeLabels(node, nodeType = node?.comfyClass ?? node?.type) {
  const locale = nodeLocale(nodeType);
  if (!locale || !node) {
    return;
  }

  if (locale.title) {
    node.title = locale.title;
  }

  const applyLabel = (slot, value) => {
    if (!slot || value === undefined) {
      return;
    }
    slot.label = value;
    slot.localized_name = value;
  };

  for (const input of node.inputs ?? []) {
    applyLabel(input, locale.inputs?.[input.name]);
  }

  for (const output of node.outputs ?? []) {
    applyLabel(output, locale.outputs?.[output.name]);
  }

  for (const widget of node.widgets ?? []) {
    const label = locale.widgets?.[widget.name] ?? locale.inputs?.[widget.name];
    if (label !== undefined) {
      widget.comfyMssOriginalName ??= widget.name;
      widget.label = label;
      widget.localized_name = label;
    }
    if (widget.name === "Refresh Models") {
      widget.label = t("refreshModels");
      widget.localized_name = t("refreshModels");
    }
    if (widget.name === "Upload Audio") {
      widget.label = t("uploadAudio");
      widget.localized_name = t("uploadAudio");
    }
  }

  node.setDirtyCanvas?.(true, true);
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
  if (currentLanguage().startsWith("zh")) {
    return model.display_name_cn ?? model.display_name ?? model.name ?? "";
  }
  return model.display_name ?? model.name ?? "";
}
