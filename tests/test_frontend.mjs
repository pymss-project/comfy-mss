import assert from "node:assert/strict";
import test from "node:test";

import { colorNodeSlots } from "../web/comfy_mss/colors.js";
import { syncAudioEnsembleInputs } from "../web/comfy_mss/ensemble.js";
import { localizedModelDisplayName } from "../web/comfy_mss/i18n.js";
import { uploadAudioFile } from "../web/comfy_mss/load_audio.js";
import {
  getCatalog,
  matchesModelName,
  refreshNodeOutputs,
  syncOutputs,
  tryRefreshModelWidgetOptions,
} from "../web/comfy_mss/separate.js";


test("missing optional model labels never match an unrelated custom model", () => {
  const customA = { name: "Custom-A", display_name: "Custom-A" };
  assert.equal(matchesModelName(customA, "Custom-B"), false);
});


test("model matching rejects filename suffix collisions", () => {
  const short = {
    name: "duality_v1.ckpt",
    display_name: "[vocal/vocal_instrumental_dual] duality_v1.ckpt",
  };
  assert.equal(matchesModelName(short, "[vocal/vocal_instrumental_dual] melband_roformer_instvoc_duality_v1.ckpt"), false);
});


test("missing custom models preserve serialized outputs and links", () => {
  let disconnected = false;
  const outputs = [{ name: "vocals (Audio)", links: [12] }];
  const node = {
    comfyClass: "pymss_custom_mss_separate",
    outputs,
    disconnectOutput() {
      disconnected = true;
    },
  };

  syncOutputs(node, null);

  assert.equal(disconnected, false);
  assert.equal(node.outputs, outputs);
  assert.equal(node.outputs[0].links[0], 12);
});


test("Chinese locales use the catalog Chinese display name", () => {
  globalThis.window = {
    app: { ui: { settings: { getSettingValue: () => "zh-CN" } } },
  };
  assert.equal(
    localizedModelDisplayName({
      name: "model.ckpt",
      display_name: "[vocal] model.ckpt",
      display_name_cn: "[人声] model.ckpt",
    }),
    "[人声] model.ckpt",
  );
});


test("audio uploads use the official ComfyUI endpoint", async () => {
  const OriginalFormData = globalThis.FormData;
  const fields = [];
  globalThis.FormData = class {
    append(name, value) {
      fields.push([name, value]);
    }
  };
  let request;
  try {
    const result = await uploadAudioFile(
      {
        fetchApi: async (path, options) => {
          request = { path, options };
          return { ok: true, json: async () => ({ name: "song.wav" }) };
        },
      },
      { name: "song.wav" },
    );
    assert.deepEqual(result, { name: "song.wav" });
  } finally {
    globalThis.FormData = OriginalFormData;
  }

  assert.equal(request.path, "/upload/image");
  assert.equal(request.options.method, "POST");
  assert.deepEqual(fields.map(([name]) => name), ["image", "type"]);
  assert.equal(fields[1][1], "input");
});


test("ensemble input sync preserves widget sockets and only removes excess audio inputs", () => {
  let disconnected = 0;
  const inputCount = { name: "input_count", value: "2" };
  const node = {
    widgets: [inputCount, { name: "weight_1" }, { name: "weight_2" }],
    inputs: [
      { name: "weight_1", type: "FLOAT", link: 11, widget: { name: "weight_1" } },
      { name: "audio_1", type: "AUDIO" },
      { name: "audio_2", type: "AUDIO" },
      { name: "audio_3", type: "AUDIO", link: 12 },
    ],
    size: [260, 200],
    computeSize: () => [260, 200],
    setSize() {},
    setDirtyCanvas() {},
    disconnectInput() {
      disconnected += 1;
    },
    removeInput(index) {
      this.disconnectInput(index);
      this.inputs.splice(index, 1);
    },
    addInput(name, type, options) {
      this.inputs.push({ name, type, ...options });
    },
  };

  syncAudioEnsembleInputs(node);
  assert.deepEqual(node.inputs.map((input) => input.name), ["weight_1", "audio_1", "audio_2"]);
  assert.equal(node.inputs[0].link, 11);
  assert.equal(disconnected, 1);

  inputCount.value = "3";
  syncAudioEnsembleInputs(node);
  assert.deepEqual(node.inputs.map((input) => input.name), ["weight_1", "audio_1", "audio_2", "audio_3"]);
});


test("coloring one node does not traverse every graph link", () => {
  const graph = {};
  Object.defineProperty(graph, "links", {
    get() {
      throw new Error("graph links should not be scanned");
    },
  });
  const node = {
    graph,
    inputs: [{ type: "AUDIO" }],
    outputs: [{ type: "STRING" }],
  };

  colorNodeSlots(node);

  assert.equal(node.inputs[0].color, "#22c55e");
  assert.equal(node.outputs[0].color, "#f2c94c");
});


test("stale model refresh cannot disconnect outputs for the current selection", async () => {
  globalThis.window = {
    app: { ui: { settings: { getSettingValue: () => "en" } } },
  };
  globalThis.document = { querySelectorAll: () => [] };

  const pending = [];
  const api = {
    fetchApi: () => new Promise((resolve) => pending.push(resolve)),
  };
  const widget = { name: "model_name", value: "Model A", options: {} };
  let disconnected = 0;
  const node = {
    comfyClass: "pymss_mss_separate",
    widgets: [widget],
    outputs: [
      { name: "slot 1", links: [1] },
      { name: "slot 2", links: [2] },
      { name: "slot 3", links: [3] },
      { name: "slot 4", links: [4] },
    ],
    size: [420, 200],
    comfyMssOutputRefreshGeneration: 1,
    disconnectOutput() {
      disconnected += 1;
    },
    computeSize: () => [420, 200],
    setSize() {},
    setDirtyCanvas() {},
    arrange() {},
    graph: { setDirtyCanvas() {} },
  };

  const staleRefresh = refreshNodeOutputs(node, api, 1);
  widget.value = "Model B";
  node.comfyMssOutputRefreshGeneration = 2;
  const currentRefresh = refreshNodeOutputs(node, api, 2);

  const catalog = [
    { name: "Model A", display_name: "Model A", model_type: "mss", stems: ["vocals"] },
    { name: "Model B", display_name: "Model B", model_type: "mss", stems: ["vocals", "instrumental"] },
  ];
  pending[0]({ ok: true, json: async () => ({ models: catalog }) });
  await Promise.all([currentRefresh, staleRefresh]);

  assert.equal(disconnected, 0);
  assert.equal(node.outputs.length, 4);
  assert.equal(node.outputs[2].name, "instrumental (Audio)");
});


test("concurrent forced catalog refreshes share one in-flight request", async () => {
  globalThis.window = {
    app: { ui: { settings: { getSettingValue: () => "en" } } },
  };
  globalThis.document = { querySelectorAll: () => [] };
  const pending = [];
  const api = {
    fetchApi: () => new Promise((resolve) => pending.push(resolve)),
  };
  const node = { comfyClass: "pymss_custom_mss_separate" };

  const first = getCatalog(api, node, true);
  const second = getCatalog(api, node, true);
  const currentCatalog = [{ name: "New", display_name: "New", model_type: "bs_roformer", stems: ["vocals"] }];

  pending[0]({ ok: true, json: async () => ({ models: currentCatalog }) });
  assert.deepEqual(await first, currentCatalog);
  assert.deepEqual(await second, currentCatalog);
  assert.deepEqual(await getCatalog(api, node), currentCatalog);
  assert.equal(pending.length, 1);
});


test("model option refresh handles request failure and can recover", async () => {
  globalThis.window = {
    app: { ui: { settings: { getSettingValue: () => "en" } } },
  };
  globalThis.document = { querySelectorAll: () => [] };
  const widget = { name: "model_name", value: "", options: {} };
  const node = {
    comfyClass: "pymss_custom_mss_separate",
    widgets: [widget],
    setDirtyCanvas() {},
  };
  let requests = 0;
  const api = {
    fetchApi: async () => {
      requests += 1;
      if (requests === 1) {
        return { ok: false, status: 503, statusText: "Unavailable" };
      }
      return {
        ok: true,
        json: async () => ({
          models: [{ name: "Recovered", display_name: "Recovered", model_type: "bs_roformer", stems: ["vocals"] }],
        }),
      };
    },
  };
  const originalWarn = console.warn;
  console.warn = () => {};
  try {
    assert.equal(await tryRefreshModelWidgetOptions(node, api, true), false);
    assert.equal(await tryRefreshModelWidgetOptions(node, api, true), true);
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(requests, 2);
  assert.deepEqual(widget.options.values, ["Recovered"]);
  assert.equal(widget.value, "Recovered");
});
