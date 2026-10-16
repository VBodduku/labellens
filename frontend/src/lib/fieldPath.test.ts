import { describe, expect, it } from "vitest";
import { fixtureScanResult } from "../api/fixtures";
import { applyCorrections, makeCorrection } from "./corrections";
import { formatPath, getAtPath, parsePath, setAtPath } from "./fieldPath";

describe("field paths", () => {
  it("parses keys and array indices", () => {
    expect(parsePath("nutrition.rows[2].values[0].amount")).toEqual(["nutrition", "rows", 2, "values", 0, "amount"]);
    expect(formatPath(["nutrition", "rows", 2, "values", 0, "amount"])).toBe("nutrition.rows[2].values[0].amount");
  });

  it("reads and immutably writes nested values", () => {
    const source = { a: [{ b: 1 }, { b: 2 }] };
    const next = setAtPath(source, "a[1].b", 5);
    expect(getAtPath(next, "a[1].b")).toBe(5);
    expect(source.a[1]?.b).toBe(2);
  });

  it("refuses paths that do not exist", () => {
    expect(() => setAtPath({ a: [] }, "a[3].b", 1)).toThrow(/does not exist/);
    expect(getAtPath({ a: 1 }, "a.b.c")).toBeUndefined();
  });
});

describe("corrections", () => {
  const extraction = fixtureScanResult.extraction;
  const sodiumRow = extraction.nutrition?.rows.findIndex((row) => row.key === "sodium_mg") ?? -1;

  it("patches a nutrient value and flags it as corrected by the user", () => {
    const path = `nutrition.rows[${sodiumRow}].values[0].amount`;
    const correction = makeCorrection(extraction, path, 145, new Date("2026-10-16T10:00:00Z"));
    expect(correction).toMatchObject({ field_path: path, new_value: 145, at: "2026-10-16T10:00:00.000Z" });

    const patched = applyCorrections(extraction, [correction]);
    const value = patched.nutrition?.rows[sodiumRow]?.values[0];
    expect(value?.amount).toBe(145);
    expect(value?.corrected_by_user).toBe(true);
    expect(patched.user_corrections).toEqual([correction]);
  });

  it("records the previous value for an ingredient rename", () => {
    const correction = makeCorrection(extraction, "ingredients[0].name", "Cane Sugar");
    expect(correction.old_value).toBe("Sugar");
  });
});
