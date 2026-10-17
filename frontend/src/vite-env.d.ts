/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCKS?: string;
  readonly VITE_HTTPS?: string;
  readonly VITE_SCAN_TIMEOUT_S?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
