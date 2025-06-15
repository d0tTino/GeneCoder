"use client";

import Link from "next/link";
import { ShoppingCart, Heart } from "lucide-react";
import { useCartStore } from "@/stores/cartStore";

export default function Navbar() {
  const totalQty = useCartStore((s) =>
    s.items.reduce((acc, i) => acc + i.quantity, 0)
  );
  // Link to shop categories under /shop/[category]
  const navItems = [
    { label: "Just In", href: "/shop/just-in" },
    { label: "Clothes", href: "/shop/clothes" },
    { label: "Shoes", href: "/shop/shoes" },
    { label: "Accessories", href: "/shop/accessories" },
    { label: "Offers", href: "/shop/offers" },
  ];

  return (
    <nav className="w-full border-b border-stone-200 py-2">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-4 py-3">
        <div className="text-2xl font-bold mb-0.5">
          <Link href="/">THE STORE</Link>
        </div>
        <div className="hidden md:flex md:flex-1 justify-center space-x-6">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-stone-600 hover:text-stone-900"
            >
              {item.label}
            </Link>
          ))}
        </div>
        <div className="flex items-center justify-end space-x-4">
          <Link
            href="/favorites"
            className="relative text-stone-700 hover:text-stone-900"
          >
            <Heart className="w-5 h-5 text-stone-700 hover:text-red-600 transition-colors duration-200" />
          </Link>
          <Link
            href="/cart"
            className="relative text-stone-700 hover:text-stone-900"
          >
            <ShoppingCart className="w-5 h-5 text-stone-700 hover:text-stone-900 transition-colors duration-200" />
            {totalQty > 0 && (
              <span className="absolute -top-1 -right-2 flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-xs text-white">
                {totalQty}
              </span>
            )}
          </Link>
        </div>
      </div>
    </nav>
  );
}
