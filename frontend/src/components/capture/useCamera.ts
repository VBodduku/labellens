import { useCallback, useEffect, useState, type RefObject } from "react";

export type CameraStatus = "requesting" | "live" | "denied" | "unavailable" | "insecure" | "error";

const CONSTRAINTS: MediaStreamConstraints = {
  audio: false,
  video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
};

type TorchCapabilities = MediaTrackCapabilities & { torch?: boolean };
type TorchConstraint = MediaTrackConstraintSet & { torch?: boolean };

function statusFromError(error: unknown): CameraStatus {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError" || name === "NotReadableError") return "unavailable";
  return "error";
}

/**
 * Rear camera stream into `videoRef`, with torch control when the device supports it. The stream stops
 * while the page is hidden or the hook is disabled, and restarts when it becomes visible again.
 */
export function useCamera(videoRef: RefObject<HTMLVideoElement>, enabled: boolean) {
  const [status, setStatus] = useState<CameraStatus>("requesting");
  const [track, setTrack] = useState<MediaStreamTrack | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [visible, setVisible] = useState(() => document.visibilityState === "visible");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const onVisibility = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (!enabled || !visible) return;
    if (!window.isSecureContext) {
      setStatus("insecure");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("unavailable");
      return;
    }
    let cancelled = false;
    let stream: MediaStream | null = null;
    const video = videoRef.current;
    setStatus("requesting");
    navigator.mediaDevices
      .getUserMedia(CONSTRAINTS)
      .then(async (granted) => {
        if (cancelled) {
          granted.getTracks().forEach((item) => item.stop());
          return;
        }
        stream = granted;
        if (video) {
          video.srcObject = granted;
          await video.play().catch(() => undefined);
        }
        setTrack(granted.getVideoTracks()[0] ?? null);
        setTorchOn(false);
        setStatus("live");
      })
      .catch((error: unknown) => {
        if (!cancelled) setStatus(statusFromError(error));
      });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((item) => item.stop());
      if (video) video.srcObject = null;
      setTrack(null);
    };
  }, [enabled, visible, attempt, videoRef]);

  const capabilities = track?.getCapabilities?.() as TorchCapabilities | undefined;
  const torchSupported = Boolean(capabilities?.torch);

  const toggleTorch = useCallback(async () => {
    if (!track) return;
    const next = !torchOn;
    try {
      await track.applyConstraints({ advanced: [{ torch: next } as TorchConstraint] });
      setTorchOn(next);
    } catch {
      setTorchOn(false);
    }
  }, [track, torchOn]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  return { status, torchSupported, torchOn, toggleTorch, retry };
}
