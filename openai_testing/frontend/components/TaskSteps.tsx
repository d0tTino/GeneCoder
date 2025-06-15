"use client";

import React, { useMemo, useEffect, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  ColumnDef,
} from "@tanstack/react-table";

import useTaskStore from "@/stores/useTaskStore";
import { Step } from "@/stores/useConversationStore";
import { emitTestCaseUpdate } from "@/components/SocketIOManager";

/* Icons */
import { CheckCircle2, XCircle, Loader2, Timer } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function TestScriptStepsTableWidget() {
  /* ─── zustand selectors ────────────────────────────── */
  const testCases = useTaskStore((s) => s.testCases);
  const testCaseUpdateStatus = useTaskStore((s) => s.testCaseUpdateStatus);
  const setTestCaseUpdateStatus = useTaskStore((s) => s.setTestCaseUpdateStatus);

  /* ─── Timer state ───────────────────────────────────── */
  const [timerStart, setTimerStart] = useState<number | null>(null);
  const [stepTimestamps, setStepTimestamps] = useState<Record<number, number>>(
    {}
  );
  const [totalTimeElapsed, setTotalTimeElapsed] = useState<number | null>(null);

  const formatTime = (ms?: number) => {
    if (!ms) return "";
    const s = Math.floor(ms / 1000);
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  };

  const getStepDuration = (n: number): number | null => {
    const ts = stepTimestamps[n];
    if (!ts || !timerStart) return null;
    const prev = Object.keys(stepTimestamps)
      .map(Number)
      .filter((k) => k < n)
      .sort((a, b) => a - b)
      .pop();
    const prevTs = prev !== undefined ? stepTimestamps[prev] : timerStart;
    return ts - prevTs;
  };

  /* ─── start timer on first render of steps ─────────── */
  useEffect(() => {
    if (testCases.length > 0 && timerStart === null) setTimerStart(Date.now());
  }, [testCases, timerStart]);

  /* ─── stamp timestamp when a step completes ────────── */
  useEffect(() => {
    if (timerStart === null) return;

    setStepTimestamps((prev) => {
      const next = { ...prev };
      testCases.forEach((step) => {
        const done = step.status === "Pass" || step.status === "Fail";
        if (done && next[step.step_number] === undefined) {
          const lastDone = Object.keys(next)
            .map(Number)
            .filter((k) => k < step.step_number)
            .sort((a, b) => a - b)
            .pop();
          const lastTs = lastDone !== undefined ? next[lastDone] : timerStart;
          let now = Date.now();
          if (now <= lastTs) now = lastTs + 1; // monotonic
          next[step.step_number] = now;
        }
      });
      return next;
    });
  }, [testCases, timerStart]);

  /* ─── total duration when all done ─────────────────── */
  useEffect(() => {
    if (
      timerStart !== null &&
      testCases.length > 0 &&
      testCases.every((s) => s.status !== "pending") &&
      totalTimeElapsed === null
    ) {
      setTotalTimeElapsed(Date.now() - timerStart);
    }
  }, [testCases, timerStart, totalTimeElapsed]);

  /* ─── sync aggregate status to server ──────────────── */
  useEffect(() => {
    const hasFail = testCases.some((s) => s.status === "Fail");
    const allPass =
      testCases.length > 0 && testCases.every((s) => s.status === "Pass");

    const nextStatus = hasFail ? "failed" : allPass ? "pass" : "pending";
    if (nextStatus !== testCaseUpdateStatus) {
      setTestCaseUpdateStatus(nextStatus as any);
      if (nextStatus !== "pending") emitTestCaseUpdate(nextStatus);
    }
  }, [testCases, testCaseUpdateStatus, setTestCaseUpdateStatus]);

  /* ─── table columns ────────────────────────────────── */
  const columns = useMemo<ColumnDef<Step>[]>(
    () => [
      {
        accessorKey: "step_number",
        header: "#",
        meta: { style: { width: "10%" } },
      },
      {
        accessorKey: "step_instructions",
        header: "Instructions",
        meta: { style: { width: "50%" } },
      },
      {
        accessorKey: "status",
        header: "Status",
        meta: { style: { width: "10%" } },
        cell: ({ row, getValue }) => {
          const status = getValue<string>();
          const reasoning = row.original.step_reasoning;
          let Icon = Loader2;
          let cls = "text-slate-600 animate-spin";
          if (status === "Pass") {
            Icon = CheckCircle2;
            cls = "text-green-600";
          } else if (status === "Fail") {
            Icon = XCircle;
            cls = "text-red-600";
          }
          return (
            <span title={reasoning}>
              <Icon className={cls} />
            </span>
          );
        },
      },
      {
        header: "Time",
        meta: { style: { width: "10%" } },
        cell: ({ row }) => {
          const n = row.original.step_number;
          const done =
            row.original.status === "Pass" || row.original.status === "Fail";
          if (!done) return <Timer className="text-gray-400" />;
          const d = getStepDuration(n);
          return d ? (
            <span className="text-sm text-gray-500">{formatTime(d)}</span>
          ) : (
            <Timer className="text-gray-400" />
          );
        },
      },
      {
        header: "Image",
        meta: { style: { width: "20%" } },
        cell: ({ row }) => {
          const path = row.original.image_path;
          if (!path) return <span className="text-gray-400">No image</span>;
          return (
            <a
              href={path}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              View Screenshot
            </a>
          );
        },
      },
    ],
    [stepTimestamps, timerStart]
  );

  const table = useReactTable({
    data: testCases,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  /* ─── UI ────────────────────────────────────────────── */
  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6">
      {/* ⬇️ overflow-hidden clips inner table so the card’s rounded
          bottom corners are visible */}
      <Card className="rounded-b-xl overflow-hidden">
        <CardHeader className="pb-4">
          <CardTitle>
            Task Steps{" "}
            {totalTimeElapsed !== null && (
              <span className="text-sm font-normal text-gray-500">
                (Total time: {formatTime(totalTimeElapsed)})
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full table-fixed divide-y divide-gray-200">
              <thead className="bg-gray-50">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((h) => (
                      <th
                        key={h.id}
                        style={h.column.columnDef.meta?.style}
                        className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        {h.isPlaceholder
                          ? null
                          : flexRender(
                              h.column.columnDef.header,
                              h.getContext()
                            )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {testCases.length === 0 ? (
                  <tr>
                    {/* “#” column */}
                    <td
                      style={{ width: "10%" }}
                      className="px-6 py-4 text-sm text-gray-500 whitespace-normal"
                    >
                      -
                    </td>
                    {/* Instructions column */}
                    <td
                      style={{ width: "50%" }}
                      className="px-6 py-4 text-sm text-gray-500 whitespace-normal"
                    >
                      Task step instructions will appear here
                    </td>
                    {/* Status column */}
                    <td
                      style={{ width: "10%" }}
                      className="px-6 py-4 text-sm text-gray-500 whitespace-normal"
                    />
                    {/* Time column */}
                    <td
                      style={{ width: "10%" }}
                      className="px-6 py-4 text-sm text-gray-500 whitespace-normal"
                    />
                    {/* Image column */}
                    <td
                      style={{ width: "20%" }}
                      className="px-6 py-4 text-sm text-gray-500 whitespace-normal"
                    />
                  </tr>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <tr key={row.id}>
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          style={cell.column.columnDef.meta?.style}
                          className="px-6 py-4 text-sm text-gray-500 whitespace-normal"
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
