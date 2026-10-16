import { assessFrame, measureFrame, toGray, type QualityRequest, type QualityResponse } from "../lib/quality";
import { QUALITY_THRESHOLDS } from "../lib/qualityThresholds";

/** Computes blur / glare / brightness / motion off the main thread for each sampled camera frame. */
const scope = self as unknown as {
  onmessage: ((event: MessageEvent<QualityRequest>) => void) | null;
  postMessage: (message: QualityResponse) => void;
};

let previous: Uint8Array | null = null;

scope.onmessage = (event) => {
  const request = event.data;
  if (request.kind === "reset") {
    previous = null;
    return;
  }
  const gray = toGray(new Uint8ClampedArray(request.buffer), request.width, request.height);
  const metrics = measureFrame(gray, request.width, request.height, previous);
  previous = gray;
  scope.postMessage({ metrics, issues: assessFrame(metrics, QUALITY_THRESHOLDS) });
};
