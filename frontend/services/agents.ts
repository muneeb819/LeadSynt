import { api } from "@/lib/api-client";
import type { Agent, AgentRun, Envelope } from "@/types/api";

export const listAgents = () => api<Envelope<Agent[]>>("/agents");
export const agentRuns = (agentId: string) =>
  api<Envelope<AgentRun[]>>(`/agents/${agentId}/runs?limit=20`);
