"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useAppStore } from "@/stores/useAppStore";
import { useCartStore } from "@/stores/cartStore";
import { checkoutOrder } from "@/lib/orderService";
import { fetchStyleById } from "@/lib/styleService";
import { useToast } from "@/hooks/use-toast";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { QtSelect } from "@/components/ui/qt-select";
import { Trash } from "lucide-react";

interface ItemData {
  id: number;
  productDisplayName: string;
  priceUSD?: number;
  imageURL: string;
}

/* ──────────────────────────────────────────────────────────
   FORM – collect shipping / payment details
   ──────────────────────────────────────────────────────────*/
function PaymentMethod({
  onCheckout,
}: {
  onCheckout: (address: {
    name: string;
    email: string;
    streetAddress: string;
    city: string;
    state: string;
    zipcode: string;
  }) => Promise<void>;
}) {
  const [address, setAddress] = useState<{
    name: string;
    email: string;
    streetAddress: string;
    city: string;
    state: string;
    zipcode: string;
    [key: string]: string;
  }>({
    name: "",
    email: "",
    streetAddress: "",
    city: "",
    state: "",
    zipcode: "",
  });
  const [errors, setErrors] = useState<
    Partial<Record<keyof typeof address, boolean>>
  >({});

  const validateAndCheckout = () => {
    const newErrors: Partial<Record<keyof typeof address, boolean>> = {};
    (Object.keys(address) as (keyof typeof address)[]).forEach((k) => {
      if (!address[k].trim()) newErrors[k] = true;
    });
    setErrors(newErrors);
    if (Object.keys(newErrors).length === 0) onCheckout(address);
  };

  const fields = [
    {
      label: "Name",
      name: "name",
      placeholder: "First and last name",
    },
    {
      label: "Email",
      name: "email",
      placeholder: "email@example.com",
    },
    {
      label: "Street Address",
      name: "streetAddress",
      placeholder: "100, Main St",
    },
    {
      label: "City",
      name: "city",
      placeholder: "City",
    },
    {
      label: "State",
      name: "state",
      placeholder: "State",
    },
    {
      label: "Zipcode",
      name: "zipcode",
      placeholder: "Zip / Postal code",
    },
  ];

  return (
    <div className="bg-stone-50 rounded-sm p-4 flex flex-col gap-4">
      <div>
        <span className="block text-lg font-semibold text-stone-800 mb-1">
          Shipping Details
        </span>
        <span className="block text-sm text-stone-600 mb-2">
          Provide a shipping address to finalise your order.
        </span>
      </div>
      <div className="grid gap-4">
        {fields.map(({ label, name, placeholder }) => (
          <div className="grid gap-1" key={name}>
            <Label htmlFor={name}>{label}</Label>
            <Input
              id={name}
              placeholder={placeholder}
              value={address[name]}
              onChange={(e) =>
                setAddress((p) => ({ ...p, [name]: e.target.value }))
              }
              className={clsx(
                "bg-white",
                errors[name] ? "border-red-500 focus:ring-red-500" : ""
              )}
            />
          </div>
        ))}
      </div>
      <Button className="w-full mt-2" onClick={validateAndCheckout}>
        Checkout
      </Button>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   MAIN CART VIEW
   ──────────────────────────────────────────────────────────*/
export default function CartView() {
  const { toast } = useToast();
  const router = useRouter();

  /* 1️⃣  Items in cart */
  const cartItems = useCartStore((s) => s.items);
  const clearCart = useCartStore((s) => s.clear);

  /* 2️⃣  Store order history */
  const addOrder = useAppStore((s) => s.addOrder);

  const [productData, setProductData] = useState<Record<number, ItemData>>({});
  const [loading, setLoading] = useState(true);

  /* Fetch data for each product in cart */
  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const pairs = await Promise.all(
          cartItems.map(async ({ id }) => {
            const data = await fetchStyleById(id);
            return [id, data] as const;
          })
        );
        setProductData(Object.fromEntries(pairs) as Record<number, ItemData>);
      } finally {
        setLoading(false);
      }
    };

    if (cartItems.length) fetchAll();
    else setLoading(false);
  }, [cartItems]);

  const total = cartItems.reduce(
    (sum, it) => sum + (productData[it.id]?.priceUSD || 0) * it.quantity,
    0
  );

  const handleCheckout = async (addr: {
    name: string;
    email: string;
    streetAddress: string;
    city: string;
    state: string;
    zipcode: string;
  }) => {
    if (cartItems.length === 0) {
      toast({ title: "Cart is empty", variant: "destructive" });
      return;
    }

    const itemsForOrder = cartItems.map(({ id, quantity }) => ({
      id,
      quantity,
      productDisplayName: productData[id]?.productDisplayName || "Unknown",
      imageURL: productData[id]?.imageURL || "",
      priceUSD: productData[id]?.priceUSD || 0,
    }));

    try {
      const res = await checkoutOrder({
        ...addr,
        items: itemsForOrder,
        totalAmount: total,
        timestamp: Date.now(),
      });

      if (res.status === "success") {
        // Save the order locally, including shipping details
        addOrder({
          orderId: res.orderId,
          items: itemsForOrder,
          totalAmount: total,
          timestamp: Date.now(),
          name: addr.name,
          streetAddress: addr.streetAddress,
          city: addr.city,
          state: addr.state,
          zipcode: addr.zipcode,
        });

        // Clear the cart
        clearCart();

        // Navigate straight to the success page
        router.push(
          `/order-success?orderId=${
            res.orderId
          }&arrivalDate=${encodeURIComponent(res.arrivalDate ?? "")}`
        );
      }
    } catch (e) {
      console.error("Checkout failed", e);
      toast({
        title: "Checkout failed",
        description: "Something went wrong while processing your order.",
        variant: "destructive",
      });
    }
  };

  if (loading) return <p className="p-4">Loading cart details...</p>;

  /* ─────────── default render ─────────── */
  return (
    <div className="flex flex-col p-4">
      <div className="flex flex-col lg:flex-row gap-8">
        {/* Items */}
        <div className="flex-1 lg:w-2/3 min-w-0 max-h-[80vh] overflow-y-auto">
          <div className="flex flex-col gap-4">
            {cartItems.length === 0 ? (
              <p className="p-4">Your cart is empty.</p>
            ) : (
              cartItems.map(({ id, quantity }) => {
                const product = productData[id];
                if (!product) return null;
                const itemTotal = (product.priceUSD || 0) * quantity;
                return (
                  <div
                    key={id}
                    className="flex items-center gap-4 bg-stone-50 rounded-sm p-4 min-h-[64px]"
                  >
                    {/* Product image */}
                    <img
                      src={product.imageURL}
                      alt={product.productDisplayName}
                      className="h-24 w-24 object-contain rounded"
                    />
                    {/* Product name */}
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-sm line-clamp-2">
                        {product.productDisplayName}
                      </span>
                    </div>
                    {/* Quantity */}
                    <div className="w-16 flex items-center gap-2">
                      <QtSelect
                        value={quantity}
                        onChange={(n) =>
                          useCartStore.getState().setItemQuantity(id, n)
                        }
                      />
                      <Trash
                        className="w-6 h-6 cursor-pointer text-gray-500 hover:text-gray-700"
                        onClick={() => {
                          useCartStore.getState().removeItem(id);
                        }}
                      />
                    </div>
                    {/* Total price for this item */}
                    <div className="text-base font-semibold w-20 text-right">
                      ${itemTotal.toFixed(2)}
                    </div>
                  </div>
                );
              })
            )}
          </div>
          <div className="mt-8 px-2 text-xl flex justify-between">
            <span className="text-stone-600 font-medium">Total</span>
            <span className="text-stone-800">${total.toFixed(2)}</span>
          </div>
        </div>

        <div className="lg:w-1/3">
          <PaymentMethod onCheckout={handleCheckout} />
        </div>
      </div>
    </div>
  );
}
