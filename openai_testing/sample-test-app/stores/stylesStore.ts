// src/store/stylesStore.ts
import { create } from "zustand";
import { fetchAllStyles } from "@/lib/styleService";

export interface StyleItem {
  id: number;
  gender: string;
  masterCategory: string;
  subCategory: string;
  articleType: string;
  baseColour: string;
  season: string;
  year: number;
  usage: string;
  productDisplayName: string;
  imageURL: string;
  priceUSD?: number;
}

interface StylesState {
  data: StyleItem[];
  loading: boolean;
  error: string | null;
  fetchStyles: () => Promise<void>;
}

export const useStylesStore = create<StylesState>((set) => ({
  data: [],
  loading: false,
  error: null,
  fetchStyles: async () => {
    set({ loading: true, error: null });
    try {
      const styles = await fetchAllStyles();
      set({ data: styles as StyleItem[], loading: false });
    } catch (e: unknown) {
      const error = e as Error;
      set({ error: error.message ?? "Failed to load styles", loading: false });
    }
  },
}));
