import { api } from "@/lib/api-client";
import type { Envelope, QaFinding, QaRun } from "@/types/api";

export const runQaSweep = () =>
  api<Envelope<{ qa_run_id: string; counts: Record<string, number>; summary: string }>>(
    "/qa/sweep",
    { method: "POST" },
  );
export const listQaRuns = () => api<Envelope<QaRun[]>>("/qa/runs?limit=20");
export const listQaFindings = (params: string = "") =>
  api<Envelope<QaFinding[]>>(`/qa/findings?limit=50${params}`);
