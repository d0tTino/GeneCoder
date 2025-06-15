import { parse } from "csv-parse/sync";
import { promises as fs } from "fs";
import path from "path";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  // Validate
  const { id: idRaw } = await params;
  const id = Number(idRaw);
  if (Number.isNaN(id)) {
    return new Response(
      JSON.stringify({ error: "Invalid style id – must be a number" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  // Read & parse the CSV
  const csvPath = path.join(process.cwd(), "public", "data", "styles.csv");
  const csvRaw = await fs.readFile(csvPath, "utf8");
  const records: Record<string, string>[] = parse(csvRaw, {
    columns: true,
    skip_empty_lines: true,
  });

  // Look‑up
  const style = records.find((r) => Number(r.id) === id);
  if (!style) {
    return new Response(
      JSON.stringify({ error: `Style with id ${id} not found` }),
      { status: 404, headers: { "Content-Type": "application/json" } }
    );
  }

  // Success
  return new Response(JSON.stringify({ style }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
