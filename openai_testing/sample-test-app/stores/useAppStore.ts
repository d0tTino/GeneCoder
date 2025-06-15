// src/store/useAppStore.ts
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import { fetchAllStyles } from "@/lib/styleService";
import { StyleItem } from "./stylesStore";

export interface OrderItem {
  id: number;
  quantity: number;
  productDisplayName: string;
  imageURL: string;
  priceUSD: number;
}

export interface Order {
  orderId: string;
  items: OrderItem[];
  totalAmount: number;
  timestamp: number;
  name: string;
  streetAddress: string;
  city: string;
  state: string;
  zipcode: string;
}

export interface AppState {
  /** (Optional) auth token if you still keep it here */
  token: string | null;
  setToken: (token: string | null) => void;

  /** Orders history */
  orders: Order[];
  addOrder: (order: Order) => void;

  /** Styles catalogue (fetched from CSV-backed API) */
  styles: StyleItem[];
  loading: boolean;
  error: string | null;
  fetchStyles: () => Promise<void>;
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        /* ---------- auth (kept for legacy reasons) ---------- */
        token: null,
        setToken: (token) => set({ token }),

        /* ---------- orders ---------- */
        orders: [],
        addOrder: (order) =>
          set((state) => ({ orders: [...state.orders, order] })),

        /* ---------- styles catalog ---------- */
        styles: [],
        loading: false,
        error: null,
        fetchStyles: async () => {
          if (get().loading) return;
          set({ loading: true, error: null });
          try {
            const styles = await fetchAllStyles();
            set({ styles: styles as StyleItem[], loading: false });
          } catch (err: unknown) {
            const error = err as Error;
            console.error(error);
            set({
              error: error.message ?? "Failed to load styles",
              loading: false,
            });
          }
        },
      }),
      {
        name: "app-storage",
        /* Persist only what really matters across sessions */
        partialize: (s) => ({
          token: s.token,
          orders: s.orders,
        }),
      }
    )
  )
);
