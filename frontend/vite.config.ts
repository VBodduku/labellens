/// <reference types="vitest/config" />
import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type PluginOption } from "vite";
import { VitePWA } from "vite-plugin-pwa";

const ENV_DIR = "..";

/** Vendor groups that must stay out of every chunk except the landing page (checked by scripts/check-chunks.mjs). */
function landingOnlyChunk(id: string): string | undefined {
  if (!id.includes("node_modules")) return undefined;
  if (/node_modules[\\/](three|three-stdlib|@react-three|three-mesh-bvh|troika-|camera-controls|maath)/.test(id)) {
    return "vendor-three";
  }
  if (/node_modules[\\/]lenis[\\/]/.test(id)) return "vendor-lenis";
  return undefined;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ENV_DIR, "VITE_");
  const plugins: PluginOption[] = [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["logo.svg", "apple-touch-icon-180x180.png"],
      manifest: {
        name: "LabelLens",
        short_name: "LabelLens",
        description: "Reads a food label and checks it for every family member, showing the exact words behind every flag.",
        theme_color: "#0B0D12",
        background_color: "#0B0D12",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "pwa-64x64.png", sizes: "64x64", type: "image/png" },
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
          { src: "maskable-icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api/],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ];
  if (env.VITE_HTTPS === "true") plugins.push(basicSsl());

  return {
    envDir: ENV_DIR,
    plugins,
    server: {
      host: true,
      allowedHosts: [".trycloudflare.com"],
      proxy: {
        "/api": { target: "http://localhost:8000", changeOrigin: true },
      },
    },
    build: {
      manifest: true,
      rollupOptions: {
        output: { manualChunks: landingOnlyChunk },
      },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
