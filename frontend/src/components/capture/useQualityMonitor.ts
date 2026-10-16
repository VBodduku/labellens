import { useMotionValue } from "motion/react";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { CAPTURED_STATE, INITIAL_CAPTURE_STATE, nextCaptureState, type QualityRequest, type QualityResponse } from "../../lib/quality";
import { FRAME_WIDTH, SAMPLE_FPS } from "../../lib/qualityThresholds";

/**
 * Samples the live video ~SAMPLE_FPS times a second at FRAME_WIDTH px, scores each frame in a Web Worker
 * and drives auto-capture: `onAutoCapture` fires once after GOOD_HOLD_MS of continuously good frames.
 * Frames are skipped while the worker is still busy, so slow phones never queue up work.
 */
export function useQualityMonitor(
  videoRef: RefObject<HTMLVideoElement>,
  active: boolean,
  autoCaptureEnabled: boolean,
  onAutoCapture: () => void,
) {
  const [latest, setLatest] = useState<QualityResponse | null>(null);
  const [fps, setFps] = useState(0);
  const [streakMs, setStreakMs] = useState(0);
  const progress = useMotionValue(0);
  const captureState = useRef(INITIAL_CAPTURE_STATE);
  const onAutoCaptureRef = useRef(onAutoCapture);
  const autoRef = useRef(autoCaptureEnabled);

  useEffect(() => {
    onAutoCaptureRef.current = onAutoCapture;
    autoRef.current = autoCaptureEnabled;
  }, [onAutoCapture, autoCaptureEnabled]);

  useEffect(() => {
    if (!active) return;
    const worker = new Worker(new URL("../../workers/quality.worker.ts", import.meta.url), { type: "module" });
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { willReadFrequently: true });
    let busy = false;
    let frames = 0;
    let windowStart = performance.now();

    worker.onmessage = (event: MessageEvent<QualityResponse>) => {
      busy = false;
      setLatest(event.data);
      const now = performance.now();
      frames += 1;
      if (now - windowStart >= 1000) {
        setFps(Math.round((frames * 1000) / (now - windowStart)));
        frames = 0;
        windowStart = now;
      }
      const issues = autoRef.current ? event.data.issues : ["blurry" as const];
      const step = nextCaptureState(captureState.current, issues, now);
      captureState.current = step.state;
      progress.set(step.progress);
      setStreakMs(step.state.goodSince === null ? 0 : now - step.state.goodSince);
      if (step.shouldCapture) onAutoCaptureRef.current();
    };

    const timer = window.setInterval(() => {
      const video = videoRef.current;
      if (busy || !context || !video || video.readyState < 2 || !video.videoWidth) return;
      const width = FRAME_WIDTH;
      const height = Math.round((FRAME_WIDTH * video.videoHeight) / video.videoWidth);
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      context.drawImage(video, 0, 0, width, height);
      const { data } = context.getImageData(0, 0, width, height);
      busy = true;
      const request: QualityRequest = { kind: "frame", buffer: data.buffer, width, height };
      worker.postMessage(request, [data.buffer]);
    }, 1000 / SAMPLE_FPS);

    return () => {
      window.clearInterval(timer);
      worker.terminate();
      captureState.current = INITIAL_CAPTURE_STATE;
      progress.set(0);
      setLatest(null);
    };
  }, [active, videoRef, progress]);

  /** After a manual capture: disarm until the camera moves, like an auto-capture. */
  const markCaptured = useCallback(() => {
    captureState.current = CAPTURED_STATE;
    progress.set(0);
  }, [progress]);

  return { latest, fps, streakMs, progress, markCaptured };
}
