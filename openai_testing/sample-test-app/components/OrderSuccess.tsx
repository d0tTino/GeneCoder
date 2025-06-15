import confetti from "canvas-confetti";
import { useEffect } from "react";
import Link from "next/link";
import { useAppStore } from "@/stores/useAppStore";

export interface OrderItem {
  id: number;
  productDisplayName: string;
  imageURL: string;
  priceUSD?: number;
  quantity: number;
}

export interface OrderDetails {
  name: string;
  streetAddress: string;
  city: string;
  state: string;
  zipcode: string;
  items: OrderItem[];
  totalAmount: number;
  timestamp: number;
}

export interface OrderSuccessProps {
  orderId: string;
  arrivalDate: string;
}

export default function OrderSuccess({
  orderId,
  arrivalDate,
}: OrderSuccessProps) {
  // retrieve stored order details from app store
  const storedOrder = useAppStore((s) =>
    s.orders.find((o) => o.orderId === orderId)
  );
  const orderDetails = storedOrder;
  /* confetti burst once */
  useEffect(() => {
    confetti({ particleCount: 100, spread: 160, origin: { y: 0.6 } });
  }, []);

  return (
    <div className="flex flex-col gap-4 mt-8">
      <div className="bg-stone-100 rounded-sm p-6 mb-2 mr-auto">
        <div className="mb-2">
          <span className="block text-xl font-semibold mb-1">
            Order #{orderId} Placed Successfully!
          </span>
        </div>
        <div className="space-y-2">
          <p>
            Your order is estimated to arrive by <strong>{arrivalDate}</strong>.
          </p>
          {!orderDetails && (
            <p className="text-sm text-muted-foreground">
              We’ve emailed you a receipt. You can always view your orders in
              your profile.
            </p>
          )}
        </div>
      </div>

      {orderDetails && (
        <div className="flex flex-col gap-8">
          {/* Items */}
          <div className="flex-1 lg:w-2/3">
            <div className="flex flex-col gap-4">
              {orderDetails.items.length === 0 ? (
                <p className="p-4">No items in this order.</p>
              ) : (
                orderDetails.items.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-4 p-4 min-h-[64px]"
                  >
                    {/* Product image */}
                    <img
                      src={item.imageURL}
                      alt={item.productDisplayName}
                      className="h-24 w-24 object-contain rounded"
                    />
                    {/* Product name */}
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-sm line-clamp-2">
                        {item.productDisplayName}
                      </span>
                    </div>
                    {/* Quantity */}
                    <div className="text-sm text-gray-700 w-16 text-right">
                      Qty:{" "}
                      <span className="font-semibold">{item.quantity}</span>
                    </div>
                    {/* Total price for this item */}
                    <div className="text-base font-semibold w-20 text-right">
                      ${(item.priceUSD * item.quantity).toFixed(2)}
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="mt-8 px-2 text-xl flex justify-between">
              <span className="text-stone-600 font-medium">Total</span>
              <span className="text-stone-800">
                ${orderDetails.totalAmount.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Shipping address */}
          <div className="flex mt-8">
            <div className="bg-stone-50 rounded-sm p-4 flex flex-col gap-2 min-w-1/3">
              <div className="text-lg font-bold mb-2">
                Your order will be shipped to:
              </div>
              <div className="font-medium">{orderDetails.name}</div>
              <div>{orderDetails.streetAddress}</div>
              <div>
                {orderDetails.city}, {orderDetails.state} {orderDetails.zipcode}
              </div>
            </div>
          </div>
        </div>
      )}

      <Link href="/" className="flex mt-4">
        <div className="bg-black text-white cursor-pointer rounded-sm px-2.5 py-1.5 hover:bg-stone-800">
          Continue shopping
        </div>
      </Link>
    </div>
  );
}
