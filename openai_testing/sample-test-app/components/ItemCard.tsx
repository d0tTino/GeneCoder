import React from "react";

import { useCartStore } from "@/stores/cartStore";
import { Minus, Plus } from "lucide-react";
import { ShoppingCart } from "lucide-react";

interface ItemCardProps {
  item: {
    id: number;
    productDisplayName: string;
    baseColour: string;
    priceUSD?: number;
    imageURL: string;
  };
}

const ItemCard: React.FC<ItemCardProps> = ({ item }) => {
  const addItem = useCartStore((s) => s.addItem);
  const increment = useCartStore((s) => s.incrementItem);
  const decrement = useCartStore((s) => s.decrementItem);
  const quantity = useCartStore(
    (s) => s.items.find((i) => i.id === item.id)?.quantity || 0
  );

  const handleAddToCart = (e: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    e.stopPropagation();
    addItem(item.id);
  };

  return (
    <div className="flex flex-col h-full cursor-pointer bg-stone-100 p-4 rounded-sm">
      {/* Product image + title */}
      <div className="flex flex-col items-center flex-grow">
        <img
          src={item.imageURL}
          alt={item.productDisplayName}
          className="w-full object-cover"
        />
        <div className="w-full m-4">
          <h3 className="font-medium text-sm text-stone-800 line-clamp-2">
            {item.productDisplayName}
          </h3>
        </div>
      </div>

      <div className="w-full py-2 flex items-center justify-between">
        <span className="text-sm font-medium text-stone-900">
          {`$${item.priceUSD ?? "N/A"}`}
        </span>
        {quantity > 0 ? (
          <div className="flex items-center md:gap-1">
            <div
              onClick={(e) => {
                e.stopPropagation();
                decrement(item.id);
              }}
              className="px-2 py-1 text-xs cursor-pointer"
            >
              <Minus className="w-3 h-3" />
            </div>
            <span className="text-sm w-4 text-center">{quantity}</span>
            <div
              onClick={(e) => {
                e.stopPropagation();
                increment(item.id);
              }}
              className="px-2 py-1 text-xs cursor-pointer"
            >
              <Plus className="w-3 h-3" />
            </div>
          </div>
        ) : (
          <div
            onClick={(e) => {
              e.stopPropagation();
              handleAddToCart(e);
            }}
            className="text-[10px] md:text-xs font-medium whitespace-nowrap text-white bg-stone-900 px-3 py-1.5 rounded-sm cursor-pointer hover:bg-stone-700 transition-colors duration-200"
          >
            <ShoppingCart className="w-4 h-4" />
          </div>
        )}
      </div>
    </div>
  );
};

export default ItemCard;
