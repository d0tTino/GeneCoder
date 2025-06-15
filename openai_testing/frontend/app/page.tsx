"use client";

import { useState } from "react";
import ConfigPanel from "@/components/ConfigPanel";
import SidePanel from "@/components/SidePanel";
import TaskSteps from "@/components/TaskSteps";

export default function Main() {
  const [isSideOpen, setIsSideOpen] = useState(false);

  /* show TaskSteps only after the configuration is submitted */
  const [configSubmitted, setConfigSubmitted] = useState(false);

  return (
    /* column that fills the <main> area supplied by layout.tsx */
    <div className="flex flex-col h-full">
      {/* ─── MOBILE TOP BAR (hamburger) ────────────────────── */}
      <div className="sm:hidden flex items-center justify-between p-4 bg-gray-100 shrink-0">
        <h1 className="text-lg font-semibold">Settings</h1>
        <button
          onClick={() => setIsSideOpen(true)}
          className="p-2 rounded-md hover:bg-gray-200 focus:outline-none focus:ring"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
      </div>

      {/* ─── MAIN ROW (desktop) ────────────────────────────── */}
      <div className="flex flex-1 min-h-0">
        {/* LEFT COLUMN – form / summary + (conditional) task table  */}
        <div className="flex flex-col w-full sm:w-3/4 overflow-y-auto">
          <ConfigPanel onSubmitted={() => setConfigSubmitted(true)} />

          {/* Show task-steps only after the config has been submitted */}
          {configSubmitted && <TaskSteps />}
        </div>

        {/* RIGHT COLUMN – agent side-panel – fixed width & full height */}
        <div className="hidden sm:block sm:w-1/4 border-l h-full">
          <SidePanel />
        </div>
      </div>

      {/* ─── MOBILE DRAWER (same SidePanel) ────────────────── */}
      {isSideOpen && (
        <div
          className="fixed inset-0 z-50 flex bg-black/50"
          onClick={() => setIsSideOpen(false)}
        >
          <div
            className="ml-auto w-3/4 max-w-xs bg-white h-full shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-lg font-medium">Menu</h2>
              <button
                onClick={() => setIsSideOpen(false)}
                className="p-2 rounded-md hover:bg-gray-200 focus:outline-none focus:ring"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            {/* let the drawer content scroll independently */}
            <div className="p-4 overflow-y-auto h-[calc(100%-64px)]">
              <SidePanel />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
