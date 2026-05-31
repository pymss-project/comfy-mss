import { AUDIO_TOOL_MIN_NODE_WIDTH } from "./constants.js";

export function registerAudioToolNode(wrapOnNodeCreated) {
  wrapOnNodeCreated(function () {
    this.setSize(this.computeSize());
    this.size[0] = Math.max(this.size[0], AUDIO_TOOL_MIN_NODE_WIDTH);
    this.setDirtyCanvas(true, true);
  });
}
