import type { QualityResponse } from "../../lib/quality";
import { GOOD_HOLD_MS, QUALITY_THRESHOLDS } from "../../lib/qualityThresholds";

interface DebugOverlayProps {
  latest: QualityResponse | null;
  fps: number;
  streakMs: number;
}

function Row({ name, value, limit, pass }: { name: string; value: string; limit: string; pass: boolean }) {
  return (
    <tr>
      <td className="pr-2 text-white/60">{name}</td>
      <td className={`pr-2 text-right ${pass ? "text-[#3ddc97]" : "text-[#ff5a4e]"}`}>{value}</td>
      <td className="text-white/50">{limit}</td>
    </tr>
  );
}

/**
 * `?debug=1` calibration aid: live metric values next to the thresholds in lib/qualityThresholds.ts.
 * Developer-only, so its labels are intentionally not translated.
 */
export function DebugOverlay({ latest, fps, streakMs }: DebugOverlayProps) {
  const metrics = latest?.metrics;
  return (
    <div className="pointer-events-none absolute left-3 top-16 z-20 rounded-lg bg-black/75 p-2.5 font-mono text-[11px] leading-5 text-white">
      {metrics ? (
        <table>
          <tbody>
            <Row name="blur" value={metrics.blur.toFixed(0)} limit={`≥ ${QUALITY_THRESHOLDS.blurMin}`} pass={metrics.blur >= QUALITY_THRESHOLDS.blurMin} />
            <Row name="glare" value={metrics.glare.toFixed(3)} limit={`≤ ${QUALITY_THRESHOLDS.glareMax}`} pass={metrics.glare <= QUALITY_THRESHOLDS.glareMax} />
            <Row
              name="light"
              value={metrics.brightness.toFixed(0)}
              limit={`≥ ${QUALITY_THRESHOLDS.darkMin}`}
              pass={metrics.brightness >= QUALITY_THRESHOLDS.darkMin}
            />
            <Row
              name="motion"
              value={metrics.motion === null ? "–" : metrics.motion.toFixed(1)}
              limit={`≤ ${QUALITY_THRESHOLDS.motionMax}`}
              pass={metrics.motion === null || metrics.motion <= QUALITY_THRESHOLDS.motionMax}
            />
            <Row name="hold" value={`${Math.round(streakMs)}ms`} limit={`/ ${GOOD_HOLD_MS}`} pass={streakMs > 0} />
            <tr>
              <td className="pr-2 text-white/60">fps</td>
              <td className="pr-2 text-right">{fps}</td>
              <td className="text-white/50">{latest.issues.join(",") || "ok"}</td>
            </tr>
          </tbody>
        </table>
      ) : (
        <span>waiting for frames…</span>
      )}
    </div>
  );
}
