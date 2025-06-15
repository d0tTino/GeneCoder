import type * as React from "react";

declare module "@tanstack/react-table" {
  interface ColumnMeta<TData extends import("@tanstack/react-table").RowData, TValue> {
    style?: React.CSSProperties;
  }
} 
