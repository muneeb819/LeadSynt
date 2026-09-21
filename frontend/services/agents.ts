import { api } from "@/lib/api-client";
import type {
  Agent,
  AgentAnalyticsResponse,
  AgentRun,
  AIModelOut,
  AIProviderOut,
  Envelope,
} from "@/types/api";

export const listAgents = () => api<Envelope<Agent[]>>("/agents");
export const agentRuns = (agentId: string) =>
  api<Envelope<AgentRun[]>>(`/agents/${agentId}/runs?limit=20`);
export const agentAnalytics = () =>
  api<Envelope<AgentAnalyticsResponse>>("/agents/analytics");
export const agentProviders = () =>
  api<Envelope<AIProviderOut[]>>("/agents/providers");
export const agentModels = () =>
  api<Envelope<AIModelOut[]>>("/agents/models");
export const runAgent = (
  agentId: string,
  body: { ticket_id?: string; payload?: Record<string, unknown> },
) =>
  api<Envelope<AgentRun>>(`/agents/${agentId}/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });