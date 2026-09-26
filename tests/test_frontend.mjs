import assert from "node:assert/strict";
import test from "node:test";

import { localizedModelDisplayName } from "../web/comfy_mss/i18n.js";
import { matchesModelName, syncOutputs } from "../web/comfy_mss/separate.js";


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
