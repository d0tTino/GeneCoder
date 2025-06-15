import { useCallback } from "react";

// Basic toast hook implementation. Currently logs to console and shows an alert on the client side.
// Can be replaced with a more sophisticated UI toast library later.
export interface ToastOptions {
  title: string;
  description?: string;
  variant?: "default" | "destructive";
}

export function useToast() {
  const toast = useCallback((opts: ToastOptions) => {
    // Fallback implementation: console + alert.
    const { title, description } = opts;
    const message = description ? `${title}: ${description}` : title;

    if (typeof window !== "undefined") {
      // Non‑blocking so it doesn't interrupt frame rendering.
      setTimeout(() => alert(message), 0);
    } else {
      console.log(`[toast] ${message}`);
    }
  }, []);

  return { toast } as const;
}
