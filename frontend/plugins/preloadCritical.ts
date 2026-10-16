import type { OutputAsset, OutputBundle, OutputChunk } from "rollup";
import type { Plugin } from "vite";

const FONT_FILES = [/manrope-latin-wght/, /bricolage-grotesque-latin-wght/];
const LANDING_ENTRY = /routes[\\/]Landing\.tsx$/;
/** Pre-rendered hero poster in public/ (see scripts/render-poster.mjs). */
const HERO_IMAGE = "/hero-poster.webp";

function isChunk(item: OutputChunk | OutputAsset): item is OutputChunk {
  return item.type === "chunk";
}

/** The landing chunk plus every chunk it imports statically (what the landing page needs to render). */
function landingFiles(bundle: OutputBundle): string[] {
  const chunks = Object.values(bundle).filter(isChunk);
  const landing = chunks.find(
    (chunk) =>
      (chunk.facadeModuleId !== null && LANDING_ENTRY.test(chunk.facadeModuleId)) ||
      Object.keys(chunk.modules).some((id) => LANDING_ENTRY.test(id)),
  );
  if (!landing) return [];
  const files = new Set<string>([landing.fileName]);
  const visit = (chunk: OutputChunk) => {
    for (const name of chunk.imports) {
      if (files.has(name)) continue;
      const next = chunks.find((candidate) => candidate.fileName === name);
      if (next && !next.isEntry) {
        files.add(name);
        visit(next);
      }
    }
  };
  visit(landing);
  return [...files];
}

/**
 * Cuts the landing page's loading waterfall (entry → lazy Landing chunk → poster image, fonts found only
 * after the CSS parses): preloads the two Latin UI fonts everywhere, and — only when the visitor is on "/" —
 * the Landing chunk with its imports and the poster image (the LCP element).
 */
export function preloadCritical(): Plugin {
  return {
    name: "labellens:preload-critical",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, context) {
        const bundle = context.bundle;
        if (!bundle) return [];
        const assets = Object.values(bundle).filter((item): item is OutputAsset => item.type === "asset");
        const fonts = assets.filter((asset) => FONT_FILES.some((pattern) => pattern.test(asset.fileName)));
        const modules = landingFiles(bundle);
        const landingLinks = [
          ...modules.map((file) => ({ rel: "modulepreload", href: `/${file}` })),
          {
            rel: "preload",
            href: HERO_IMAGE,
            as: "image",
            imageSrcset: "/hero-poster-500.webp 500w, /hero-poster.webp 1000w",
            imageSizes: "(min-width: 1024px) 34vw, 62vw",
            fetchpriority: "high",
          },
        ];
        const script = `if(location.pathname==="/"){for(const a of ${JSON.stringify(landingLinks)}){const l=document.createElement("link");Object.assign(l,a);if(a.fetchpriority)l.setAttribute("fetchpriority",a.fetchpriority);document.head.appendChild(l)}}`;
        return [
          ...fonts.map((font) => ({
            tag: "link",
            attrs: { rel: "preload", href: `/${font.fileName}`, as: "font", type: "font/woff2", crossorigin: "" },
            injectTo: "head-prepend" as const,
          })),
          { tag: "script", children: script, injectTo: "head" as const },
        ];
      },
    },
  };
}
