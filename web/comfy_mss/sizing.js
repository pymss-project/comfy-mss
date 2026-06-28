const STANDARD_NODE_WIDTH = 260;

export function setNodeWidth(node, width = STANDARD_NODE_WIDTH) {
  node.setSize(node.computeSize());
  node.size[0] = width;
  node.setDirtyCanvas(true, true);
}

export function setNodeWidthOnly(node, width = STANDARD_NODE_WIDTH) {
  node.size ||= node.computeSize();
  node.size[0] = width;
  node.setDirtyCanvas(true, true);
}

export function resizeNodeKeepingWidth(node, width = STANDARD_NODE_WIDTH) {
  node.setSize(node.computeSize());
  node.size[0] = width;
  node.setDirtyCanvas(true, true);
}

export function registerFixedWidthNode(wrapOnNodeCreated, width = STANDARD_NODE_WIDTH) {
  wrapOnNodeCreated(function () {
    setNodeWidth(this, width);
  });
}

export function registerFixedWidthOnlyNode(wrapOnNodeCreated, width = STANDARD_NODE_WIDTH) {
  wrapOnNodeCreated(function () {
    setNodeWidthOnly(this, width);
  });
}
