import { cn } from "@/utils/cn";

export function Card({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-zinc-800/80 bg-zinc-900/60 backdrop-blur",
        "shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-zinc-800/80 px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-zinc-100">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}
