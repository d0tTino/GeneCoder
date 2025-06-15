import { notFound } from "next/navigation";
import ShopPageContent from "@/components/ShopPageContent";
import { categoryFilter } from "@/lib/shopConfig";

interface ShopCategoryPageProps {
  params: Promise<{ category: string }>;
}

/**
 * Server component for /shop/[category]
 */
export default async function ShopCategoryPage({
  params,
}: ShopCategoryPageProps) {
  const { category } = await params;
  // Validate category
  if (!(category in categoryFilter)) notFound();
  return <ShopPageContent category={category} />;
}
