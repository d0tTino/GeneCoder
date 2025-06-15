"use client";

import React, { useEffect } from "react";
import io, { Socket } from "socket.io-client";

import useConversationStore from "@/stores/useConversationStore";
import useTaskStore from "@/stores/useTaskStore";

/** One singleton client socket. */
let socket: Socket | null = null;

/* ───── helper emitters (exported) ─────────────────────────── */
export function sendSocketMessage(msg: string) {
  socket?.emit("message", msg);
}

export function emitTestCaseInitiated(formData: any) {
  socket?.emit("testCaseInitiated", formData);
}

export function emitTestCaseUpdate(status: string) {
  socket?.emit("testCaseUpdate", status);
}

/* ───── Manager component  (mount once, e.g. in RootLayout) ─ */
export function SocketIOManager() {
  /* store actions */
  const addChatMessage = useConversationStore((s) => s.addChatMessage);
  const addConversationItem = useConversationStore(
    (s) => s.addConversationItem
  );
  const setTestCases = useTaskStore((s) => s.setTestCases);
  const updateTestScript = useTaskStore((s) => s.updateTestScript);

  useEffect(() => {
    // Connect to standalone WebSocket server
    const SOCKET_SERVER_URL =
      process.env.NEXT_PUBLIC_SOCKET_SERVER_URL || "http://localhost:8000";
    socket = io(SOCKET_SERVER_URL);

      socket.on("connect", () =>
        console.log("[socket] connected:", socket?.id)
      );

      /* initial JSON test steps */
      socket.on("testcases", (msg: string) => {
        try {
          const parsed = JSON.parse(msg);
          if (Array.isArray(parsed.steps)) setTestCases(parsed.steps);
        } catch (err) {
          console.error("✖ parse testcases", err);
        }
      });

      /* step‑by‑step status updates */
      socket.on("testscriptupdate", (payload: string | object) => {
        try {
          const parsed =
            typeof payload === "string" ? JSON.parse(payload) : payload;
          if (Array.isArray(parsed.steps)) updateTestScript(parsed.steps);
        } catch (err) {
          console.error("✖ parse testscriptupdate", err);
        }
      });

      socket.on("message", (msg: string) => {
        addChatMessage({
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: msg }],
        } as any);

        addConversationItem({
          role: "assistant",
          content: msg,
          timestamp: new Date().toLocaleTimeString(),
        });
      });
    // connection setup complete

    return () => {
      socket?.disconnect();
      socket = null;
    };
  }, [addChatMessage, addConversationItem, setTestCases, updateTestScript]);

  return null;
}
