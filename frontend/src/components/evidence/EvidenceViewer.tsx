import { ChevronDown, ChevronUp, Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { TransformComponent, TransformWrapper, type ReactZoomPanPinchRef } from "react-zoom-pan-pinch";
import { containSize, focusTransform, imageIndex, type Size } from "../../lib/boxMath";
import type { Box, ImageInfo, VerdictState } from "../../shared/contract";
import type { Panel } from "../../store/scan";
import { useUiStore, type FocusedEvidence } from "../../store/ui";
import { IconButton } from "../ui/IconButton";
import { EvidenceOverlay, type OverlayItem } from "./EvidenceOverlay";
import { PanelSwitcher } from "./PanelSwitcher";

const FOCUS_MS = 420;

interface EvidenceViewerProps {
  panels: Panel[];
  images: ImageInfo[];
  items: OverlayItem[];
  className?: string;
}

/**
 * The label photo with pinch/zoom/pan and the evidence overlay. Whenever any evidence chip in the app is
 * tapped (ui store `focusedEvidence`), it switches to that panel, animates the box to fill ~60 % of the
 * viewer, dims the rest and pulses the outline — and announces the words for screen readers.
 */
export function EvidenceViewer({ panels, images, items, className = "" }: EvidenceViewerProps) {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  const focused = useUiStore((store) => store.focusedEvidence);
  /** Focus requests left over from a previous visit must not replay when the viewer mounts. */
  const mountNonce = useRef(focused?.nonce ?? 0);
  const zoomRef = useRef<ReactZoomPanPinchRef>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<Size>({ width: 0, height: 0 });
  const [loaded, setLoaded] = useState<Record<number, Size>>({});
  const [active, setActive] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pending, setPending] = useState<FocusedEvidence | null>(null);
  const [focus, setFocus] = useState<{ box: Box; state: VerdictState | null; pulse: number } | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const panelIndex = Math.min(active, Math.max(panels.length - 1, 0));
  const panel = panels[panelIndex];
  const info = images[panelIndex];
  const natural = loaded[panelIndex] ?? (info ? { width: info.width, height: info.height } : { width: 0, height: 0 });
  const image = containSize(natural, viewport);

  useLayoutEffect(() => {
    const node = viewportRef.current;
    if (!node) return;
    const measure = () => setViewport({ width: node.clientWidth, height: node.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [collapsed]);

  // A chip somewhere asked for evidence: open the viewer on the right panel, then zoom once it is laid out.
  useEffect(() => {
    if (!focused || focused.nonce <= mountNonce.current) return;
    setCollapsed(false);
    setActive(imageIndex(focused.evidence.image_id));
    setPending(focused);
    setAnnouncement(t("result.viewer.showing", { text: focused.evidence.text }));
  }, [focused, t]);

  useEffect(() => {
    if (!pending) return;
    const { box, status } = pending.evidence;
    if (!box || status === "unverified") {
      setPending(null);
      return;
    }
    if (imageIndex(pending.evidence.image_id) !== panelIndex || image.width === 0) return;
    const transform = focusTransform(box, image, viewport);
    void zoomRef.current?.setTransform(transform.positionX, transform.positionY, transform.scale, reduce ? 0 : FOCUS_MS, "easeOut");
    setFocus({ box, state: pending.state, pulse: pending.nonce });
    setPending(null);
  }, [pending, panelIndex, image, viewport, reduce]);

  // A different family member was selected: drop the old highlight and show the whole photo again.
  useEffect(() => {
    setFocus(null);
    void zoomRef.current?.resetTransform(0);
  }, [items]);

  const panelItems = useMemo(
    () => items.filter((item) => imageIndex(item.evidence.image_id) === panelIndex),
    [items, panelIndex],
  );

  function switchPanel(index: number) {
    setActive(index);
    setFocus(null);
    void zoomRef.current?.resetTransform(0);
  }

  function resetView() {
    setFocus(null);
    void zoomRef.current?.resetTransform(reduce ? 0 : 260);
  }

  return (
    <section aria-label={t("result.viewer.label")} className={`card flex flex-col overflow-hidden ${className}`}>
      <div className="flex items-center gap-1 border-b border-line py-1 pl-4 pr-1">
        <h2 className="mr-auto text-sm font-semibold text-text-dim">{t("result.viewer.label")}</h2>
        {!collapsed && (
          <>
            <IconButton label={t("result.viewer.zoomOut")} onClick={() => void zoomRef.current?.zoomOut(0.6)}>
              <ZoomOut className="size-[1.1rem]" aria-hidden="true" />
            </IconButton>
            <IconButton label={t("result.viewer.zoomIn")} onClick={() => void zoomRef.current?.zoomIn(0.6)}>
              <ZoomIn className="size-[1.1rem]" aria-hidden="true" />
            </IconButton>
            <IconButton label={t("result.viewer.reset")} onClick={resetView}>
              <Maximize2 className="size-[1.05rem]" aria-hidden="true" />
            </IconButton>
          </>
        )}
        <IconButton
          label={collapsed ? t("result.viewer.expand") : t("result.viewer.collapse")}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed((value) => !value)}
          className="lg:hidden"
        >
          {collapsed ? <ChevronDown className="size-5" aria-hidden="true" /> : <ChevronUp className="size-5" aria-hidden="true" />}
        </IconButton>
      </div>

      {!collapsed && panel && (
        <div ref={viewportRef} className="relative h-[38svh] min-h-56 bg-[#0d1015] lg:h-auto lg:min-h-0 lg:flex-1">
          {viewport.width > 0 && (
            <TransformWrapper
              ref={zoomRef}
              minScale={1}
              maxScale={8}
              limitToBounds
              disablePadding
              doubleClick={{ mode: "toggle", step: 1.2 }}
              wheel={{ step: 0.12 }}
              panning={{ disabled: zoom <= 1.01, velocityDisabled: true }}
              onTransformed={(_ref, state) => setZoom(state.scale)}
            >
              <TransformComponent
                wrapperStyle={{ width: "100%", height: "100%" }}
                contentStyle={{ width: viewport.width, height: viewport.height }}
              >
                <div className="flex items-center justify-center" style={{ width: viewport.width, height: viewport.height }}>
                  <div className="relative" style={{ width: image.width, height: image.height }}>
                    <img
                      src={panel.url}
                      alt={t("result.photoAlt", { n: panelIndex + 1 })}
                      draggable={false}
                      className="size-full select-none"
                      onLoad={(event) => {
                        const { naturalWidth, naturalHeight } = event.currentTarget;
                        if (!info && naturalWidth > 0) setLoaded((sizes) => ({ ...sizes, [panelIndex]: { width: naturalWidth, height: naturalHeight } }));
                      }}
                    />
                    <EvidenceOverlay items={panelItems} focus={focus} zoom={zoom} />
                  </div>
                </div>
              </TransformComponent>
            </TransformWrapper>
          )}
        </div>
      )}

      {!collapsed && panels.length > 1 && (
        <div className="border-t border-line p-2">
          <PanelSwitcher panels={panels} active={panelIndex} onChange={switchPanel} />
        </div>
      )}
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </section>
  );
}
