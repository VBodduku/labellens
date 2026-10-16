import type { Lang } from "../shared/contract";
import { formatNumber, joinWithOr } from "../lib/format";
import { lookup } from "./resources";

export interface MessageSegment {
  text: string;
  /** `label` = text copied from the packet; render verbatim in the evidence (mono) font. */
  kind: "text" | "label";
}

export type MessageParams = Record<string, string | number>;

const PLACEHOLDER = /\{(\w+)\}/g;
const LABEL_PARAMS = new Set(["term", "item"]);
export const MISSING_PARAM = "—";

function translateParam(name: string, value: string | number, lang: Lang): MessageSegment {
  if (LABEL_PARAMS.has(name)) return { text: String(value), kind: "label" };
  if (typeof value === "number") return { text: formatNumber(value, lang), kind: "text" };
  if (name === "category") {
    const names = value
      .split("|")
      .filter(Boolean)
      .map((id) => lookup(`categories.${id}`, lang) ?? id);
    return { text: joinWithOr(names, lang), kind: "text" };
  }
  if (name === "nutrient") return { text: lookup(`nutrients.${value}`, lang) ?? value, kind: "text" };
  if (name === "basis") return { text: lookup(`basis.${value}`, lang) ?? value, kind: "text" };
  return { text: value, kind: "text" };
}

/**
 * Renders an engine message_key with its params (frontend spec §8). category → translated category
 * names joined with the locale's "or"; nutrient/basis → translated names; term/item → label text
 * verbatim; numbers → locale formatted. Unknown keys fall back to English, then to the key itself.
 */
export function renderMessageParts(key: string, params: MessageParams = {}, lang: Lang = "en"): MessageSegment[] {
  const template = lookup(key, lang) ?? key;
  const segments: MessageSegment[] = [];
  let cursor = 0;
  for (const match of template.matchAll(PLACEHOLDER)) {
    const [placeholder, name = ""] = match;
    const index = match.index ?? 0;
    if (index > cursor) segments.push({ text: template.slice(cursor, index), kind: "text" });
    const value = params[name];
    segments.push(value === undefined ? { text: MISSING_PARAM, kind: "text" } : translateParam(name, value, lang));
    cursor = index + placeholder.length;
  }
  if (cursor < template.length) segments.push({ text: template.slice(cursor), kind: "text" });
  return segments;
}

export function renderMessage(key: string, params: MessageParams = {}, lang: Lang = "en"): string {
  return renderMessageParts(key, params, lang)
    .map((segment) => segment.text)
    .join("");
}
