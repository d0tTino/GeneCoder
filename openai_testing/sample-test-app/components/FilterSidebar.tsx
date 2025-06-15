"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { categoryFilter } from "@/lib/shopConfig";
import { ChevronDown, ChevronRight } from "lucide-react";
import { filterConfig } from "@/lib/filterConfig";
import { StyleFilters, useStyleFiltersStore } from "@/stores/styleFiltersStore";
import { Checkbox } from "@/components/ui/checkbox";
export default function FilterSidebar() {
  const { clearFilters, toggleFilter, ...filters } = useStyleFiltersStore();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      filterConfig.map(
        (g) => [g.title, g.title === "Department"] as [string, boolean]
      )
    )
  );

  const pathname = usePathname();
  useEffect(() => {
    // Reset filters on mount
    clearFilters();
    // If on a specific shop category with a default category filter, open the Categories group
    const segments = pathname?.split("/") || [];
    const cat = segments[2];
    if (cat && categoryFilter[cat] != null) {
      setOpenGroups((prev) => ({ ...prev, Categories: true }));
    }
  }, [clearFilters, pathname]);

  // Determine if current category should hide the "Categories" group
  const segments = pathname?.split("/") || [];
  const currentCat = segments[2];
  const hideCategories = ["shoes", "clothes", "accessories"].includes(
    currentCat
  );
  // Filter out the Categories group on specific category pages
  const visibleConfig = filterConfig.filter(
    (g) => !(g.title === "Categories" && hideCategories)
  );
  return (
    <aside className="w-full bg-white p-6 border-y border-stone-200 sticky top-16 max-h-[80vh] overflow-y-auto">
      {visibleConfig.map((group) => {
        const isOpen = openGroups[group.title];
        const clearGroup = () => {
          if (group.filterKey) {
            // clear only this group's selections
            useStyleFiltersStore.setState({
              [group.filterKey]: [] as string[],
            });
          }
        };
        return (
          <div key={group.title} className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <span className="font-medium text-stone-900">{group.title}</span>
              <div className="items-center gap-2 hidden md:flex">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    clearGroup();
                  }}
                  className="text-xs text-stone-600 hover:text-stone-900 transition-colors duration-200 cursor-pointer"
                >
                  Clear
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenGroups((prev) => ({
                      ...prev,
                      [group.title]: !prev[group.title],
                    }));
                  }}
                  className="text-stone-500 hover:text-stone-700"
                >
                  {isOpen ? (
                    <ChevronDown size={16} />
                  ) : (
                    <ChevronRight size={16} />
                  )}
                </button>
              </div>
            </div>
            {isOpen && (
              <div className="space-y-2">
                {group.items.map((item) => {
                  const checked =
                    group.filterKey &&
                    filters[group.filterKey as keyof typeof filters]?.includes(
                      item.filterValue
                    );
                  return (
                    <label
                      key={item.title}
                      className="flex items-center cursor-pointer gap-2"
                    >
                      <Checkbox
                        className="mr-2"
                        checked={!!checked}
                        onCheckedChange={() =>
                          group.filterKey &&
                          toggleFilter({
                            key: group.filterKey as keyof StyleFilters,
                            value: item.filterValue,
                          })
                        }
                      />
                      <span
                        className={
                          checked ? "text-stone-900" : "text-stone-700"
                        }
                      >
                        {item.title}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}
