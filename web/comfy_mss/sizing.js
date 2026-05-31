import { STANDARD_NODE_WIDTH } from "./constants.js";

export function setNodeWidth(node, width = STANDARD_NODE_WIDTH) {
  node.setSize(node.computeSize());
  node.size[0] = width;
  node.setDirtyCanvas(true, true);
}

export function registerFixedWidthNode(wrapOnNodeCreated, width = STANDARD_NODE_WIDTH) {
  wrapOnNodeCreated(function () {
    setNodeWidth(this, width);
  });
}
