import { cn } from "@/utils/cn";

interface TableProps {
  headers: string[];
  children: React.ReactNode;
  onRowClick?: () => void;
  className?: string;
}

export function Table({ headers, children, onRowClick, className }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full text-left text-sm", className)}>
        <thead>
          <tr className="border-b border-zinc-800 text-[11px] uppercase tracking-wider text-zinc-500">
            {headers.map((h) => (
              <th key={h} className="px-4 py-2.5 font-medium whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60">
          {Array.isArray(children)
            ? children
            : [children]}
        </tbody>
      </table>
    </div>
  );
}

export function Tr({
  children,
  onRowClick,
}: {
  children: React.ReactNode;
  onRowClick?: () => void;
}) {
  return (
    <tr
      onClick={onRowClick}
      className={cn(
        "text-zinc-300 transition-colors",
        onRowClick && "cursor-pointer hover:bg-white/[0.03]",
      )}
    >
      {children}
    </tr>
  );
}

export function Td({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return <td className={cn("px-4 py-3 align-middle", className)}>{children}</td>;
}
