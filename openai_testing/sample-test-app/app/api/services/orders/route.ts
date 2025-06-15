import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const ORDERS_CSV = path.join(process.cwd(), "public", "data", "orders.csv");
const CSV_HEADER =
  "orderId,name,streetAddress,city,state,zipcode,totalAmount,timestamp,itemsJson\n";

function append(row: string) {
  if (!fs.existsSync(ORDERS_CSV)) fs.writeFileSync(ORDERS_CSV, CSV_HEADER);
  fs.appendFileSync(ORDERS_CSV, row);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const {
    name,
    streetAddress,
    city,
    state,
    zipcode,
    items,
    totalAmount,
    timestamp,
  } = body;

  // Generate a plausible e-commerce order id: e.g. "ORD-20240610-ABCD"
  function generateOrderId() {
    const date = new Date();
    const y = date.getFullYear().toString().slice(-2);
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    const letters = Array.from({ length: 4 }, () =>
      String.fromCharCode(65 + Math.floor(Math.random() * 26))
    ).join("");
    return `${letters}-${y}${m}${d}`;
  }
  const orderId = generateOrderId();
  const arrivalDate = new Date(Date.now() + 3 * 86_400_000)
    .toISOString()
    .split("T")[0];

  /* very-naïve CSV escaping */
  const safe = (v: string | number) =>
    String(v).replace(/"/g, '""').replace(/,/g, " ");

  append(
    [
      orderId,
      safe(name),
      safe(streetAddress),
      safe(city),
      safe(state),
      safe(zipcode),
      totalAmount,
      timestamp,
      `"${safe(JSON.stringify(items))}"`,
    ].join(",") + "\n"
  );

  return NextResponse.json({
    orderId,
    status: "success",
    message: "Order placed successfully",
    arrivalDate,
    orderDetails: {
      name,
      streetAddress,
      city,
      state,
      zipcode,
      totalAmount,
      timestamp,
      items,
    },
  });
}
