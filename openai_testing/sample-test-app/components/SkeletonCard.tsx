import { Skeleton } from "@/components/ui/skeleton"
import { Card } from "@/components/ui/card"

export function SkeletonCard() {
  return (
    <Card className="flex flex-col h-full">
      <div className="p-4 flex flex-col items-center flex-grow">
        {/* Image placeholder */}
        <Skeleton className="mb-2 w-full h-[200px] rounded-md" />
        {/* Title placeholder */}
        <div className="w-full p-0">
          <Skeleton className="h-5 w-[60%]" />
        </div>
      </div>

      {/* Bottom price block placeholder */}
      <div className="w-full py-2 bg-amber-100 text-center">
        <Skeleton className="h-5 w-[30%] mx-auto" />
      </div>
    </Card>
  )
}
