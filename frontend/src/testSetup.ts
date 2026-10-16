/**
 * Node 25+ defines its own global `localStorage`, which is unusable without `--localstorage-file` and hides
 * jsdom's. Put jsdom's Storage back so persisted stores behave like they do in the browser, on every Node version.
 */
const dom = (globalThis as { jsdom?: { window: Pick<Window, "localStorage" | "sessionStorage"> } }).jsdom;

if (dom && typeof globalThis.localStorage?.setItem !== "function") {
  for (const name of ["localStorage", "sessionStorage"] as const) {
    Object.defineProperty(globalThis, name, { value: dom.window[name], configurable: true, writable: true });
  }
}
