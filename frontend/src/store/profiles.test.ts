import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "../shared/contract";

const storage = new Map<string, unknown>();
vi.mock("idb-keyval", () => ({
  get: vi.fn(async (key: string) => storage.get(key)),
  set: vi.fn(async (key: string, value: unknown) => void storage.set(key, value)),
}));

const { PROFILES_KEY, useProfilesStore } = await import("./profiles");

const aarav: Profile = { profile_id: "p_aarav", name: "Aarav", color: "#ff7a59", restrictions: [] };
const thatha: Profile = { profile_id: "p_thatha", name: "Thatha", color: "#7c9cff", restrictions: [] };

describe("profiles store", () => {
  beforeEach(() => {
    storage.clear();
    useProfilesStore.setState({ profiles: [], hydrated: false });
  });

  it("hydrates from IndexedDB once", async () => {
    storage.set(PROFILES_KEY, [aarav]);
    await useProfilesStore.getState().hydrate();
    expect(useProfilesStore.getState().profiles).toEqual([aarav]);
    expect(useProfilesStore.getState().hydrated).toBe(true);
  });

  it("persists add, update and remove", async () => {
    const store = useProfilesStore.getState();
    await store.add(aarav);
    await store.add(thatha);
    await useProfilesStore.getState().update({ ...thatha, name: "Thatha garu" });
    expect(storage.get(PROFILES_KEY)).toEqual([aarav, { ...thatha, name: "Thatha garu" }]);

    await useProfilesStore.getState().remove("p_aarav");
    expect(useProfilesStore.getState().profiles.map((profile) => profile.profile_id)).toEqual(["p_thatha"]);
    expect(storage.get(PROFILES_KEY)).toEqual(useProfilesStore.getState().profiles);
  });
});
