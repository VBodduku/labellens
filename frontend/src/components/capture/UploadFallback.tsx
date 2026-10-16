import { ImagePlus } from "lucide-react";
import { useRef, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

interface UploadFallbackProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  variant?: "icon" | "button";
  multiple?: boolean;
}

/** Photo picker — always available beside the camera, and the main path when the camera can't be used. */
export function UploadFallback({ onFiles, disabled = false, variant = "icon", multiple = true }: UploadFallbackProps) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length > 0) onFiles(files);
  }

  return (
    <>
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        multiple={multiple}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={onChange}
      />
      {variant === "icon" ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => input.current?.click()}
          aria-label={t("scan.upload")}
          title={t("scan.upload")}
          className="flex size-12 items-center justify-center rounded-full bg-black/50 text-white backdrop-blur-md disabled:opacity-40"
        >
          <ImagePlus className="size-5" aria-hidden="true" />
        </button>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => input.current?.click()}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-chip bg-white px-5 text-sm font-semibold text-black disabled:opacity-40"
        >
          <ImagePlus className="size-4" aria-hidden="true" />
          {t("scan.upload")}
        </button>
      )}
    </>
  );
}
