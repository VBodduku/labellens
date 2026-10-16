import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useScanStore } from "../../store/scan";

export type DemoState = "idle" | "loading" | "error";

/** Loads the fixture scan (no camera, no backend) and opens the result screen. */
export function useDemoLauncher() {
  const loadDemo = useScanStore((state) => state.loadDemo);
  const navigate = useNavigate();
  const [state, setState] = useState<DemoState>("idle");

  async function launch() {
    setState("loading");
    try {
      await loadDemo();
      navigate("/result");
    } catch {
      setState("error");
    }
  }

  return { launch, state };
}
