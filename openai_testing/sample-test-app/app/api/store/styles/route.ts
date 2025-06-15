import { NextResponse } from "next/server";
import { getStylesCache } from "@/lib/styleCache";

export async function GET() {
  const styles = getStylesCache();
  return NextResponse.json(styles);
}
