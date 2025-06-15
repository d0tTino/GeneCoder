import { create } from "zustand";

export interface StyleFilters {
  gender: string[];
  masterCategory: string[];
  subCategory: string[];
  season: string[];
  usage: string[];
  maxPrice: string[];
  color: string[];
}

interface StyleFiltersState extends StyleFilters {
  toggleFilter: (p: { key: keyof StyleFilters; value: string }) => void;
  clearFilters: () => void;
}

const init: StyleFilters = {
  gender: [],
  masterCategory: [],
  subCategory: [],
  season: [],
  usage: [],
  maxPrice: [],
  color: [],
};

export const useStyleFiltersStore = create<StyleFiltersState>((set) => ({
  ...init,
  toggleFilter: ({ key, value }) =>
    set((state) => {
      const list = state[key];
      const next = list.includes(value)
        ? list.filter((v) => v !== value)
        : [...list, value];
      return { [key]: next } as Partial<StyleFiltersState>;
    }),
  clearFilters: () => set({ ...init }),
}));
