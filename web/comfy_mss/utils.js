export function getWidget(node, name) {
  return node.widgets?.find((widget) => widget.name === name);
}

export function disconnectOutput(node, index) {
  try {
    if (typeof node.disconnectOutput === "function") {
      node.disconnectOutput(index);
      return;
    }
    const output = node.outputs?.[index];
    for (const linkId of output?.links ?? []) {
      node.graph?.removeLink?.(linkId);
    }
  } catch (error) {
    console.warn("[comfy-mss] failed to disconnect output", error);
  }
}

export function disconnectInput(node, index) {
  try {
    if (typeof node.disconnectInput === "function") {
      node.disconnectInput(index);
      return;
    }
    const linkId = node.inputs?.[index]?.link;
    if (linkId != null) {
      node.graph?.removeLink?.(linkId);
    }
  } catch (error) {
    console.warn("[comfy-mss] failed to disconnect input", error);
  }
}
