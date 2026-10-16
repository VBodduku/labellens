import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../ui/Button";
import { Sheet } from "../ui/Sheet";

export type EditTarget =
  | { kind: "ingredient"; fieldPath: string; current: string; rawText: string }
  | { kind: "nutrient"; fieldPath: string; label: string; current: number | null; unit: string; rawText: string };

interface CorrectionEditorProps {
  target: EditTarget | null;
  onClose: () => void;
  onSave: (fieldPath: string, value: string | number) => void;
}

/** Lets the user fix a misread ingredient name or nutrient value; saving rechecks every verdict. */
export function CorrectionEditor({ target, onClose, onSave }: CorrectionEditorProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const errorId = useId();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    setValue(target.kind === "ingredient" ? target.current : target.current === null ? "" : String(target.current));
    setError(null);
  }, [target]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!target) return;
    if (target.kind === "ingredient") {
      const name = value.trim();
      if (!name) {
        setError(t("editor.empty"));
        return;
      }
      onSave(target.fieldPath, name);
      return;
    }
    const amount = Number(value.replace(",", "."));
    if (value.trim() === "" || !Number.isFinite(amount) || amount < 0) {
      setError(t("editor.invalid"));
      return;
    }
    onSave(target.fieldPath, amount);
  }

  const title = target?.kind === "nutrient" ? t("editor.title.nutrient") : t("editor.title.ingredient");
  return (
    <Sheet open={target !== null} title={title} onClose={onClose}>
      {target && (
        <form onSubmit={submit} noValidate>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-dim">{t("editor.original")}</p>
          <p lang="" className="evidence-text mt-1 rounded-lg bg-surface-2 px-3 py-2 text-sm">
            {target.kind === "nutrient" && <span className="font-body text-text-dim">{target.label}: </span>}
            {target.rawText || t("editor.unreadable")}
          </p>
          <label htmlFor={inputId} className="mt-5 block text-sm font-semibold">
            {target.kind === "nutrient" ? t("editor.amount", { unit: target.unit }) : t("editor.name")}
          </label>
          <input
            id={inputId}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            inputMode={target.kind === "nutrient" ? "decimal" : "text"}
            autoComplete="off"
            aria-invalid={error !== null}
            aria-describedby={error ? errorId : undefined}
            className="mt-2 min-h-12 w-full rounded-xl bg-surface-2 px-4 text-base text-text shadow-[inset_0_0_0_1px_var(--line)] focus:shadow-[inset_0_0_0_2px_var(--beam)] focus:outline-none"
          />
          {error && (
            <p id={errorId} role="alert" className="mt-2 text-sm text-conflict">
              {error}
            </p>
          )}
          <p className="mt-3 text-xs text-text-dim">{t("editor.note")}</p>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit">{t("editor.save")}</Button>
          </div>
        </form>
      )}
    </Sheet>
  );
}
