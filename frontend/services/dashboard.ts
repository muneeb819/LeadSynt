import { api } from "@/lib/api-client";
import type { DashboardData, Envelope } from "@/types/api";

export const getDashboard = () => api<Envelope<DashboardData>>("/analytics/dashboard");
