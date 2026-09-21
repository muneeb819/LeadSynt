// API contracts (mirrors backend Pydantic schemas)

export interface Envelope<T> {
  data: T;
  request_id?: string | null;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: unknown;
    request_id?: string | null;
  };
}

export interface Page<T> {
  items: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    cursor?: string;
  };
}

export interface ContactOut {
  id: string;
  full_name: string;
  title: string | null;
  work_email: string | null;
  phone: string | null;
  profile_url: string | null;
  company_id: string | null;
  role?: string | null;
}

export interface CompanyOut {
  id: string;
  legal_name: string;
  trade_name: string | null;
  domain: string | null;
  website: string | null;
  industry: string | null;
  country: string | null;
  is_verified: boolean;
  role?: string | null;
}

export interface Ticket {
  id: string;
  reference: string;
  status: string;
  type_code: string;
  type_name: string;
  category_code: string | null;
  domain: string | null;
  market_sector: string | null;
  product: string | null;
  service: string | null;
  requirement: string | null;
  intent_level: string | null;
  urgency: string | null;
  budget: number | null;
  currency: string | null;
  deal_size: string | null;
  location: string | null;
  jurisdiction: string | null;
  timezone: string | null;
  pain_point: string | null;
  platform: string | null;
  platform_url: string | null;
  original_url: string | null;
  official_website_url: string | null;
  discovered_at: string | null;
  published_at: string | null;
  last_verified_at: string | null;
  discovered_by: string | null;
  lead_score: number | null;
  intent_score: number | null;
  risk_score: number | null;
  confidence: number | null;
  verification_status: string;
  freshness: string;
  duplicate_status: string;
  owner_id: string | null;
  notes: string | null;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
  contacts: ContactOut[];
  companies: CompanyOut[];
}

export interface TicketDetail extends Ticket {
  verification_history: VerificationRecord[];
}

export interface VerificationRecord {
  id: string;
  kind: string;
  result: string;
  verified_at: string | null;
  verified_by: string | null;
  confidence: number | null;
  evidence: Record<string, unknown> | null;
  notes: string | null;
}

export interface DashboardData {
  kpis: {
    new_tickets_24h: number;
    verified_tickets: number;
    qualified_tickets: number;
    hot_leads: number;
    replies: number;
    meetings: number;
    open_deals: number;
    won_deals: number;
    avg_lead_score: number;
  };
  pipeline_by_status: Record<string, number>;
  health: {
    connectors: { connector_id: string; health: string }[];
    connectors_total: number;
    connectors_healthy: number;
    ai_runs_failed: number;
    job_runs_failed: number;
  };
  generated_at: string;
}

export interface Agent {
  id: string;
  agent_id: string;
  name: string;
  version: string;
  purpose: string;
  status: string;
  system_instructions: string | null;
  allowed_tools: string[];
  total_runs: number;
  total_cost_usd: number;
  max_cost_usd_per_run: number;
  monthly_budget_usd: number;
}

export interface AgentRun {
  id: string;
  status: string;
  kind: string | null;
  ticket_id: string | null;
  confidence: number | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  error: string | null;
  output: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AgentAnalyticsItem {
  agent: Agent;
  runs: {
    total: number;
    completed: number;
    failed: number;
    cancelled: number;
    avg_confidence: number | null;
  };
  cost: {
    total_usd: number;
    avg_per_run_usd: number;
  };
  budget: {
    monthly_budget_usd: number;
    spent_this_month_usd: number;
    remaining_usd: number | null;
    enforced: boolean;
  };
  trend_7d: Record<string, number>;
  last_run_at: string | null;
}

export interface AgentAnalyticsResponse {
  items: AgentAnalyticsItem[];
  overall: {
    agents: number;
    runs: number;
    failed: number;
    total_cost_usd: number;
    llm_configured: boolean;
  };
  generated_at: string;
}

export interface AIProviderOut {
  id: string;
  provider_id: string;
  name: string;
  kind: string;
  base_url: string;
  api_key_env: string | null;
  is_default: boolean;
  enabled: boolean;
  model_count: number;
}

export interface AIModelOut {
  id: string;
  model_id: string;
  provider_id: string | null;
  display_name: string;
  context_window: number;
  input_price_per_mtok: number;
  output_price_per_mtok: number;
  enabled: boolean;
}

export interface QaFinding {
  id: string;
  run_id: string;
  category: string;
  severity: string;
  title: string;
  description: string | null;
  evidence: Record<string, unknown> | null;
  root_cause_hypothesis: string | null;
  recommended_action: string | null;
  affected_component: string | null;
  test_recommendation: string | null;
  status: string;
  created_at: string;
}

export interface QaRun {
  id: string;
  trigger: string;
  status: string;
  summary: string | null;
  metrics: Record<string, number> | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface SourceOut {
  id: string;
  name: string;
  platform: string | null;
  kind: string;
  base_url: string | null;
  description: string | null;
  is_active: boolean;
  compliance_notes: string | null;
}

export interface ConnectorOut {
  id: string;
  connector_id: string;
  source_id: string;
  source_name: string | null;
  status: string;
  auth_method: string;
  schedule_cron: string | null;
  rate_limit_per_hour: number | null;
  last_run_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  health: string;
  configuration: Record<string, unknown>;
}

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
  last_login_at: string | null;
}

export interface MeOut {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
  timezone: string;
}

export interface NotificationOut {
  id: string;
  type: string;
  title: string;
  body: string | null;
  ticket_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AuditRow {
  id: string;
  timestamp: string;
  actor_id: string | null;
  actor_type: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  meta: Record<string, unknown> | null;
}

export interface SettingOut {
  key: string;
  value: Record<string, unknown>;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export const TICKET_STATUSES = [
  "DISCOVERED", "INGESTED", "PROCESSING", "REVIEW_REQUIRED",
  "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED", "OUTREACH_READY",
  "OUTREACH_ACTIVE", "REPLIED", "HOT_LEAD", "AWAITING_HUMAN",
  "MEETING_BOOKED", "NEGOTIATION", "PROPOSAL_SENT", "WON", "LOST",
  "DISQUALIFIED", "DUPLICATE", "EXPIRED", "ARCHIVED",
] as const;
