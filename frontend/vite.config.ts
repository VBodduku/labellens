/// <reference types="vitest/config" />
import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type PluginOption } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { preloadCritical } from "./plugins/preloadCritical";

const ENV_DIR = "..";

/**
 * Dev and preview servers: reachable on the LAN and through a cloudflared tunnel, with /api proxied to the
 * backend (API_PROXY_TARGET in ../.env, e.g. the integration Mac). The browser only ever calls same-origin
 * /api, so the backend needs no CORS entry for phones or tunnels.
 */
function networkOptions(proxyTarget: string) {
  return {
    host: true,
    allowedHosts: [".trycloudflare.com"],
    proxy: {
      "/api": { target: proxyTarget, changeOrigin: true },
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ENV_DIR, "");
  const network = networkOptions(env.API_PROXY_TARGET || "http://localhost:8000");
  const plugins: PluginOption[] = [
    react(),
    preloadCritical(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "script-defer",
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
        globPatterns: ["**/*.{js,css,html,svg,png,webp,woff2}"],
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
    server: { ...network },
    preview: { ...network },
    build: {
      manifest: true,
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
