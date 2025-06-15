import { create } from "zustand";

interface CartItem {
  id: number;
  quantity: number;
}

interface CartState {
  items: CartItem[];

  /**
   * Add an item to the cart.
   * @param id        Product ID
   * @param quantity  How many to add (default = 1)
   */
  addItem: (id: number, quantity?: number) => void;

  /** Increase quantity by 1 */
  incrementItem: (id: number) => void;

  /** Decrease quantity by 1 (remove if it hits zero) */
  decrementItem: (id: number) => void;

  /** Set item quantity explicitly (remove if quantity <= 0) */
  setItemQuantity: (id: number, quantity: number) => void;

  /** Remove *all* copies of the given product from the cart */
  removeItem: (id: number) => void;

  /** Empty the entire cart */
  clear: () => void;
}

export const useCartStore = create<CartState>((set) => ({
  items: [],

  addItem: (id, quantity = 1) =>
    set((state) => {
      const existing = state.items.find((i) => i.id === id);

      if (existing) {
        return {
          items: state.items.map((i) =>
            i.id === id ? { ...i, quantity: i.quantity + quantity } : i
          ),
        };
      }

      return { items: [...state.items, { id, quantity }] };
    }),

  incrementItem: (id) =>
    set((state) => ({
      items: state.items.map((i) =>
        i.id === id ? { ...i, quantity: i.quantity + 1 } : i
      ),
    })),

  decrementItem: (id) =>
    set((state) => {
      const existing = state.items.find((i) => i.id === id);
      if (!existing) return state;
      if (existing.quantity <= 1) {
        return { items: state.items.filter((i) => i.id !== id) };
      }
      return {
        items: state.items.map((i) =>
          i.id === id ? { ...i, quantity: i.quantity - 1 } : i
        ),
      };
    }),

  setItemQuantity: (id, quantity) =>
    set((state) => {
      if (quantity <= 0)
        return { items: state.items.filter((i) => i.id !== id) };
      const existing = state.items.find((i) => i.id === id);
      if (existing) {
        return {
          items: state.items.map((i) => (i.id === id ? { ...i, quantity } : i)),
        };
      }
      return { items: [...state.items, { id, quantity }] };
    }),

  removeItem: (id) =>
    set((state) => ({ items: state.items.filter((i) => i.id !== id) })),

  clear: () => set({ items: [] }),
}));
