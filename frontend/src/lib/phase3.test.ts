import { describe, expect, it } from "vitest";
import { fixtureCatalog, fixtureProfileParse, fixtureProfiles, fixtureScanResult } from "../api/fixtures";
import { finalizeParsedProfiles, nextColor, PROFILE_COLORS, restrictionFromCatalog } from "./profileParse";
import { pickVoice, recognitionErrorKey, sentenceChunks } from "./speech";
import { speechScript } from "./speechScript";
import { describeToolCall } from "./toolTrace";

const voices = [
  { name: "Google US English", lang: "en-US" },
  { name: "Microsoft Heera", lang: "en-IN" },
  { name: "Google हिन्दी", lang: "hi-IN" },
  { name: "Telugu (generic)", lang: "te" },
];

describe("speech helpers", () => {
  it("prefers the exact Indian voice, then any voice of the language", () => {
    expect(pickVoice(voices, "en")?.name).toBe("Microsoft Heera");
    expect(pickVoice(voices, "hi")?.name).toBe("Google हिन्दी");
    expect(pickVoice(voices, "te")?.name).toBe("Telugu (generic)");
    expect(pickVoice([{ name: "x", lang: "en-US" }], "te")).toBeNull();
    expect(pickVoice([{ name: "underscore", lang: "hi_IN" }], "hi")?.name).toBe("underscore");
  });

  it("maps recognition errors to friendly message keys", () => {
    expect(recognitionErrorKey("not-allowed")).toBe("speech.error.notAllowed");
    expect(recognitionErrorKey("no-speech")).toBe("speech.error.noSpeech");
    expect(recognitionErrorKey("network")).toBe("speech.error.network");
    expect(recognitionErrorKey("audio-capture")).toBe("speech.error.generic");
    expect(recognitionErrorKey("aborted")).toBeNull();
  });

  it("splits long text into sentences, including the Devanagari danda", () => {
    expect(sentenceChunks("One. Two! Three?")).toEqual(["One.", "Two!", "Three?"]);
    expect(sentenceChunks("पहला। दूसरा।")).toEqual(["पहला।", "दूसरा।"]);
  });
});

describe("read-aloud script", () => {
  const thatha = fixtureScanResult.reports[1]!;
  const profile = fixtureProfiles.find((candidate) => candidate.profile_id === "p_thatha");

  it("short mode says the overall line and the most important result", () => {
    expect(speechScript(thatha, profile, "en", "short")).toBe(
      "Thatha: Conflicts with this profile. Diabetic: limit sugar: Conflict. Total sugars is 38 g per 100 g, above your limit of 22.5 g.",
    );
  });

  it("full mode reads the summary and every result, in the chosen language", () => {
    const full = speechScript(thatha, profile, "en", "full");
    expect(full.startsWith(thatha.summary ?? "")).toBe(true);
    expect(full).toContain("Low sodium (BP): Can't determine.");
    const telugu = speechScript(thatha, profile, "te", "full");
    expect(telugu).toContain("తక్కువ సోడియం (బీపీ)");
    expect(telugu).toContain("నిర్ణయించలేం");
  });
});

describe("tool trace", () => {
  it("describes the agent's steps in plain language", () => {
    const calls = [
      { tool: "get_profiles", args: {}, result_summary: "" },
      { tool: "get_verdict", args: { profile_id: "p_thatha" }, result_summary: "" },
      { tool: "find_evidence", args: { query: "total sugars" }, result_summary: "" },
      { tool: "get_nutrition", args: { key: "sodium_mg", basis: "per_100g" }, result_summary: "" },
      { tool: "mystery", args: {}, result_summary: "" },
    ];
    expect(calls.map((call) => describeToolCall(call, fixtureProfiles, "en"))).toEqual([
      "Checked the family profiles",
      "Checked Thatha's results",
      "Searched the label for “total sugars”",
      "Read the Sodium value",
      "Used mystery",
    ]);
  });
});

describe("profiles from the catalog and the sentence parser", () => {
  it("builds a restriction with the catalog's default severity and threshold", () => {
    const sugar = fixtureCatalog.find((item) => item.key === "diabetes_sugar")!;
    const restriction = restrictionFromCatalog(sugar);
    expect(restriction).toMatchObject({ key: "diabetes_sugar", kind: "health_limit", severity: "strict", source_text: null });
    expect(restriction.threshold).toEqual(sugar.default_threshold);
    expect(restriction.threshold).not.toBe(sugar.default_threshold);
    const peanut = fixtureCatalog.find((item) => item.key === "peanut")!;
    expect(restrictionFromCatalog(peanut, "preference")).toMatchObject({ severity: "preference", threshold: null });
  });

  it("gives confirmed proposals fresh ids and unused colours, and drops unnamed people", () => {
    const proposed = [...structuredClone(fixtureProfileParse.profiles), { profile_id: "p_x", name: "  ", color: null, restrictions: [] }];
    const saved = finalizeParsedProfiles(proposed, fixtureProfiles);
    expect(saved).toHaveLength(fixtureProfileParse.profiles.length);
    const ids = saved.flatMap((profile) => [profile.profile_id, ...profile.restrictions.map((restriction) => restriction.id)]);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.some((id) => fixtureProfileParse.profiles.some((profile) => profile.profile_id === id))).toBe(false);
    const used = new Set(fixtureProfiles.map((profile) => profile.color));
    for (const profile of saved) expect(used.has(profile.color)).toBe(false);
    expect(saved[0]?.restrictions[0]?.source_text).toBe(fixtureProfileParse.profiles[0]?.restrictions[0]?.source_text);
  });

  it("cycles colours once the palette is used up", () => {
    expect(nextColor([])).toBe(PROFILE_COLORS[0]);
    expect(PROFILE_COLORS).toContain(nextColor([...PROFILE_COLORS]));
  });
});
