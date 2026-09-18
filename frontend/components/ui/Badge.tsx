import { cn } from "@/utils/cn";

type Tone = "green" | "amber" | "red" | "blue" | "zinc" | "violet" | "cyan";

const TONES: Record<Tone, string> = {
  green: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/25",
  amber: "bg-amber-500/10 text-amber-400 ring-amber-500/25",
  red: "bg-rose-500/10 text-rose-400 ring-rose-500/25",
  blue: "bg-sky-500/10 text-sky-400 ring-sky-500/25",
  zinc: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/25",
  violet: "bg-violet-500/10 text-violet-400 ring-violet-500/25",
  cyan: "bg-cyan-500/10 text-cyan-400 ring-cyan-500/25",
};

export function Badge({
  tone = "zinc",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tones: Record<string, Tone> = {
    DISCOVERED: "zinc",
    INGESTED: "zinc",
    PROCESSING: "blue",
    REVIEW_REQUIRED: "amber",
    VERIFICATION_PENDING: "amber",
    VERIFIED: "green",
    QUALIFIED: "green",
    OUTREACH_READY: "cyan",
    OUTREACH_ACTIVE: "cyan",
    REPLIED: "violet",
    HOT_LEAD: "red",
    AWAITING_HUMAN: "amber",
    MEETING_BOOKED: "violet",
    NEGOTIATION: "violet",
    PROPOSAL_SENT: "violet",
    WON: "green",
    LOST: "zinc",
    DISQUALIFIED: "zinc",
    DUPLICATE: "amber",
    EXPIRED: "zinc",
    ARCHIVED: "zinc",
  };
  return <Badge tone={tones[status] || "zinc"}>{status.replaceAll("_", " ")}</Badge>;
}

export function VerificationBadge({ status }: { status: string }) {
  const tones: Record<string, Tone> = {
    VERIFIED: "green",
    PENDING: "amber",
    FAILED: "red",
    UNVERIFIED: "zinc",
    UNKNOWN: "zinc",
    STALE: "amber",
  };
  return <Badge tone={tones[status] || "zinc"}>{status}</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tones: Record<string, Tone> = {
    CRITICAL: "red",
    HIGH: "red",
    MEDIUM: "amber",
    LOW: "blue",
    INFO: "zinc",
  };
  return <Badge tone={tones[severity] || "zinc"}>{severity}</Badge>;
}

export function HealthBadge({ health }: { health: string }) {
  const tones: Record<string, Tone> = {
    HEALTHY: "green",
    DEGRADED: "amber",
    DOWN: "red",
    UNKNOWN: "zinc",
    ACTIVE: "green",
    ERROR: "red",
    RUNNING: "cyan",
  };
  return <Badge tone={tones[health] || "zinc"}>{health}</Badge>;
}
