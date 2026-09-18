import { cn } from "@/utils/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-5 w-5 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500",
        className,
      )}
      aria-label="Loading"
    />
  );
}

export function LoadingRow({ cols = 8 }: { cols?: number }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16">
      <Spinner />
      <span className="text-sm text-zinc-500">
        {cols ? "Loading data…" : "Loading…"}
      </span>
    </div>
  );
}

export function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-16 text-center">
      <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-800/80 text-lg">
        ◌
      </div>
      <p className="text-sm font-medium text-zinc-300">{title}</p>
      {hint && <p className="max-w-sm text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-16 text-center">
      <p className="text-sm font-medium text-rose-400">Something went wrong</p>
      <p className="max-w-md text-xs text-zinc-500">{message}</p>
    </div>
  );
}
