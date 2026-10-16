/**
 * Field paths address a value inside a LabelExtraction, e.g. `ingredients[3].name` or
 * `nutrition.rows[2].values[0].amount`. Segments are object keys separated by dots, array indices in
 * brackets. This is the format the frontend writes into Correction.field_path.
 */
export type PathSegment = string | number;

const SEGMENT = /([^.[\]]+)|\[(\d+)\]/g;

export function parsePath(path: string): PathSegment[] {
  const segments: PathSegment[] = [];
  for (const match of path.matchAll(SEGMENT)) {
    if (match[2] !== undefined) segments.push(Number(match[2]));
    else if (match[1] !== undefined) segments.push(match[1]);
  }
  if (segments.length === 0) throw new Error(`Empty field path: "${path}"`);
  return segments;
}

export function formatPath(segments: PathSegment[]): string {
  return segments
    .map((segment, index) => (typeof segment === "number" ? `[${segment}]` : index === 0 ? segment : `.${segment}`))
    .join("");
}

function isContainer(value: unknown): value is Record<string | number, unknown> {
  return typeof value === "object" && value !== null;
}

export function getAtPath(root: unknown, path: string): unknown {
  let current: unknown = root;
  for (const segment of parsePath(path)) {
    if (!isContainer(current)) return undefined;
    current = current[segment];
  }
  return current;
}

/** Returns a deep copy of `root` with the value at `path` replaced. Throws if the path does not exist. */
export function setAtPath<T>(root: T, path: string, value: unknown): T {
  const segments = parsePath(path);
  const copy = structuredClone(root);
  let current: unknown = copy;
  segments.forEach((segment, index) => {
    if (!isContainer(current) || !(segment in current)) {
      throw new Error(`Field path does not exist: "${path}"`);
    }
    if (index === segments.length - 1) current[segment] = value;
    else current = current[segment];
  });
  return copy;
}
