import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AdditiveBlending,
  CanvasTexture,
  Color,
  SRGBColorSpace,
  type Group,
  type Mesh,
  type PerspectiveCamera,
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { sampleLabelUrl } from "../../api/fixtures";
import { isMobile } from "../../lib/featureDetect";
import { LABEL_ASPECT } from "./heroChipData";

const FOV = 30;
const LABEL_HEIGHT = 1.4;
const LABEL_WIDTH = LABEL_HEIGHT * LABEL_ASPECT;
const DEPTH = 0.18;
const RIM = 0.03;
const FACE_Z = DEPTH / 2 + 0.002;
const BEAM_PERIOD_S = 3.4;
const MAX_TILT = { x: 0.07, y: 0.11 };

interface Hero3DProps {
  /** Fraction of the canvas height the label face must occupy (matches the DOM overlay). */
  heightRatio: number;
  active: boolean;
  onReady: () => void;
}

/** Rasterises the fixture SVG label once into a crisp texture. */
function useLabelTexture(onLoaded: () => void): CanvasTexture | null {
  const [texture, setTexture] = useState<CanvasTexture | null>(null);
  const onLoadedRef = useRef(onLoaded);
  onLoadedRef.current = onLoaded;

  useEffect(() => {
    let disposed = false;
    let created: CanvasTexture | null = null;
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
      if (disposed) return;
      const scale = isMobile() ? 1.25 : 1.6;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(1000 * scale);
      canvas.height = Math.round(canvas.width / LABEL_ASPECT);
      canvas.getContext("2d")?.drawImage(image, 0, 0, canvas.width, canvas.height);
      created = new CanvasTexture(canvas);
      created.colorSpace = SRGBColorSpace;
      created.anisotropy = 8;
      setTexture(created);
      onLoadedRef.current();
    };
    image.src = sampleLabelUrl;
    return () => {
      disposed = true;
      created?.dispose();
    };
  }, []);

  return texture;
}

/** Soft vertical falloff for the beam's glow band. */
function useGlowTexture(): CanvasTexture {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 4;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    if (context) {
      const gradient = context.createLinearGradient(0, 0, 0, 128);
      gradient.addColorStop(0, "rgba(255,255,255,0)");
      gradient.addColorStop(0.5, "rgba(255,255,255,1)");
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      context.fillStyle = gradient;
      context.fillRect(0, 0, 4, 128);
    }
    return new CanvasTexture(canvas);
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

/** Places the camera so the label face fills exactly `heightRatio` of the viewport height. */
function CameraRig({ heightRatio }: { heightRatio: number }) {
  const camera = useThree((state) => state.camera) as PerspectiveCamera;
  useEffect(() => {
    const visibleHeight = LABEL_HEIGHT / Math.max(heightRatio, 0.1);
    const distance = visibleHeight / (2 * Math.tan((FOV * Math.PI) / 360));
    camera.position.set(0, 0, FACE_Z + distance);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }, [camera, heightRatio]);
  return null;
}

function Packet({ texture, children }: { texture: CanvasTexture; children?: ReactNode }) {
  const group = useRef<Group>(null);
  const pointer = useRef({ x: 0, y: 0 });
  const bodyGeometry = useMemo(() => new RoundedBoxGeometry(LABEL_WIDTH + RIM * 2, LABEL_HEIGHT + RIM * 2, DEPTH, 4, 0.05), []);
  useEffect(() => () => bodyGeometry.dispose(), [bodyGeometry]);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      pointer.current.x = (event.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = (event.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  useFrame((state, delta) => {
    const node = group.current;
    if (!node) return;
    const t = state.clock.elapsedTime;
    const targetY = pointer.current.x * MAX_TILT.y + Math.sin(t * 0.6) * 0.025;
    const targetX = pointer.current.y * MAX_TILT.x + Math.cos(t * 0.5) * 0.015;
    const ease = 1 - Math.exp(-delta * 4);
    node.rotation.y += (targetY - node.rotation.y) * ease;
    node.rotation.x += (targetX - node.rotation.x) * ease;
  });

  return (
    <group ref={group}>
      <mesh geometry={bodyGeometry}>
        <meshStandardMaterial color="#3d1d15" roughness={0.32} metalness={0.55} />
      </mesh>
      <mesh position={[0, 0, FACE_Z]}>
        <planeGeometry args={[LABEL_WIDTH, LABEL_HEIGHT]} />
        <meshStandardMaterial map={texture} roughness={0.55} metalness={0} />
      </mesh>
      {children}
    </group>
  );
}

/** The signature beam: a hairline of light wider than the packet with a soft glow band, sweeping down. */
function Beam() {
  const group = useRef<Group>(null);
  const glow = useRef<Mesh>(null);
  const glowTexture = useGlowTexture();
  const beamColor = useMemo(() => new Color("#7cf5ff"), []);
  const beamColor2 = useMemo(() => new Color("#a98bff"), []);

  useFrame((state) => {
    const node = group.current;
    if (!node) return;
    const phase = (state.clock.elapsedTime % (BEAM_PERIOD_S * 2)) / BEAM_PERIOD_S;
    const linear = phase <= 1 ? phase : 2 - phase;
    const eased = linear * linear * (3 - 2 * linear);
    node.position.y = (LABEL_HEIGHT / 2 + 0.02) - eased * (LABEL_HEIGHT + 0.04);
    if (glow.current) glow.current.scale.y = 0.8 + Math.sin(state.clock.elapsedTime * 3) * 0.08;
  });

  return (
    <group ref={group} position={[0, 0, FACE_Z + 0.004]}>
      <mesh ref={glow}>
        <planeGeometry args={[LABEL_WIDTH * 1.08, 0.2]} />
        <meshBasicMaterial
          color={beamColor}
          alphaMap={glowTexture}
          transparent
          opacity={0.32}
          blending={AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh>
        <planeGeometry args={[LABEL_WIDTH * 1.5, 0.007]} />
        <meshBasicMaterial color={beamColor} transparent opacity={0.95} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, 0.001]}>
        <planeGeometry args={[LABEL_WIDTH * 0.9, 0.003]} />
        <meshBasicMaterial color={beamColor2} transparent opacity={0.9} blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  );
}

/** Lazy-loaded landing hero: the floating packet with the fixture label and the sweeping scan beam. */
export default function Hero3D({ heightRatio, active, onReady }: Hero3DProps) {
  const [textureReady, setTextureReady] = useState(false);
  const texture = useLabelTexture(() => setTextureReady(true));

  useEffect(() => {
    if (!textureReady) return;
    const frame = requestAnimationFrame(() => requestAnimationFrame(onReady));
    return () => cancelAnimationFrame(frame);
  }, [textureReady, onReady]);

  return (
    <Canvas
      dpr={[1, isMobile() ? 1.5 : 2]}
      frameloop={active ? "always" : "never"}
      camera={{ fov: FOV, near: 0.1, far: 50, position: [0, 0, 4] }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ position: "absolute", inset: 0 }}
      aria-hidden="true"
    >
      <CameraRig heightRatio={heightRatio} />
      <ambientLight intensity={0.85} />
      <directionalLight position={[2.5, 3, 5]} intensity={1.5} />
      <directionalLight position={[-3, -1.5, 2]} intensity={0.6} color="#a98bff" />
      <pointLight position={[0, 0, 2]} intensity={0.4} color="#7cf5ff" />
      {texture && (
        <Packet texture={texture}>
          <Beam />
        </Packet>
      )}
    </Canvas>
  );
}
