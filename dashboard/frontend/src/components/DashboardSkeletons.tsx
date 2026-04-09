import { Card } from "@heroui/react/card";
import { Skeleton } from "@heroui/react/skeleton";

export function StatGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <Card.Root
          key={i}
          className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-sm ring-1 ring-slate-100/80 dark:border-slate-700 dark:bg-slate-900"
        >
          <Skeleton.Root className="mb-3 h-3 w-24 rounded-md" />
          <Skeleton.Root className="h-9 w-16 rounded-md" />
          <Skeleton.Root className="mt-3 h-3 w-full max-w-[12rem] rounded-md" />
        </Card.Root>
      ))}
    </div>
  );
}

export function CardRowSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-4">
      {Array.from({ length: rows }).map((_, i) => (
        <Card.Root
          key={i}
          className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <Card.Header className="space-y-3 px-6 pt-6">
            <div className="flex flex-wrap items-center gap-2">
              <Skeleton.Root className="h-5 w-40 rounded-md" />
              <Skeleton.Root className="h-5 w-14 rounded-full" />
            </div>
            <Skeleton.Root className="h-4 w-full max-w-xl rounded-md" />
            <Skeleton.Root className="h-3 w-48 rounded-md" />
          </Card.Header>
        </Card.Root>
      ))}
    </div>
  );
}

export function HomeSectionCardSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card.Root
          key={i}
          className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-100/80 dark:border-slate-700 dark:bg-slate-900"
        >
          <Skeleton.Root className="h-5 w-[65%] max-w-[10rem] rounded-md" />
          <Skeleton.Root className="mt-2 h-3 w-16 rounded-md" />
          <Skeleton.Root className="mt-4 h-3 w-full rounded-md" />
          <Skeleton.Root className="mt-2 h-3 w-4/5 rounded-md" />
        </Card.Root>
      ))}
    </div>
  );
}
