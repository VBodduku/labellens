import { renderMessage } from "../i18n/renderMessage";
import type { Lang, Profile, ToolCallTrace } from "../shared/contract";

const KNOWN_TOOLS = new Set(["get_profiles", "get_verdict", "find_evidence", "explain_ingredient", "get_nutrition"]);

function text(value: unknown): string {
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : "";
}

/** The agent's tool calls in plain language ("Checked Thatha's results", "Searched the label for “sugar”"). */
export function describeToolCall(call: ToolCallTrace, profiles: Profile[], lang: Lang): string {
  if (!KNOWN_TOOLS.has(call.tool)) return renderMessage("tool.other", { tool: call.tool }, lang);
  const profileId = text(call.args.profile_id);
  const name = profiles.find((profile) => profile.profile_id === profileId)?.name ?? profileId;
  return renderMessage(
    `tool.${call.tool}`,
    {
      name,
      query: text(call.args.query),
      term: text(call.args.term),
      nutrient: text(call.args.key) || text(call.args.nutrient),
    },
    lang,
  );
}
