import { renderMessageParts, type MessageParams } from "../../i18n/renderMessage";
import type { Lang } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

interface MessageProps {
  messageKey: string;
  params?: MessageParams;
  lang?: Lang;
  className?: string;
}

/** Renders an engine message; text copied from the packet appears verbatim in the evidence font. */
export function Message({ messageKey, params, lang, className }: MessageProps) {
  const currentLang = useUiStore((state) => state.lang);
  const parts = renderMessageParts(messageKey, params, lang ?? currentLang);
  return (
    <span className={className}>
      {parts.map((part, index) =>
        part.kind === "label" ? (
          <span key={index} lang="" className="evidence-text text-[0.92em] text-text">
            {part.text}
          </span>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </span>
  );
}
