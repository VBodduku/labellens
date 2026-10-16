import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { initI18n } from "./i18n";
import { applyTheme, useUiStore } from "./store/ui";
import "./styles/globals.css";

const { lang, theme } = useUiStore.getState();
initI18n(lang);
applyTheme(theme);

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
