"use client";
import StyleCardContainer from "@/components/ItemsGrid";
import FilterSidebar from "@/components/FilterSidebar";

/**
 * Shop landing – shows all products with filters.
 */
export default function ShopHomePage() {
  return (
    <div className="min-h-screen p-8 bg-white">
      <h1 className="text-3xl font-bold mb-6">Shop All</h1>
      <div className="flex gap-8">
        <div className="w-1/4">
          <FilterSidebar />
        </div>
        <div className="flex-1">
          <StyleCardContainer />
        </div>
      </div>
    </div>
  );
}
