import { useState } from "react";

/** True from the first time `value` is true onwards (mount lazy UI once, keep it for exit animations). */
export function useLatch(value: boolean): boolean {
  const [latched, setLatched] = useState(value);
  if (value && !latched) setLatched(true);
  return latched || value;
}
