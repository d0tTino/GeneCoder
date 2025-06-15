"use client";

import React, { useEffect, useRef } from "react";
import { Dot } from "lucide-react";
import useConversationStore from "@/stores/useConversationStore";

export default function SidePanel() {
  const conversationItems = useConversationStore((s) => s.conversationItems);

  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [conversationItems]);

  return (
    <div className="w-full h-full flex flex-col border-l bg-background">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-2">
          <h3 className="font-medium">Agent Messages</h3>
        </div>
      </div>

      <div className="flex flex-col flex-1 min-h-0">
        <div
          ref={listRef}
          className="flex-1 overflow-y-auto p-2 space-y-3 scroll-smooth"
        >
          {conversationItems.map((m, i) => (
            <div key={i} className="flex gap-2 items-start">
              <Dot size={32} className="text-green-500" />
              <div className="flex-1 flex flex-col gap-1 mt-1">
                <div className="text-sm">{m.content}</div>
                <div className="text-xs text-muted-foreground">
                  {m.timestamp}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
