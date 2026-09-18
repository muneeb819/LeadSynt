import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";

export function ModuleRoadmap({
  title,
  description,
  module,
  planned,
  foundation,
}: {
  title: string;
  description: string;
  module: string;
  planned: string[];
  foundation: string[];
}) {
  return (
    <div>
      <PageHeader
        title={title}
        description={description}
        actions={<Badge tone="amber">NEXT PHASE MODULE</Badge>}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
            Foundation already in place
          </p>
          <ul className="mt-3 space-y-2">
            {foundation.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                <span className="mt-0.5 text-emerald-400">✓</span>
                {f}
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
            Planned for {module} phase
          </p>
          <ul className="mt-3 space-y-2">
            {planned.map((p) => (
              <li key={p} className="flex items-start gap-2 text-sm text-zinc-400">
                <span className="mt-0.5 text-zinc-600">○</span>
                {p}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
