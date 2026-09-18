import { Card } from "./Card";
import { cn } from "@/utils/cn";

export function StatCard({
  label,
  value,
  sub,
  accent = "indigo",
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "indigo" | "emerald" | "amber" | "rose" | "cyan" | "violet";
}) {
  const accents: Record<string, string> = {
    indigo: "from-indigo-500/15 to-transparent text-indigo-400",
    emerald: "from-emerald-500/15 to-transparent text-emerald-400",
    amber: "from-amber-500/15 to-transparent text-amber-400",
    rose: "from-rose-500/15 to-transparent text-rose-400",
    cyan: "from-cyan-500/15 to-transparent text-cyan-400",
    violet: "from-violet-500/15 to-transparent text-violet-400",
  };
  return (
    <Card className="relative overflow-hidden p-4">
      <div
        className={cn(
          "pointer-events-none absolute inset-0 bg-gradient-to-br opacity-60",
          accents[accent],
        )}
      />
      <div className="relative">
        <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
          {label}
        </p>
        <p className={cn("mt-1.5 text-2xl font-semibold tabular-nums", accents[accent].split(" ").pop())}>
          {value}
        </p>
        {sub && <p className="mt-0.5 text-[11px] text-zinc-500">{sub}</p>}
      </div>
    </Card>
  );
}
