import { useState } from "react";

/** Contradictions the user marked as checked on the pack, for one scan (a new scan starts unchecked). */
export function useCheckedContradictions(scanId: string) {
  const [checked, setChecked] = useState<{ scanId: string; ids: string[] }>({ scanId, ids: [] });
  const ids = checked.scanId === scanId ? checked.ids : [];
  return { checked: ids, check: (id: string) => setChecked({ scanId, ids: [...ids, id] }) };
}
