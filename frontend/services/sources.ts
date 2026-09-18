import { api } from "@/lib/api-client";
import type { ConnectorOut, Envelope, SourceOut } from "@/types/api";

export const listSources = () => api<Envelope<SourceOut[]>>("/sources");
export const listConnectors = () => api<Envelope<ConnectorOut[]>>("/connectors");
export const connectorHealth = () =>
  api<Envelope<{ connector_id: string; health: string; status: string }[]>>("/connectors/health");
export const runConnector = (key: string) =>
  api<Envelope<Record<string, unknown>>>(`/connectors/${key}/run`, { method: "POST" });
export const connectorRuns = (key: string) =>
  api<Envelope<Record<string, unknown>[]>>(`/connectors/${key}/runs?limit=10`);
