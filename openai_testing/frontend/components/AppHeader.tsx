"use client";

import React from "react";

export default function AppHeader() {
  return (
    <div className="space-y-2 mt-4 mb-8">
      <h1 className="flex items-center gap-2 text-3xl font-bold">
        Automated Testing Agent
      </h1>
      <p className="text-muted-foreground">
        Authors and executes tests on your behalf using the OpenAI&nbsp;CUA
        model.
      </p>
    </div>
  );
}
