"use client";

import { useSearchParams } from "next/navigation";
import OrderSuccess from "@/components/OrderSuccess";

export default function OrderSuccessPage() {
  const searchParams = useSearchParams();
  const orderId = searchParams.get("orderId") ?? "";
  const arrivalDate = searchParams.get("arrivalDate") ?? "";

  if (!orderId) {
    return <p className="p-4">No order information available.</p>;
  }

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 p-4">
        <OrderSuccess orderId={orderId} arrivalDate={arrivalDate} />
      </main>
    </div>
  );
}
