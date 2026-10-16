import { get as idbGet, set as idbSet } from "idb-keyval";
import { create } from "zustand";
import type { Profile } from "../shared/contract";

export const PROFILES_KEY = "labellens.profiles";

interface ProfilesState {
  profiles: Profile[];
  hydrated: boolean;
  hydrate: () => Promise<void>;
  add: (profile: Profile) => Promise<void>;
  update: (profile: Profile) => Promise<void>;
  remove: (profileId: string) => Promise<void>;
  replaceAll: (profiles: Profile[]) => Promise<void>;
}

/** Family profiles live only in this browser (IndexedDB) — no accounts, no server copy. */
export const useProfilesStore = create<ProfilesState>()((set, get) => {
  async function commit(profiles: Profile[]): Promise<void> {
    set({ profiles });
    await idbSet(PROFILES_KEY, profiles);
  }

  return {
    profiles: [],
    hydrated: false,
    hydrate: async () => {
      if (get().hydrated) return;
      try {
        const stored = await idbGet<Profile[]>(PROFILES_KEY);
        set({ profiles: Array.isArray(stored) ? stored : [], hydrated: true });
      } catch {
        set({ hydrated: true });
      }
    },
    add: (profile) => commit([...get().profiles, profile]),
    update: (profile) =>
      commit(get().profiles.map((existing) => (existing.profile_id === profile.profile_id ? profile : existing))),
    remove: (profileId) => commit(get().profiles.filter((profile) => profile.profile_id !== profileId)),
    replaceAll: (profiles) => commit(profiles),
  };
});
