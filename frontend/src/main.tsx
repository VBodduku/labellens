import { startTransition, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { initI18n, loadLanguage } from "./i18n";
import { applyTheme, useUiStore } from "./store/ui";
import "./styles/globals.css";

const { lang, theme } = useUiStore.getState();
initI18n(lang);
applyTheme(theme);

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");
const container = root;

/** A transition render lets React yield to the browser while the first screen builds (no long task). */
function render() {
  const root = createRoot(container);
  startTransition(() => {
    root.render(
      <StrictMode>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </StrictMode>,
    );
  });
}

// Hindi/Telugu strings are a separate chunk: load the saved language before the first render.
if (lang === "en") render();
else void loadLanguage(lang).finally(render);
