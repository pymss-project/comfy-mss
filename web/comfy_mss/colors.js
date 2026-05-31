import { TYPE_ALIASES, TYPE_COLORS } from "./constants.js";

const ALIAS_COLORS = Object.fromEntries(
  Object.entries(TYPE_ALIASES).flatMap(([type, aliases]) => aliases.map((alias) => [alias.toLowerCase(), TYPE_COLORS[type]]))
);

let linkColorPatchApplied = false;

export function typeColor(type) {
  return String(type ?? "")
    .split(",")
    .map((item) => ALIAS_COLORS[item.trim().toLowerCase()])
    .find(Boolean);
}

export function applyTypeColors(app) {
  const canvas = app.canvas;
  const LiteGraph = globalThis.LiteGraph;
  const canvasTypes = [globalThis.LGraphCanvas, LiteGraph?.LGraphCanvas, canvas?.constructor].filter(Boolean);

  for (const [type, color] of Object.entries(TYPE_COLORS)) {
    for (const alias of TYPE_ALIASES[type] ?? [type]) {
      for (const CanvasType of canvasTypes) {
        if (CanvasType?.link_type_colors) {
          CanvasType.link_type_colors[alias] = color;
        }
      }
      if (canvas?.default_connection_color_byType) {
        canvas.default_connection_color_byType[alias] = color;
      }
      if (canvas?.default_connection_color_byTypeOff) {
        canvas.default_connection_color_byTypeOff[alias] = color;
      }
      if (LiteGraph?.slot_types_in && !LiteGraph.slot_types_in.includes(alias.toLowerCase())) {
        LiteGraph.slot_types_in.push(alias.toLowerCase());
      }
      if (LiteGraph?.slot_types_out && !LiteGraph.slot_types_out.includes(alias.toLowerCase())) {
        LiteGraph.slot_types_out.push(alias.toLowerCase());
      }
    }
  }
}

function linkEndpoints(graph, link) {
  const originNode = graph?.getNodeById?.(link?.origin_id);
  const targetNode = graph?.getNodeById?.(link?.target_id);
  return {
    originSlot: originNode?.outputs?.[link?.origin_slot],
    targetSlot: targetNode?.inputs?.[link?.target_slot],
  };
}

export function colorLink(graph, link) {
  if (!link) {
    return;
  }
  const { originSlot, targetSlot } = linkEndpoints(graph, link);
  const color = typeColor(link.type) || typeColor(originSlot?.type) || typeColor(targetSlot?.type);
  if (color) {
    link.color = color;
  }
}

export function colorGraphLinks(graph) {
  if (!graph) {
    return;
  }
  const links = graph._links instanceof Map ? graph._links.values() : Object.values(graph.links ?? {});
  for (const link of links) {
    colorLink(graph, link);
  }
}

export function colorSlot(slot) {
  const color = typeColor(slot?.type);
  if (!slot || !color) {
    return;
  }
  slot.color_on = color;
  slot.color_off = color;
  slot.color = color;
}

export function colorNodeSlots(node) {
  for (const input of node.inputs ?? []) {
    colorSlot(input);
  }
  for (const output of node.outputs ?? []) {
    colorSlot(output);
  }
  colorGraphLinks(node.graph);
}

export function applyLinkColorPatch(app) {
  if (linkColorPatchApplied) {
    return;
  }
  const canvas = app.canvas;
  const CanvasType = canvas?.constructor;
  const prototype = CanvasType?.prototype;
  if (!prototype?.renderLink) {
    return;
  }

  linkColorPatchApplied = true;
  const originalRenderLink = prototype.renderLink;
  prototype.renderLink = function (ctx, a, b, link, skipBorder, flow, color, startDir, endDir, extras) {
    const effectiveColor = color ?? typeColor(link?.type) ?? (() => {
      const { originSlot, targetSlot } = linkEndpoints(this.graph, link);
      return typeColor(originSlot?.type) ?? typeColor(targetSlot?.type);
    })();
    return originalRenderLink.call(this, ctx, a, b, link, skipBorder, flow, effectiveColor ?? color, startDir, endDir, extras);
  };
}
