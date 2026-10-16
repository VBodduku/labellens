import { ArrowRight, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { CameraStateCard } from "../components/capture/CameraStateCard";
import { CameraView } from "../components/capture/CameraView";
import { CaptureButton } from "../components/capture/CaptureButton";
import { DebugOverlay } from "../components/capture/DebugOverlay";
import { PanelTray } from "../components/capture/PanelTray";
import { QualityHints } from "../components/capture/QualityHints";
import { TorchToggle } from "../components/capture/TorchToggle";
import { UploadFallback } from "../components/capture/UploadFallback";
import { useCamera } from "../components/capture/useCamera";
import { useQualityMonitor } from "../components/capture/useQualityMonitor";
import { captureVideoFrame, prepareImage } from "../lib/imageProcessing";
import { useProfilesStore } from "../store/profiles";
import { MAX_PANELS, useScanStore } from "../store/scan";
import { useUiStore } from "../store/ui";

/** Query string for /result without the scan-only `retake` parameter (dev switches like ?mockError survive). */
function resultSearch(search: string): string {
  const params = new URLSearchParams(search);
  params.delete("retake");
  const query = params.toString();
  return query ? `?${query}` : "";
}

/**
 * Camera-first capture (§5.2): live quality coaching, auto-capture when sharp and steady, up to three
 * panels, upload fallback. `?retake=<i>` replaces panel i from the result screen and reruns the scan.
 */
export default function Scan() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const debug = params.get("debug") === "1";

  const { panels: storedPanels, isDemo, scanProfiles, addPanel, retakePanel, removePanel, setPanelHint, analyse } = useScanStore();
  const userProfiles = useProfilesStore((state) => state.profiles);
  const lang = useUiStore((state) => state.lang);

  const retakeParam = params.get("retake");
  const resultRetake =
    retakeParam !== null && Number.isInteger(Number(retakeParam)) && Number(retakeParam) < storedPanels.length
      ? Number(retakeParam)
      : null;
  const panels = isDemo && resultRetake === null ? [] : storedPanels;

  const videoRef = useRef<HTMLVideoElement>(null);
  const captureRef = useRef<() => void>(() => undefined);
  const [trayRetake, setTrayRetake] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState(0);
  const [announcement, setAnnouncement] = useState("");

  const camera = useCamera(videoRef, true);
  const live = camera.status === "live";
  const replacing = resultRetake !== null || trayRetake !== null;
  const full = panels.length >= MAX_PANELS && !replacing;
  const monitor = useQualityMonitor(videoRef, live, !full && !busy, () => captureRef.current());

  const storePhoto = useCallback(
    (photo: Blob) => {
      if (resultRetake !== null) {
        retakePanel(resultRetake, photo);
        void analyse({ profiles: scanProfiles.length > 0 ? scanProfiles : userProfiles, lang });
        navigate({ pathname: "/result", search: resultSearch(search) });
        return;
      }
      if (trayRetake !== null) {
        retakePanel(trayRetake, photo);
        setTrayRetake(null);
        setAnnouncement(t("scan.captured", { n: trayRetake + 1 }));
        return;
      }
      const state = useScanStore.getState();
      const count = state.isDemo ? 0 : state.panels.length;
      if (count >= MAX_PANELS) return;
      addPanel(photo, count === 0 ? "back" : "side");
      setAnnouncement(t("scan.captured", { n: count + 1 }));
    },
    [resultRetake, trayRetake, retakePanel, analyse, scanProfiles, userProfiles, lang, navigate, search, addPanel, t],
  );

  const capture = useCallback(async () => {
    const video = videoRef.current;
    if (!video || busy || full) return;
    setBusy(true);
    try {
      const photo = await captureVideoFrame(video);
      monitor.markCaptured();
      setFlash((value) => value + 1);
      navigator.vibrate?.(30);
      storePhoto(photo);
    } finally {
      setBusy(false);
    }
  }, [busy, full, monitor, storePhoto]);

  useEffect(() => {
    captureRef.current = () => void capture();
  }, [capture]);

  async function onFiles(files: File[]) {
    setBusy(true);
    try {
      const room = replacing ? 1 : MAX_PANELS - panels.length;
      for (const file of files.slice(0, room)) storePhoto(await prepareImage(file));
    } finally {
      setBusy(false);
    }
  }

  function onAnalyse() {
    void analyse({ profiles: userProfiles, lang });
    navigate({ pathname: "/result", search: resultSearch(search) });
  }

  const issues = monitor.latest?.issues ?? null;
  const topMessage = resultRetake !== null ? t("scan.retakeMode", { n: resultRetake + 1 }) : t("scan.title");

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      <CameraView videoRef={videoRef} live={live} ready={issues !== null && issues.length === 0} />
      {debug && live && <DebugOverlay latest={monitor.latest} fps={monitor.fps} streakMs={monitor.streakMs} />}
      <AnimatePresence>
        {flash > 0 && (
          <motion.div
            key={flash}
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-30 bg-white"
            initial={{ opacity: 0.85 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
          />
        )}
      </AnimatePresence>

      <header className="relative z-10 flex items-center gap-3 px-3 pb-2 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <button
          type="button"
          onClick={() => navigate(resultRetake !== null ? { pathname: "/result", search: resultSearch(search) } : "/")}
          aria-label={t("scan.close")}
          className="flex size-11 items-center justify-center rounded-full bg-black/50 backdrop-blur-md"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
        <h1 className="min-w-0 flex-1 truncate text-sm font-semibold text-white/90">{topMessage}</h1>
        {live && camera.torchSupported && <TorchToggle on={camera.torchOn} onToggle={() => void camera.toggleTorch()} />}
      </header>

      <div className="relative z-10 flex flex-1 items-center justify-center">
        {!live && (
          <CameraStateCard
            status={camera.status === "live" ? "requesting" : camera.status}
            actions={
              <>
                <UploadFallback variant="button" onFiles={(files) => void onFiles(files)} disabled={full} multiple={!replacing} />
                {(camera.status === "denied" || camera.status === "error" || camera.status === "unavailable") && (
                  <button
                    type="button"
                    onClick={camera.retry}
                    className="inline-flex min-h-11 items-center rounded-chip px-4 text-sm font-semibold text-white ring-1 ring-white/30"
                  >
                    {t("scan.camera.retry")}
                  </button>
                )}
              </>
            }
          />
        )}
      </div>

      <div className="relative z-10 space-y-3 bg-gradient-to-t from-black/85 via-black/50 to-transparent px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-8">
        {live && <QualityHints issues={issues} ready={monitor.latest !== null} />}
        {panels.length > 0 && resultRetake === null && (
          <PanelTray
            panels={panels}
            retakeIndex={trayRetake}
            onRetake={setTrayRetake}
            onRemove={(index) => {
              if (trayRetake === index) setTrayRetake(null);
              removePanel(index);
            }}
            onHint={setPanelHint}
          />
        )}
        {resultRetake === null && panels.length === 1 && <p className="text-center text-xs text-white/75">{t("scan.wrapHint")}</p>}
        {full && <p className="text-center text-xs text-white/75">{t("scan.limit")}</p>}
        <div className="mx-auto grid max-w-md grid-cols-[1fr_auto_1fr] items-center gap-3">
          <div className="justify-self-start">
            <UploadFallback onFiles={(files) => void onFiles(files)} disabled={full || busy} multiple={!replacing} />
          </div>
          <CaptureButton progress={monitor.progress} disabled={!live || full || busy} onCapture={() => void capture()} />
          <div className="justify-self-end">
            {resultRetake === null && (
              <button
                type="button"
                onClick={onAnalyse}
                disabled={panels.length === 0 || busy}
                className="inline-flex min-h-12 items-center gap-1.5 rounded-chip bg-[image:var(--beam-gradient)] px-4 text-sm font-bold text-[#06121a] disabled:opacity-35"
              >
                {t("scan.analyse")}
                <ArrowRight className="size-4" aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}
