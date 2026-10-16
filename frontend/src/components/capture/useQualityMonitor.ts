import { useMotionValue } from "motion/react";
import { useEffect, useRef, useState, type RefObject } from "react";
import { nextReadyStep, type QualityRequest, type QualityResponse } from "../../lib/quality";
import { FRAME_WIDTH, SAMPLE_FPS } from "../../lib/qualityThresholds";

/**
 * Samples the live video ~SAMPLE_FPS times a second at FRAME_WIDTH px and scores each frame in a Web Worker
 * for the live hints and the shutter ring. It never takes a photo: only the shutter does.
 * Frames are skipped while the worker is still busy, so slow phones never queue up work.
 */
export function useQualityMonitor(videoRef: RefObject<HTMLVideoElement>, active: boolean) {
  const [latest, setLatest] = useState<QualityResponse | null>(null);
  const [fps, setFps] = useState(0);
  const [streakMs, setStreakMs] = useState(0);
  const progress = useMotionValue(0);
  const goodSince = useRef<number | null>(null);

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
      const step = nextReadyStep(goodSince.current, event.data.issues, now);
      goodSince.current = step.goodSince;
      progress.set(step.progress);
      setStreakMs(step.goodSince === null ? 0 : now - step.goodSince);
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
      goodSince.current = null;
      progress.set(0);
      setLatest(null);
    };
  }, [active, videoRef, progress]);

  return { latest, fps, streakMs, progress };
}
