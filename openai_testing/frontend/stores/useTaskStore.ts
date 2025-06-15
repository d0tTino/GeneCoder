// /stores/useTaskStore.ts
import { create } from "zustand";
import { Step } from "@/stores/useConversationStore";

/* ───── Types ──────────────────────────────────────────────── */
type Status = "pending" | "pass" | "failed";

interface TaskStoreState {
  /* Test‑case steps coming from the backend */
  testCases: Step[];
  /* Aggregate status for the whole script */
  testCaseUpdateStatus: Status;

  /* ─── actions ─── */
  setTestCases: (steps: Step[]) => void;
  updateTestScript: (steps: Step[]) => void;
  setTestCaseUpdateStatus: (status: Status) => void;
}

export const useTaskStore = create<TaskStoreState>()((set) => ({
  testCases: [],
  testCaseUpdateStatus: "pending",

  setTestCases: (steps) => set({ testCases: steps }),
  updateTestScript: (steps) =>
    set((state) => {
      /* Build a map of existing steps by their step_number for quick lookup */
      const existingMap = new Map(
        state.testCases.map((s) => [s.step_number, { ...s }])
      );

      /* Merge each incoming step with the existing one (if any) */
      steps.forEach((incoming) => {
        const current = existingMap.get(incoming.step_number) || {};
        existingMap.set(incoming.step_number, {
          ...current,
          ...incoming,
        });
      });

      /* Preserve a stable ordering by step_number */
      const mergedSteps = Array.from(existingMap.values()).sort(
        (a, b) => a.step_number - b.step_number
      );

      return { testCases: mergedSteps };
    }),
  setTestCaseUpdateStatus: (status) => set({ testCaseUpdateStatus: status }),
}));

export default useTaskStore;
